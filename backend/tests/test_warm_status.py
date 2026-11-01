"""GET /warm/status, GET /doc, the 12-hour caches and warm_stage1 (a warmed URL opens instantly)."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from api import analyze
from api.main import app
from pipeline import warmer
from test_analyze import PARAS, URL, Stubs, fresh, run, steps  # noqa: F401  (fresh is autouse there; re-exported here)


@pytest.fixture
def stubs(monkeypatch):
    return Stubs(monkeypatch)


@pytest.fixture
def client():
    return TestClient(app)


def test_status_shape_and_values(client, stubs):
    warmer.state.running, warmer.state.queued, warmer.state.last_run_at = False, 0, None
    assert client.get("/warm/status").json() == {"running": False, "queued": 0, "cached_count": 0, "last_run_at": None}
    asyncio.run(analyze.warm_stage1(URL))
    from datetime import datetime, timezone
    warmer.state.running, warmer.state.queued = True, 3
    warmer.state.last_run_at = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    body = client.get("/warm/status").json()
    assert body == {"running": True, "queued": 3, "cached_count": 1, "last_run_at": "2026-10-31T12:00:00Z"}
    warmer.state.running, warmer.state.queued, warmer.state.last_run_at = False, 0, None


def test_all_caches_live_twelve_hours():
    assert analyze.CACHE_TTL_S == 12 * 3600
    for cache in (analyze._stage1, analyze._applies, analyze._explainers):
        assert cache.ttl == 12 * 3600


def test_warm_stage1_does_the_profile_independent_work_once(stubs):
    assert asyncio.run(analyze.warm_stage1(URL)) is True
    assert stubs.calls == {"fetch": 1, "extract": 1, "retry": 1, "applies": 0, "explain": 0}  # no applicability/explainer
    assert asyncio.run(analyze.warm_stage1(URL)) is False  # already cached: nothing to do
    assert stubs.calls["extract"] == 1 and analyze.is_cached(URL) and analyze.cached_count() == 1


def test_opening_a_warmed_url_shows_cached_steps_and_no_new_extraction(client, stubs):
    asyncio.run(analyze.warm_stage1(URL))
    events, _ = run(client)
    done = {e["name"]: e["detail"] for e in events if e["type"] == "step" and e["status"] == "done"}
    for name in ("fetch_document", "extract", "verify", "retry"):
        assert done[name].endswith("(cached)"), name
    assert stubs.calls["extract"] == 1 and stubs.calls["fetch"] == 1 and stubs.calls["retry"] == 1
    assert events[-1]["type"] == "result" and events[-1]["counts"]["verified"] == 1


def test_a_failed_warm_leaves_nothing_cached(stubs):
    from sources.errors import FetchFailed
    stubs.extract_error = FetchFailed("down", URL)
    with pytest.raises(FetchFailed):
        asyncio.run(analyze.warm_stage1(URL))
    assert not analyze.is_cached(URL)


# ---------------------------------------------------------------- /doc

def test_doc_returns_the_cached_paragraphs_without_analysing(client, stubs):
    asyncio.run(analyze.warm_stage1(URL))
    before = dict(stubs.calls)
    r = client.get("/doc", params={"url": URL})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Test circular" and body["url"] == URL and body["fetched_at"].startswith("2026-10-31")
    assert [p["id"] for p in body["paragraphs"]] == [p.id for p in PARAS]
    assert stubs.calls == before


def test_doc_not_in_cache_is_a_404_with_a_message(client, stubs):
    r = client.get("/doc", params={"url": URL})
    assert r.status_code == 404 and "Open it again" in r.json()["error"]
    assert stubs.calls["fetch"] == 0  # it never fetches


@pytest.mark.parametrize("url", ["", "https://example.com/x", "not a url", "https://rbi.org.in.evil.com/x"])
def test_doc_refuses_other_hosts(client, stubs, url):
    r = client.get("/doc", params={"url": url})
    assert r.status_code == 400 and "error" in r.json()

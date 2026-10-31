from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api import routes_health
from api.main import app
from api.schemas import LLMHealth
from sources.feeds import FeedItem, FeedResult
from sources.http import FetchError
from sources.pagecheck import PageInfo

NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fresh_cache():
    routes_health._cache = routes_health.StatusCache()


@pytest.fixture
def client():
    return TestClient(app)


def stub(monkeypatch, *, failing=None, page_fails=None):
    calls = {"feed": 0}

    async def fake_feed(source):
        calls["feed"] += 1
        if source == failing:
            return FeedResult(source, False, error=f"{source.upper()} unreachable, retried 2 times (timeout)")
        return FeedResult(source, True, [FeedItem(source, "t", f"https://x/{source}", None)], NOW)

    async def fake_page(url, label):
        if url.endswith(str(page_fails)):
            raise FetchError(f"{label} refused the request (HTTP 403)")
        return PageInfo(url, 200, 100, None)

    async def fake_ping():
        return LLMHealth(ok=True, model="m")

    monkeypatch.setattr(routes_health, "fetch_feed", fake_feed)
    monkeypatch.setattr(routes_health, "check_page", fake_page)
    monkeypatch.setattr(routes_health.llm_health, "ping", fake_ping)
    return calls


def test_all_ok_shape(client, monkeypatch):
    stub(monkeypatch)
    body = client.get("/health").json()
    assert set(body["sources"]) == {"rbi", "sebi", "pib"}
    assert body["sources"]["rbi"] == {"ok": True, "last_fetch": "2026-10-31T00:00:00Z", "count": 1, "error": None}
    assert body["llm"] == {"ok": True, "model": "m", "error": None}


def test_one_source_down_does_not_affect_others(client, monkeypatch):
    stub(monkeypatch, failing="rbi")
    s = client.get("/health").json()["sources"]
    assert s["rbi"]["ok"] is False and "RBI unreachable" in s["rbi"]["error"]
    assert s["sebi"]["ok"] is True and s["pib"]["ok"] is True


def test_page_failure_marks_source_not_ok(client, monkeypatch):
    stub(monkeypatch, page_fails="sebi")
    s = client.get("/health").json()["sources"]["sebi"]
    assert s["ok"] is False and "newest page failed" in s["error"] and s["count"] == 1


def test_unexpected_crash_never_leaks_traceback(client, monkeypatch):
    stub(monkeypatch)

    async def boom(source):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(routes_health, "fetch_feed", boom)
    r = client.get("/health")
    assert r.status_code == 200
    assert "secret internals" not in r.text and "failed unexpectedly" in r.text


def test_results_are_cached(client, monkeypatch):
    calls = stub(monkeypatch)
    client.get("/health")
    client.get("/health")
    assert calls["feed"] == 3  # one per source, second request served from cache


def test_cors_only_for_allowed_origin(client, monkeypatch):
    stub(monkeypatch)
    ok = client.get("/health", headers={"Origin": "http://localhost:3000"})
    bad = client.get("/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers


def test_allowed_origin_accepts_comma_separated_list(monkeypatch):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    import config

    monkeypatch.setenv("ALLOWED_ORIGIN", "http://localhost:3000, https://pramaan.vercel.app/ ,")
    assert config.allowed_origins() == ["http://localhost:3000", "https://pramaan.vercel.app"]

    # the middleware is built at import time, so build a fresh app from the parsed list
    mini = FastAPI()
    mini.add_middleware(CORSMiddleware, allow_origins=config.allowed_origins(), allow_methods=["GET"])

    @mini.get("/x")
    def x():
        return {}

    c = TestClient(mini)
    for origin in ("http://localhost:3000", "https://pramaan.vercel.app"):
        assert c.get("/x", headers={"Origin": origin}).headers["access-control-allow-origin"] == origin
    assert "access-control-allow-origin" not in c.get("/x", headers={"Origin": "https://evil.example"}).headers


def test_runtime_import_check_ok(client, monkeypatch):
    stub(monkeypatch)
    assert client.get("/health").json()["runtime"] == {"ok": True, "error": None}


def test_broken_dependency_shows_up_in_runtime_without_breaking_health(client, monkeypatch):
    stub(monkeypatch)
    real = routes_health.importlib.import_module

    def broken(name, *a, **kw):
        if name == "pipeline.fetch_document":
            raise ImportError("No module named 'pdfplumber'")
        return real(name, *a, **kw)

    monkeypatch.setattr(routes_health.importlib, "import_module", broken)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["runtime"]["ok"] is False and "pdfplumber" in body["runtime"]["error"]
    assert body["sources"]["rbi"]["ok"] is True  # everything else still reported


def test_broken_verifier_dependency_also_shows_up_in_runtime(client, monkeypatch):
    stub(monkeypatch)
    real = routes_health.importlib.import_module

    def broken(name, *a, **kw):
        if name == "verify.verifier":
            raise ImportError("No module named 'rapidfuzz'")
        return real(name, *a, **kw)

    monkeypatch.setattr(routes_health.importlib, "import_module", broken)
    body = client.get("/health").json()
    assert body["runtime"]["ok"] is False and "rapidfuzz" in body["runtime"]["error"]

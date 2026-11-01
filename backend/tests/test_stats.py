"""GET /stats and the in-memory proof counters (inline strings only; verify() is the real one)."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from api import analyze
from api.main import app
from pipeline import stats
from test_analyze import URL, Stubs, fresh, run  # noqa: F401  (fresh resets caches and stats before each test)

SEBI_URL = "https://www.sebi.gov.in/legal/circulars/oct-2026/x_1.html"


@pytest.fixture
def stubs(monkeypatch):
    return Stubs(monkeypatch)


@pytest.fixture
def client():
    return TestClient(app)


def test_empty_snapshot_is_zero_with_null_averages(client):
    body = client.get("/stats").json()
    assert body["circulars_analysed"] == 0 and body["duties_extracted"] == 0
    assert body["avg_latency_ms_fresh"] is None and body["avg_latency_ms_cached"] is None
    assert body["started_at"].endswith("Z")
    assert set(body["by_source"]) == {"rbi", "sebi", "pib"}


def test_one_analysis_counts_each_status(client, stubs):
    asyncio.run(analyze.warm_stage1(URL))
    body = client.get("/stats").json()
    # the stub extracts one real quote (verified) and one invented one (rejected)
    assert (body["circulars_analysed"], body["duties_extracted"]) == (1, 2)
    assert (body["verified"], body["rejected"], body["fixed"]) == (1, 1, 0)
    assert body["by_source"]["rbi"]["circulars_analysed"] == 1 and body["by_source"]["sebi"]["circulars_analysed"] == 0
    assert body["avg_latency_ms_fresh"] is not None and body["avg_latency_ms_cached"] is None


def test_same_url_is_not_counted_twice(client, stubs):
    asyncio.run(analyze.warm_stage1(URL))
    run(client)  # a visitor opens the warmed notice: served from the cache
    run(client)
    body = client.get("/stats").json()
    assert (body["circulars_analysed"], body["duties_extracted"]) == (1, 2)
    assert body["avg_latency_ms_cached"] is not None


def test_a_visitor_analysis_counts_once_and_a_second_url_adds(client, stubs):
    run(client)
    run(client, url=SEBI_URL)
    body = client.get("/stats").json()
    assert body["circulars_analysed"] == 2 and body["duties_extracted"] == 4
    assert body["by_source"]["sebi"]["duties_extracted"] == 2


def test_verifier_test_is_counted_per_url_and_caught(client, stubs):
    run(client, verifier_test="1")
    run(client, verifier_test="1")  # same URL again: latest result replaces, not adds
    body = client.get("/stats").json()
    assert (body["injected_tests_run"], body["injected_tests_caught"]) == (1, 1)
    assert body["duties_extracted"] == 2  # the fake claim is never a duty


def test_failed_analysis_records_nothing(client, stubs):
    from sources.errors import FetchFailed
    stubs.extract_error = FetchFailed("down", URL)
    run(client)
    assert client.get("/stats").json()["circulars_analysed"] == 0


def test_record_injected_only_rejected_counts_as_caught():
    stats.record_injected(URL, "verified")
    assert stats.snapshot()["injected_tests_caught"] == 0

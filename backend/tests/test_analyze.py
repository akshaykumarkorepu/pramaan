"""/analyze with every pipeline stage faked (inline strings only). verify() is the real one, so quote checks are genuine."""
import asyncio
import json
import time
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api import analyze
from api.main import app
from api.schemas import Explainer
from llm.client import CallMeta, on_wait_var
from llm.errors import LLMError
from pipeline.applicability import ApplicabilityMeta
from pipeline.explain import ExplainMeta
from pipeline.extract import ExtractionResult
from pipeline.fetch_document import FetchedDocument
from pipeline.models import ExtractedObligation
from pipeline.paragraphs import Paragraph
from pipeline.retry import RetryCounts, RetryMeta
from api.schemas import Applicability
from sources.errors import FetchFailed

URL = "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=1"
GOOD_QUOTE = "All Co-operative Banks shall file the return by 15 December 2026."
PARAS = [Paragraph(id="1", text="1. " + GOOD_QUOTE), Paragraph(id="2", text="2. Banks must keep records safely.")]


def make_doc(url=URL):
    text = "\n\n".join(p.text for p in PARAS)
    return FetchedDocument(
        title="Test circular", url=url, source="rbi", fetched_at=datetime(2026, 10, 31, tzinfo=timezone.utc),
        paragraphs=PARAS, full_text=text, from_pdf=True, char_count=len(text),
    )


def obligation(quote, deadline=None):
    return ExtractedObligation(
        who="Co-operative Banks", must_do="File the return", deadline=deadline, effective_from=None,
        paragraph="1", quote=quote, penalty_or_consequence=None,
    )


class Stubs:
    """Counts calls and lets a test slow or break a stage."""

    def __init__(self, monkeypatch):
        self.calls = {"fetch": 0, "extract": 0, "retry": 0, "applies": 0, "explain": 0}
        self.extract_delay = 0.0
        self.extract_error = None
        self.extract_hook = None
        monkeypatch.setattr(analyze, "fetch_document", self.fetch)
        monkeypatch.setattr(analyze, "extract", self.extract)
        monkeypatch.setattr(analyze, "retry", self.retry)
        monkeypatch.setattr(analyze, "check_applicability", self.applies)
        monkeypatch.setattr(analyze, "explain", self.explain)

    async def fetch(self, url):
        self.calls["fetch"] += 1
        return make_doc(url)

    async def extract(self, doc):
        self.calls["extract"] += 1
        if self.extract_hook:
            self.extract_hook()
        if self.extract_delay:
            await asyncio.sleep(self.extract_delay)
        if self.extract_error:
            raise self.extract_error
        meta = CallMeta(model_used="model-x", fallback_used=False, latency_ms=7, prompt_tokens=1, completion_tokens=1, attempts=1)
        obs = [obligation(GOOD_QUOTE, "2026-12-15"), obligation("This sentence was invented and is not in the notice at all.")]
        return ExtractionResult(kind="obligations", addressees=["Co-operative Banks"], obligations=obs), meta

    async def retry(self, obligations, doc):
        self.calls["retry"] += 1
        counts = RetryCounts(verified=1, near=0, rejected=1, fixed=0)
        return list(obligations), counts, RetryMeta()

    async def applies(self, profile, doc, extraction, verified):
        self.calls["applies"] += 1
        return Applicability(value="yes", reason="matched addressee line"), ApplicabilityMeta(method="rule", latency_ms=1)

    async def explain(self, title, obligations, applicability, profile, lang):
        self.calls["explain"] += 1
        return Explainer(lang=lang, text="one two three", source="llm"), ExplainMeta(latency_ms=2)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    analyze.clear_caches()
    yield
    analyze.clear_caches()


@pytest.fixture
def stubs(monkeypatch):
    return Stubs(monkeypatch)


@pytest.fixture
def client():
    return TestClient(app)


def run(client, url=URL, profile="coop_bank", lang="te", **extra):
    """-> (events, raw lines) of one /analyze call."""
    params = {"url": url, "profile": profile, "lang": lang, **extra}
    events, lines = [], []
    with client.stream("GET", "/analyze", params=params) as r:
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-cache" and r.headers["x-accel-buffering"] == "no"
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            lines.append(line)
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events, lines


def steps(events):
    return [(e["name"], e["status"]) for e in events if e["type"] == "step"]


ORDER = ["fetch_document", "extract", "verify", "retry", "applicability", "explain"]


def test_event_order_and_result_shape(client, stubs):
    events, _ = run(client)
    assert steps(events) == [(n, s) for n in ORDER for s in ("running", "done")]
    assert [e["type"] for e in events].count("result") == 1 and events[-1]["type"] == "result"
    done = {e["name"]: e["detail"] for e in events if e["type"] == "step" and e["status"] == "done"}
    assert done["fetch_document"] == "2 paragraphs, read from PDF"
    assert done["extract"] == "2 duties found"
    assert done["verify"] == "2 quotes checked: 1 verified, 1 rejected"
    assert done["retry"] == "nothing to fix — skipped"
    assert done["applicability"] == "applies to Co-operative Banks — matched addressee line"
    assert done["explain"] == "Telugu explainer, 3 words"
    r = events[-1]
    assert r["counts"] == {"verified": 1, "rejected": 1, "fixed": 0}
    assert r["applies"]["value"] == "yes" and r["explainer"] == {"lang": "te", "text": "one two three", "source": "llm"}
    assert r["llm"] == {"model": "model-x", "ms": 10}  # extract 7 + applicability 1 + explain 2
    assert r["doc"]["title"] == "Test circular" and len(r["doc"]["paragraphs"]) == 2
    status = {o["quote"]: o["status"] for o in r["obligations"]}
    assert status[GOOD_QUOTE] == "verified" and "rejected" in status.values()  # rejected items are shown
    assert not any(o["injected_test"] for o in r["obligations"])


def test_second_identical_run_is_cached_and_fast(client, stubs):
    run(client)
    t = time.perf_counter()
    events, _ = run(client)
    assert time.perf_counter() - t < 2
    assert stubs.calls == {"fetch": 1, "extract": 1, "retry": 1, "applies": 1, "explain": 1}
    done = [e for e in events if e["type"] == "step" and e["status"] == "done"]
    assert [e["name"] for e in done] == ORDER
    assert all(e["detail"].endswith("(cached)") and e["ms"] == 0 for e in done)
    assert events[-1]["type"] == "result" and events[-1]["llm"]["ms"] == 0


def test_other_profile_and_language_reuse_the_url_cache(client, stubs):
    run(client)
    events, _ = run(client, profile="nbfc", lang="hi")
    details = {e["name"]: e["detail"] for e in events if e["type"] == "step" and e["status"] == "done"}
    assert details["extract"].endswith("(cached)") and details["retry"].endswith("(cached)")
    assert not details["applicability"].endswith("(cached)") and not details["explain"].endswith("(cached)")
    assert stubs.calls["extract"] == 1 and stubs.calls["applies"] == 2 and stubs.calls["explain"] == 2


def test_verifier_test_injects_exactly_one_rejected_item_without_llm(client, stubs):
    run(client)  # warm cache
    events, _ = run(client, verifier_test="1")
    obs = events[-1]["obligations"]
    injected = [o for o in obs if o["injected_test"]]
    assert len(injected) == 1 and injected[0]["status"] == "rejected" and injected[0]["reason"]
    assert injected[0]["deadline"] > date.today().isoformat() and injected[0]["deadline"] <= (date.today() + timedelta(days=60)).isoformat()
    assert stubs.calls["extract"] == 1 and stubs.calls["retry"] == 1  # never extracted again, never retried
    assert events[-1]["counts"] == {"verified": 1, "rejected": 1, "fixed": 0}  # the test claim is not counted
    verify_done = next(e for e in events if e["type"] == "step" and e["name"] == "verify" and e["status"] == "done")
    assert "test claim rejected live" in verify_done["detail"]
    # and it did not leak into the cache
    again, _ = run(client)
    assert not any(o["injected_test"] for o in again[-1]["obligations"])


def test_verifier_test_on_a_fresh_url_also_works(client, stubs):
    events, _ = run(client, verifier_test="1")
    assert sum(o["injected_test"] for o in events[-1]["obligations"]) == 1


def test_failure_in_extract_is_a_failed_step_then_an_error_event(client, stubs):
    stubs.extract_error = LLMError("rate_limit", "The AI service is busy right now. Please try again in a minute.")
    events, _ = run(client)
    assert steps(events) == [("fetch_document", "running"), ("fetch_document", "done"), ("extract", "running"), ("extract", "failed")]
    failed = events[-2]
    assert failed["detail"] == "The AI service is busy right now. Please try again in a minute."
    assert events[-1] == {"type": "error", "step": "extract", "message": failed["detail"], "url": URL}
    assert not any(e["type"] == "result" for e in events)
    assert stubs.extract_error and analyze._stage1.get(URL) is None  # failures are not cached


def test_failure_in_fetch_carries_the_original_link(client, stubs, monkeypatch):
    async def broken(url):
        raise FetchFailed("RBI could not be reached.", url)

    monkeypatch.setattr(analyze, "fetch_document", broken)
    events, _ = run(client)
    assert events[-1]["step"] == "fetch_document" and events[-1]["url"] == URL


def test_unexpected_exception_never_leaks_a_traceback(client, stubs):
    stubs.extract_error = ZeroDivisionError("secret internals")
    events, lines = run(client)
    assert events[-1]["type"] == "error" and "secret internals" not in "".join(lines) and "Traceback" not in "".join(lines)


@pytest.mark.parametrize("params", [
    {"url": "https://evil.example.com/a", "profile": "coop_bank", "lang": "te"},
    {"url": "", "profile": "coop_bank", "lang": "te"},
    {"url": URL, "profile": "banker", "lang": "te"},
    {"url": URL, "profile": "", "lang": "te"},
    {"url": URL, "profile": "coop_bank", "lang": "fr"},
])
def test_invalid_input_is_a_single_error_event(client, stubs, params):
    events, _ = run(client, **params)
    assert len(events) == 1 and events[0]["type"] == "error" and events[0]["step"] == "request" and events[0]["message"]
    assert stubs.calls["fetch"] == 0


def test_pings_are_sent_during_a_slow_step(client, stubs, monkeypatch):
    monkeypatch.setattr(analyze, "PING_INTERVAL_S", 0.05)
    stubs.extract_delay = 0.4
    events, lines = run(client)
    assert lines.count(": ping") >= 3
    assert events[-1]["type"] == "result"


def test_overall_timeout_becomes_an_error_event(client, stubs, monkeypatch):
    monkeypatch.setattr(analyze, "TOTAL_TIMEOUT_S", 0.2)
    stubs.extract_delay = 5
    t = time.perf_counter()
    events, _ = run(client)
    assert time.perf_counter() - t < 3
    assert steps(events)[-1] == ("extract", "failed") and events[-1]["type"] == "error" and events[-1]["step"] == "extract"


def test_rate_limit_wait_is_shown_as_a_running_step(client, stubs):
    stubs.extract_hook = lambda: on_wait_var.get()(26.6)
    events, _ = run(client)
    waits = [e for e in events if e["type"] == "step" and "waiting for AI capacity" in (e["detail"] or "")]
    assert len(waits) == 1 and waits[0]["name"] == "extract" and waits[0]["status"] == "running"
    assert waits[0]["detail"] == "waiting for AI capacity (~27s)"


def test_simultaneous_requests_for_one_url_do_the_work_once(stubs):
    stubs.extract_delay = 0.1

    async def collect(profile):
        return [json.loads(c[6:]) async for c in analyze._stream(URL, profile, "en", False) if c.startswith("data: ")]

    async def both():
        return await asyncio.gather(collect("coop_bank"), collect("coop_bank"))

    a, b = asyncio.run(both())
    assert stubs.calls["extract"] == 1 and stubs.calls["fetch"] == 1 and stubs.calls["explain"] == 1
    assert a[-1]["type"] == b[-1]["type"] == "result"
    assert analyze._locks == {}  # the lock entry is cleaned up


@pytest.mark.parametrize("lang", ["en", "te", "hi"])
def test_explainer_is_never_null_when_nothing_is_verified(client, stubs, monkeypatch, lang):
    from pipeline.explain import explain as real_explain

    async def only_rejected(doc):
        stubs.calls["extract"] += 1
        meta = CallMeta(model_used="model-x", fallback_used=False, latency_ms=1, prompt_tokens=1, completion_tokens=1, attempts=1)
        bad = obligation("This sentence was invented and is not in the notice at all.")
        return ExtractionResult(kind="obligations", addressees=[], obligations=[bad]), meta

    async def no_llm_allowed(*a, **k):
        raise AssertionError("the no-duties note must not call the LLM")

    import pipeline.explain as explain_mod
    monkeypatch.setattr(analyze, "extract", only_rejected)
    monkeypatch.setattr(analyze, "explain", real_explain)  # the real M8 explain(), whose empty case is a template
    monkeypatch.setattr(explain_mod, "call_text", no_llm_allowed)
    events, _ = run(client, lang=lang)
    r = events[-1]
    assert r["type"] == "result" and r["counts"]["verified"] == 0
    assert r["explainer"]["lang"] == lang and r["explainer"]["source"] == "template" and r["explainer"]["text"]
    assert analyze._explainers.get((URL, "coop_bank", lang)) is None  # the plain note is not cached


def test_run_analysis_for_ics_reuses_cache_and_never_calls_explain(stubs):
    first = asyncio.run(analyze.run_analysis(URL, "coop_bank"))
    assert first.type == "result" and first.explainer.source == "template" and first.counts.verified == 1
    assert stubs.calls["explain"] == 0
    asyncio.run(analyze.run_analysis(URL, "coop_bank"))
    assert stubs.calls["extract"] == 1  # second call served from the per-URL cache


def test_run_analysis_returns_an_error_event_instead_of_raising(stubs):
    stubs.extract_error = LLMError("rate_limit", "The AI service is busy right now.")
    err = asyncio.run(analyze.run_analysis(URL, "coop_bank"))
    assert err.type == "error" and err.message == "The AI service is busy right now."

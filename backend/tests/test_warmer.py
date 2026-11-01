"""The background pre-analysis: what it picks, how it paces itself, and that it never gets in a user's way."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from api import analyze, routes_notices
from api.schemas import Notice, NoticesResponse, NoticeSource
from llm import usage_log
from llm.errors import LLMError
from pipeline import warmer
from sources.errors import FetchFailed

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
SRC = {s: NoticeSource(ok=True, error=None, count=1) for s in ("rbi", "sebi", "pib")}


def notice(n, source="rbi", date="2026-10-30", applies="yes"):
    return Notice(
        id=f"id{n}", source=source, title=f"t{n}", url=f"https://www.{source}.org.in/{n}" if source != "rbi" else f"https://www.rbi.org.in/{n}",
        date=date, fetched_at=NOW, applies=applies, reason="r",
    )


def put(profile, *items):
    routes_notices._cache.put(profile, NoticesResponse(items=list(items), sources=SRC), True)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    analyze.clear_caches()
    routes_notices.clear_cache()
    usage_log.clear()
    analyze.active_requests = 0
    warmer.state.running, warmer.state.queued, warmer.state.last_run_at, warmer.state.last_cost = False, 0, None, warmer.DEFAULT_COST
    clock = {"t": NOW}
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        clock["t"] += timedelta(seconds=s)

    monkeypatch.setattr(warmer, "_sleep", fake_sleep)
    monkeypatch.setattr(warmer, "_now", lambda: clock["t"])
    yield type("Env", (), {"clock": clock, "sleeps": sleeps})
    analyze.clear_caches()
    routes_notices.clear_cache()
    usage_log.clear()
    analyze.active_requests = 0


def log_tokens(env, seconds_ago, tokens, model="big"):
    usage_log._records.append({"at": (env.clock["t"] - timedelta(seconds=seconds_ago)).isoformat(), "kind": "json", "role": "primary",
                               "error": None, "model_used": model, "prompt_tokens": tokens, "completion_tokens": 0})


# ---------------------------------------------------------------- picking

def test_union_over_profiles_yes_and_review_only_deduped(fresh):
    put("nbfc", notice(1), notice(2, applies="no"), notice(3, applies="review"))
    put("coop_bank", notice(1), notice(2, applies="yes"), notice(4, applies="no"))
    urls = [n.url for n in warmer.candidates()]
    assert sorted(urls) == sorted(f"https://www.rbi.org.in/{i}" for i in (1, 2, 3))  # 2 is "yes" for one profile; 4 is "no" for all


def test_rbi_and_sebi_newest_first_then_pib_and_max_twelve(fresh):
    items = [notice(i, "rbi", f"2026-10-{10 + i:02d}") for i in range(1, 9)]
    items += [notice(20, "sebi", "2026-10-30"), notice(21, "sebi", "2026-10-05")]
    items += [notice(i, "pib", None, "review") for i in range(30, 38)]
    put("nbfc", *items)
    picked = warmer.candidates()
    assert len(picked) == 12
    assert [n.source for n in picked[:10]] != ["pib"] * 10 and all(n.source != "pib" for n in picked[:10])
    assert [n.date for n in picked[:10]] == sorted((n.date for n in picked[:10]), reverse=True)  # newest first
    assert [n.source for n in picked[10:]] == ["pib", "pib"]


def test_cached_items_are_skipped(fresh, monkeypatch):
    put("nbfc", notice(1), notice(2))
    monkeypatch.setattr(analyze, "is_cached", lambda url: url.endswith("/1"))
    assert [n.url for n in warmer.candidates()] == ["https://www.rbi.org.in/2"]


# ---------------------------------------------------------------- pacing

def test_waits_while_the_minute_window_is_full_then_goes(fresh):
    log_tokens(fresh, 10, 5000)  # 5,000 tokens 10 s ago: 5,000 + 4,000 > 6,000
    asyncio.run(warmer.wait_for_budget())
    assert fresh.sleeps and sum(fresh.sleeps) >= 50  # it had to wait for that call to leave the 60 s window
    assert warmer._window_tokens(fresh.clock["t"] - timedelta(seconds=60)) == 0


def test_goes_at_once_when_there_is_room(fresh):
    log_tokens(fresh, 5, 1000)
    asyncio.run(warmer.wait_for_budget())
    assert fresh.sleeps == []


def test_each_model_has_its_own_budget(fresh):
    log_tokens(fresh, 5, 5000, model="fast")  # the fast model is busy; the big one is idle: that is the bottleneck that counts
    log_tokens(fresh, 5, 1000, model="big")
    assert warmer._window_tokens(fresh.clock["t"] - timedelta(seconds=60)) == 5000  # the largest single model, not the sum


# ---------------------------------------------------------------- one at a time, user first

def test_documents_are_processed_strictly_one_at_a_time(fresh, monkeypatch):
    put("nbfc", *[notice(i) for i in range(1, 5)])
    live, peak, order = 0, 0, []

    async def fake(url):
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        await asyncio.sleep(0)
        order.append(url)
        live -= 1
        analyze._stage1[url] = object()
        return True

    monkeypatch.setattr(analyze, "warm_stage1", fake)
    assert asyncio.run(warmer.run_cycle()) == 4
    assert peak == 1 and len(order) == 4
    assert warmer.state.running is False and warmer.state.queued == 0 and warmer.state.last_run_at == fresh.clock["t"]


def test_nothing_starts_while_a_user_request_is_running(fresh, monkeypatch):
    put("nbfc", notice(1))
    analyze.active_requests = 1
    started_at = []

    async def fake(url):
        started_at.append(analyze.active_requests)
        analyze._stage1[url] = object()
        return True

    monkeypatch.setattr(analyze, "warm_stage1", fake)

    async def release_later(s):  # the user's request ends after the warmer has waited three times
        fresh.sleeps.append(s)
        if len(fresh.sleeps) == 3:
            analyze.active_requests = 0

    monkeypatch.setattr(warmer, "_sleep", release_later)
    asyncio.run(warmer.run_cycle())
    assert started_at == [0] and len(fresh.sleeps) >= 3


def test_user_requests_are_counted_around_the_stream_and_ics(monkeypatch):
    from fastapi.testclient import TestClient
    from api.main import app
    from test_analyze import Stubs, URL

    Stubs(monkeypatch)
    seen = []
    real = analyze._produce

    async def spy(*a, **k):
        seen.append(analyze.active_requests)
        await real(*a, **k)

    monkeypatch.setattr(analyze, "_produce", spy)
    with TestClient(app).stream("GET", "/analyze", params={"url": URL, "profile": "nbfc", "lang": "en"}) as r:
        list(r.iter_lines())
    assert seen == [1] and analyze.active_requests == 0
    asyncio.run(analyze.run_analysis(URL, "nbfc", "en"))
    assert seen == [1, 1] and analyze.active_requests == 0


# ---------------------------------------------------------------- failures never stop the cycle

def test_rate_limit_is_retried_once_after_a_minute_then_skipped(fresh, monkeypatch):
    put("nbfc", notice(1), notice(2))
    calls = []

    async def fake(url):
        calls.append(url)
        if url.endswith("/1"):
            raise LLMError("rate_limit", "busy")
        analyze._stage1[url] = object()
        return True

    monkeypatch.setattr(analyze, "warm_stage1", fake)
    assert asyncio.run(warmer.run_cycle()) == 1
    assert [c[-1] for c in calls] == ["1", "1", "2"]  # item 1 tried twice, then the cycle moved on
    assert warmer.RATE_LIMIT_BACKOFF_S in fresh.sleeps


@pytest.mark.parametrize("error", [FetchFailed("page down", "https://www.rbi.org.in/1"), LLMError("unavailable", "x"), RuntimeError("bug")])
def test_any_other_failure_skips_that_item_and_never_raises(fresh, monkeypatch, error):
    put("nbfc", notice(1), notice(2))

    async def fake(url):
        if url.endswith("/1"):
            raise error
        analyze._stage1[url] = object()
        return True

    monkeypatch.setattr(analyze, "warm_stage1", fake)
    assert asyncio.run(warmer.run_cycle()) == 1


def test_a_cycle_with_nothing_cached_asks_for_the_notices_first(fresh, monkeypatch):
    asked = []

    async def fake_warm_cache():
        asked.append(True)
        put("nbfc", notice(1))
        return 5

    async def fake(url):
        analyze._stage1[url] = object()
        return True

    monkeypatch.setattr(routes_notices, "warm_cache", fake_warm_cache)
    monkeypatch.setattr(analyze, "warm_stage1", fake)
    assert asyncio.run(warmer.run_cycle()) == 1 and asked == [True]


def test_start_delay_then_cycle_then_every_half_hour(fresh, monkeypatch):
    cycles = []

    async def fake_cycle():
        cycles.append(len(fresh.sleeps))
        if len(cycles) == 2:
            raise asyncio.CancelledError
        return 0

    monkeypatch.setattr(warmer, "run_cycle", fake_cycle)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(warmer.keep_warm())
    assert fresh.sleeps == [60, 1800] and cycles == [1, 2]

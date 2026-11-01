"""Background pre-analysis for the free Groq tier (8,000 tokens/min PER MODEL).

After startup and then every 30 minutes, this week's "yes"/"review" notices (any profile) are analysed up front, one at a
time, so a visitor opening one finds fetch + extract + verify + retry already in the cache. It only does the
profile-independent part (analyze.warm_stage1); applicability and the explainer are per profile/language and cheap.

Two rules keep it from hurting real users:
  * pacing: the next document starts only when the tokens used in the last 60 s (from llm.usage_log) plus the cost of
    one document fit inside 75 % of the per-minute limit; the LLM client itself still honours retry-after;
  * priority: nothing starts while any /analyze or /ics request is running (analyze.active_requests > 0).
A document already in flight is never cancelled (that would waste its tokens)."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import get_args

from api import analyze, routes_notices
from api.schemas import Notice, ProfileId
from llm import usage_log
from llm.errors import LLMError

log = logging.getLogger("pramaan.warmer")

MAX_ITEMS = 12
START_DELAY_S = 60
EVERY_S = 30 * 60
TOKENS_PER_MIN = 8000
BUDGET = int(TOKENS_PER_MIN * 0.75)
WINDOW_S = 60.0
DEFAULT_COST = 4000  # tokens one document costs until we have measured one
IDLE_POLL_S = 2.0
MAX_BUDGET_SLEEP_S = 15.0
RATE_LIMIT_BACKOFF_S = 60.0
APPLIES = ("yes", "review")


@dataclass
class WarmState:
    running: bool = False
    queued: int = 0
    last_run_at: datetime | None = None
    last_cost: int = DEFAULT_COST


state = WarmState()


async def _sleep(seconds: float) -> None:  # replaced in tests
    await asyncio.sleep(seconds)


def _now() -> datetime:  # replaced in tests
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- what to analyse

def candidates() -> list[Notice]:
    """This week's yes/review notices for any profile (from the cached /notices answers), RBI/SEBI newest first, then PIB;
    at most MAX_ITEMS; those already cached are dropped. Reads caches only, no network."""
    seen: dict[str, Notice] = {}
    for profile in get_args(ProfileId):
        response = routes_notices._cache.get(profile)
        for n in (response.items if response else []):
            if n.applies in APPLIES:
                seen.setdefault(n.url, n)

    def key(n: Notice):
        # PIB press releases only fill what is left; undated items (PIB) keep feed order, newest dated first
        return (n.source == "pib", -date.fromisoformat(n.date).toordinal() if n.date else 0)

    ordered = sorted(seen.values(), key=key)[:MAX_ITEMS]
    return [n for n in ordered if not analyze.is_cached(n.url)]


# ---------------------------------------------------------------- pacing and priority

def _window_tokens(since: datetime) -> int:
    """Tokens used since `since`; the largest per-model total, because every model has its own per-minute limit."""
    per_model: dict[str, int] = {}
    for r in usage_log.recent(500):
        if datetime.fromisoformat(r["at"]) >= since:
            per_model[r.get("model_used", "")] = per_model.get(r.get("model_used", ""), 0) + r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)
    return max(per_model.values(), default=0)


def _oldest_in_window(since: datetime) -> datetime | None:
    times = [datetime.fromisoformat(r["at"]) for r in usage_log.recent(500)]
    return min((t for t in times if t >= since), default=None)


async def wait_for_budget() -> None:
    """Return when one more document fits under the per-minute budget."""
    cost = min(state.last_cost, BUDGET - 1)
    while True:
        since = _now().timestamp() - WINDOW_S
        since_dt = datetime.fromtimestamp(since, timezone.utc)
        if _window_tokens(since_dt) + cost <= BUDGET:
            return
        oldest = _oldest_in_window(since_dt)
        wait = (oldest.timestamp() + WINDOW_S - _now().timestamp() + 1) if oldest else 2.0
        await _sleep(min(max(wait, 2.0), MAX_BUDGET_SLEEP_S))


async def wait_until_idle() -> None:
    while analyze.active_requests > 0:
        await _sleep(IDLE_POLL_S)


# ---------------------------------------------------------------- one cycle

async def _warm_one(url: str) -> bool:
    """True if it is now cached. A rate limit is retried once after a minute; anything else is logged and skipped."""
    for attempt in range(2):
        try:
            await analyze.warm_stage1(url)
            return True
        except LLMError as e:
            if e.kind == "rate_limit" and attempt == 0:
                log.info("warmer: rate limited on %s, waiting %ds", url, RATE_LIMIT_BACKOFF_S)
                await _sleep(RATE_LIMIT_BACKOFF_S)
                await wait_until_idle()
                continue
            log.warning("warmer: skipped %s (%s)", url, e.kind)
            return False
        except asyncio.CancelledError:
            raise
        except Exception as e:  # DocumentError (page unreadable) or anything unexpected: never stop the cycle
            log.warning("warmer: skipped %s (%s)", url, type(e).__name__)
            return False
    return False


async def run_cycle() -> int:
    """Analyse the pending candidates one at a time. Returns how many were newly cached. Never raises."""
    state.running = True
    done = 0
    try:
        if not any(routes_notices._cache.get(p) for p in get_args(ProfileId)):
            await routes_notices.warm_cache()  # the /notices lists are what we pick from
        items = candidates()
        for i, notice in enumerate(items):
            state.queued = len(items) - i
            await wait_until_idle()
            await wait_for_budget()
            await wait_until_idle()
            if analyze.is_cached(notice.url):  # a visitor opened it while we waited
                continue
            started = _now()
            if await _warm_one(notice.url):
                done += 1
                spent = _window_tokens(started)
                if spent:
                    state.last_cost = spent  # measured cost of one document, used for the next pacing decision
        log.info("warmer: cycle done, %d newly cached, %d in cache", done, analyze.cached_count())
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("warmer: cycle failed")
    finally:
        state.running, state.queued, state.last_run_at = False, 0, _now()
    return done


async def keep_warm() -> None:
    """The background task started from the app's lifespan."""
    await _sleep(START_DELAY_S)
    while True:
        await run_cycle()
        await _sleep(EVERY_S)

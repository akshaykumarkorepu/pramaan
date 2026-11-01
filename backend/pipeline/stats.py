"""Live proof stats, in memory only: how well the verifier is doing on the notices this server has really analysed.

Everything is kept per URL, so analysing the same notice again (cache expiry, a visitor after the warmer) replaces its
numbers instead of counting it twice. Nothing is labelled by hand: the counts come straight from verify()'s statuses.
After a restart the numbers start from zero and the background warmer refills them."""
from datetime import datetime, timezone
from typing import Iterable, Optional

from sources.allowlist import source_of

SOURCES = ("rbi", "sebi", "pib")
STATUSES = ("verified", "near", "fixed", "rejected")

started_at: datetime = datetime.now(timezone.utc)
_analysed: dict[str, dict] = {}   # url -> {source, extracted, verified, near, fixed, rejected, fresh_ms}
_injected: dict[str, bool] = {}   # url -> did the verifier reject the fake claim (latest test)
_cached_ms: dict[str, int] = {}   # url -> latest time to serve it from the cache


def reset() -> None:
    global started_at
    started_at = datetime.now(timezone.utc)
    _analysed.clear()
    _injected.clear()
    _cached_ms.clear()


def record_analysis(url: str, obligations: Iterable, fresh_ms: int) -> None:
    """A document finished fetch -> extract -> verify -> retry. `obligations` is the final list, rejected ones included."""
    counts = {s: 0 for s in STATUSES}
    items = [o for o in obligations if not getattr(o, "injected_test", False)]
    for o in items:
        if o.status in counts:
            counts[o.status] += 1
    _analysed[url] = {"source": source_of(url), "extracted": len(items), "fresh_ms": fresh_ms, **counts}


def record_injected(url: str, status: str) -> None:
    """The verifier test ran on this document: caught = the verifier rejected the fake claim."""
    _injected[url] = status == "rejected"


def record_cached(url: str, ms: int) -> None:
    _cached_ms[url] = ms


def _avg(values: list[int]) -> Optional[int]:
    return round(sum(values) / len(values)) if values else None


def _block(urls: list[str]) -> dict:
    rows = [_analysed[u] for u in urls if u in _analysed]
    tests = [_injected[u] for u in urls if u in _injected]
    return {
        "circulars_analysed": len(rows),
        "duties_extracted": sum(r["extracted"] for r in rows),
        **{s: sum(r[s] for r in rows) for s in STATUSES},
        "injected_tests_run": len(tests),
        "injected_tests_caught": sum(tests),
        "avg_latency_ms_fresh": _avg([r["fresh_ms"] for r in rows]),
        "avg_latency_ms_cached": _avg([_cached_ms[u] for u in urls if u in _cached_ms]),
    }


def snapshot() -> dict:
    # a fake-claim test can run on a URL that was never fully analysed (it failed later), so count tests over every URL seen
    urls = list(_analysed.keys() | _injected.keys() | _cached_ms.keys())
    return {
        "started_at": started_at.isoformat().replace("+00:00", "Z"),
        **_block(urls),
        "by_source": {s: _block([u for u in urls if (_analysed.get(u, {}).get("source") or source_of(u)) == s]) for s in SOURCES},
    }

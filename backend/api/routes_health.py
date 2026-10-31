import asyncio
import importlib
import logging

from fastapi import APIRouter

from api.schemas import HealthResponse, RuntimeHealth, SourceHealth
from llm import health as llm_health
from sources.cache import StatusCache
from sources.feeds import FEEDS, LABELS, fetch_feed, newest
from sources.http import FetchError
from sources.pagecheck import check_page

log = logging.getLogger("pramaan.health")
router = APIRouter()
_cache = StatusCache(ok_ttl=300, fail_ttl=30)


async def _check_source(source: str) -> SourceHealth:
    cached = _cache.get(source)
    if cached:
        return cached
    label = LABELS[source]
    try:
        feed = await fetch_feed(source)
        if not feed.ok:
            result = SourceHealth(ok=False, last_fetch=feed.fetched_at, count=len(feed.items), error=feed.error)
        else:
            # A feed that loads but whose pages are blocked would still break the app, so fetch the newest page too.
            top = newest(feed.items)
            try:
                await check_page(top.url, label)
                result = SourceHealth(ok=True, last_fetch=feed.fetched_at, count=len(feed.items))
            except FetchError as e:
                result = SourceHealth(
                    ok=False, last_fetch=feed.fetched_at, count=len(feed.items),
                    error=f"{label} feed OK but newest page failed: {e}",
                )
    except Exception:  # /health must never 500 or leak a traceback
        log.exception("health check for %s crashed", source)
        result = SourceHealth(ok=False, error=f"{label} check failed unexpectedly")
    _cache.put(source, result, result.ok)
    return result


RUNTIME_MODULES = ("pipeline.fetch_document", "verify.verifier")  # pdfplumber/selectolax, rapidfuzz/dateparser


def _check_runtime() -> RuntimeHealth:
    """Import (not run) the pipeline modules so a broken dependency shows up here instead of on the first request."""
    try:
        for name in RUNTIME_MODULES:
            importlib.import_module(name)
        return RuntimeHealth(ok=True)
    except Exception as e:
        log.exception("runtime import check failed")
        return RuntimeHealth(ok=False, error=f"{type(e).__name__}: {e}"[:200])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    sources = list(FEEDS)
    *checks, llm = await asyncio.gather(*(_check_source(s) for s in sources), llm_health.ping())
    return HealthResponse(sources=dict(zip(sources, checks)), llm=llm, runtime=_check_runtime())

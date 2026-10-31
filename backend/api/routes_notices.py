"""GET /notices: the newest items from the RBI, SEBI (circulars) and PIB feeds, each with a rules-only applicability badge.

No LLM here at all (zero Groq tokens): applicability comes from pipeline.applicability.check_applicability_rules.
When the rules are unsure the badge is "review"; open the notice to get the full AI-checked answer."""
import asyncio
import hashlib
import logging
from datetime import date, datetime, timezone
from typing import get_args

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.schemas import Applicability, Notice, NoticeSource, NoticesResponse, ProfileId
from pipeline.applicability import check_applicability_rules
from pipeline.fetch_document import fetch_document
from sources.cache import StatusCache
from sources.errors import DocumentError
from sources.feeds import FEEDS, FeedItem, FeedResult, fetch_feed, newest_n

log = logging.getLogger("pramaan.notices")
router = APIRouter()

PER_SOURCE = 8
CONCURRENCY = 6  # document fetches in flight
ITEM_TIMEOUT_S = 25.0  # one slow PDF must not hold up the whole list
ORDER = {"yes": 0, "review": 1, "no": 2}

# 10 min per profile; a response with a source down is kept only 1 min so recovery shows up quickly
_cache = StatusCache(ok_ttl=600, fail_ttl=60, maxsize=16)


def clear_cache() -> None:
    _cache._ok.clear()
    _cache._fail.clear()


def notice_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


async def _applicability(item: FeedItem, profile: str, sem: asyncio.Semaphore) -> tuple[Applicability, datetime]:
    async with sem:
        try:
            doc = await asyncio.wait_for(fetch_document(item.url), ITEM_TIMEOUT_S)
        except (DocumentError, asyncio.TimeoutError):
            return Applicability(value="review", reason="couldn't read the document yet"), datetime.now(timezone.utc)
        except Exception:  # one bad item must never take the list down
            log.exception("notices: unexpected failure for %s", item.url)
            return Applicability(value="review", reason="couldn't read the document yet"), datetime.now(timezone.utc)
    return check_applicability_rules(profile, doc), doc.fetched_at


def _sort_key(n: Notice):
    # stable sort: undated items (PIB) keep feed order, which is newest first
    return (ORDER[n.applies], -(date.fromisoformat(n.date).toordinal()) if n.date else 0)


async def _build(profile: str) -> NoticesResponse:
    feeds: list[FeedResult] = await asyncio.gather(*(fetch_feed(s) for s in FEEDS))
    sources: dict[str, NoticeSource] = {}
    picked: list[FeedItem] = []
    for f in feeds:
        top = newest_n(f.items, PER_SOURCE) if f.ok else []
        sources[f.source] = NoticeSource(ok=f.ok, error=f.error, count=len(top))
        picked += top

    sem = asyncio.Semaphore(CONCURRENCY)
    checked = await asyncio.gather(*(_applicability(i, profile, sem) for i in picked))
    items = [
        Notice(
            id=notice_id(i.url), source=i.source, title=i.title, url=i.url,  # type: ignore[arg-type]
            date=i.date.isoformat() if i.date else None, fetched_at=fetched_at, applies=a.value, reason=a.reason,
        )
        for i, (a, fetched_at) in zip(picked, checked)
    ]
    items.sort(key=_sort_key)
    return NoticesResponse(items=items, sources=sources)  # type: ignore[arg-type]


@router.get("/notices", response_model=NoticesResponse)
async def notices(profile: str = "", lang: str = "en"):
    if profile not in get_args(ProfileId):
        return JSONResponse({"error": "Choose who you are (NBFC, co-operative bank, research analyst, stock broker or citizen/MSME) first."}, status_code=400)
    if lang not in ("en", "te", "hi"):
        return JSONResponse({"error": "Choose English, Telugu or Hindi."}, status_code=400)
    hit = _cache.get(profile)
    if hit:
        return hit
    try:
        result = await _build(profile)
    except Exception:
        log.exception("notices failed")
        return JSONResponse({"error": "Couldn't load the notice list. Please try again."}, status_code=503)
    _cache.put(profile, result, all(s.ok for s in result.sources.values()))
    return result

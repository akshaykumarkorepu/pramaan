"""Live RSS feeds for RBI, SEBI and PIB (English)."""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import dateparser
import feedparser

from sources.http import FetchError, get

# PIB: without &reg=3 the server 302-redirects every Lang value to the Hindi feed.
FEEDS = {
    "rbi": "https://www.rbi.org.in/notifications_rss.xml",
    "sebi": "https://www.sebi.gov.in/sebirss.xml",
    "pib": "https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3&reg=3",
}
LABELS = {"rbi": "RBI", "sebi": "SEBI", "pib": "PIB"}


@dataclass
class FeedItem:
    source: str
    title: str
    url: str
    date: date | None  # PIB items carry no date
    summary: str = ""


@dataclass
class FeedResult:
    source: str
    ok: bool
    items: list[FeedItem] = field(default_factory=list)
    fetched_at: datetime | None = None
    error: str | None = None


def is_sebi_circular(url: str) -> bool:
    # The SEBI feed also carries enforcement orders, recovery notices and press releases.
    return "/legal/circulars/" in url


def _item_date(entry) -> date | None:
    parsed = entry.get("published_parsed")
    if parsed:
        return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
    raw = entry.get("published")
    if raw:
        # SEBI writes "30 Oct, 2026 ..." which feedparser can't read
        dt = dateparser.parse(raw, settings={"DATE_ORDER": "DMY"})
        if dt:
            return dt.date()
    return None


def parse_feed(source: str, content: bytes) -> list[FeedItem]:
    """Parse raw RSS bytes. Garbage input yields an empty list rather than an exception."""
    items = []
    for e in feedparser.parse(content).entries:
        url = (e.get("link") or "").strip()
        title = (e.get("title") or "").strip()
        if not url or not title:
            continue
        if source == "sebi" and not is_sebi_circular(url):
            continue
        items.append(FeedItem(source, title, url, _item_date(e), e.get("summary", "")))
    return items


def newest(items: list[FeedItem]) -> FeedItem | None:
    """Newest by date; undated items (PIB) keep feed order, which is newest-first."""
    if not items:
        return None
    dated = [i for i in items if i.date]
    return max(dated, key=lambda i: i.date) if dated else items[0]


async def fetch_feed(source: str) -> FeedResult:
    try:
        resp = await get(FEEDS[source], LABELS[source])
    except FetchError as e:
        return FeedResult(source, False, error=str(e))
    items = parse_feed(source, resp.content)
    fetched_at = datetime.now(timezone.utc)
    if not items:
        return FeedResult(source, False, [], fetched_at, f"{LABELS[source]} feed loaded but had no usable items")
    return FeedResult(source, True, items, fetched_at)

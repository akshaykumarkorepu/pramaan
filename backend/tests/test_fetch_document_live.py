"""Live checks against the real sites. Skipped automatically when the feeds can't be reached.

Whether the single newest notice is long depends on what the regulator published that day, so each
test fetches the newest few items from the live feed and checks the longest one."""
import asyncio
from datetime import date

import pytest

from pipeline.fetch_document import FetchedDocument, fetch_document
from sources.errors import DocumentError
from sources.feeds import fetch_feed

pytestmark = pytest.mark.live

NEWEST_N = 5


async def _longest_of_newest(source: str) -> tuple[FetchedDocument, int]:
    feed = await fetch_feed(source)
    if not feed.ok:
        pytest.skip(f"{source} feed unreachable: {feed.error}")
    # newest first by date; ties (and undated items) keep feed order, which is newest-first
    items = sorted(feed.items, key=lambda i: i.date or date.min, reverse=True)[:NEWEST_N]
    results = await asyncio.gather(*(fetch_document(i.url) for i in items), return_exceptions=True)
    docs = [r for r in results if isinstance(r, FetchedDocument)]
    errors = [f"{i.url}: {r}" for i, r in zip(items, results) if isinstance(r, DocumentError)]
    unexpected = [r for r in results if isinstance(r, Exception) and not isinstance(r, DocumentError)]
    assert not unexpected, f"unexpected exception type: {unexpected[0]!r}"  # only typed errors are acceptable
    assert docs, f"none of the newest {len(items)} {source} items could be read: {errors}"
    return max(docs, key=lambda d: d.char_count), len(items)


@pytest.mark.parametrize("source", ["rbi", "sebi"])
def test_longest_of_newest_items_gives_real_text(source):
    doc, n = asyncio.run(_longest_of_newest(source))  # URLs come from the live feed, never hardcoded
    assert doc.source == source
    assert doc.char_count > 1000, f"longest of newest {n} {source} items had only {doc.char_count} chars"
    assert len(doc.paragraphs) > 3
    assert doc.title


def test_sebi_text_comes_from_the_pdf():
    doc, _ = asyncio.run(_longest_of_newest("sebi"))
    assert doc.pdf_url and doc.pdf_url.lower().endswith(".pdf")

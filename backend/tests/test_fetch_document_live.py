"""Live checks against the real sites. Skipped automatically when the feeds can't be reached."""
import asyncio

import pytest

from pipeline.fetch_document import fetch_document
from sources.feeds import fetch_feed, newest

pytestmark = pytest.mark.live


def newest_url(source: str) -> str:
    feed = asyncio.run(fetch_feed(source))
    if not feed.ok:
        pytest.skip(f"{source} feed unreachable: {feed.error}")
    return newest(feed.items).url


@pytest.mark.parametrize("source", ["rbi", "sebi"])
def test_newest_item_gives_real_text(source):
    url = newest_url(source)  # taken from the live feed, never hardcoded
    doc = asyncio.run(fetch_document(url))
    assert doc.source == source
    assert doc.char_count > 1000, f"{url} gave only {doc.char_count} chars"
    assert len(doc.paragraphs) > 3
    assert doc.title


def test_sebi_text_comes_from_the_pdf():
    doc = asyncio.run(fetch_document(newest_url("sebi")))
    assert doc.pdf_url and doc.pdf_url.lower().endswith(".pdf")

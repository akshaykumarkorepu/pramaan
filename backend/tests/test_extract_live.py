"""Live extraction against the real feeds and Groq. Skipped without GROQ_API_KEY or when the feed is unreachable."""
import asyncio
import os

import pytest

import config
from pipeline.extract import extract
from pipeline.fetch_document import FetchedDocument, fetch_document
from sources.errors import DocumentError
from sources.feeds import fetch_feed, newest_n

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def live_env():
    config.load_env()
    if not (os.environ.get("GROQ_API_KEY") and os.environ.get("GROQ_MODEL_PRIMARY")):
        pytest.skip("GROQ_API_KEY / GROQ_MODEL_PRIMARY not set")


async def _longest_of_newest_rbi(n=5) -> FetchedDocument:
    feed = await fetch_feed("rbi")
    if not feed.ok:
        pytest.skip(f"rbi feed unreachable: {feed.error}")
    results = await asyncio.gather(*(fetch_document(i.url) for i in newest_n(feed.items, n)), return_exceptions=True)
    docs = [r for r in results if isinstance(r, FetchedDocument)]
    assert docs, f"none of the newest {n} RBI items could be read: {[str(r) for r in results if isinstance(r, DocumentError)]}"
    return max(docs, key=lambda d: d.char_count)


def test_longest_of_newest_rbi_items_yields_obligations_with_quotes():
    doc = asyncio.run(_longest_of_newest_rbi())
    result, meta = asyncio.run(extract(doc))
    assert result.kind == "obligations", f"{doc.title!r} came back {result.kind}"
    assert len(result.obligations) >= 1
    assert any(o.quote.strip() for o in result.obligations)
    assert meta.attempts >= 1
    # under Groq's rate limits the client correctly falls back to the FAST model, so either model is fine
    allowed = {os.environ["GROQ_MODEL_PRIMARY"], os.environ.get("GROQ_MODEL_FAST")} - {None}
    assert meta.model_used in allowed

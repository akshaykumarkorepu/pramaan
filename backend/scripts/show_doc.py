"""M2 check: newest RBI, SEBI and PIB items FROM THE LIVE FEEDS -> fetch_document -> print what we got.
Run from backend/:  python scripts/show_doc.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.fetch_document import fetch_document  # noqa: E402
from sources.errors import DocumentError  # noqa: E402
from sources.feeds import FEEDS, LABELS, fetch_feed, newest  # noqa: E402


async def main() -> int:
    failed = False
    for source in FEEDS:
        label = LABELS[source]
        feed = await fetch_feed(source)
        if not feed.ok:
            failed = True
            print(f"=== [{label}] feed failed: {feed.error}\n")
            continue
        item = newest(feed.items)
        print(f"=== [{label}] {item.url}")
        try:
            doc = await fetch_document(item.url)
        except DocumentError as e:
            failed = True
            print(f"FAILED ({e.kind}): {e}\n")
            continue
        print(f"title: {doc.title}")
        print(f"char_count: {doc.char_count}   paragraphs: {len(doc.paragraphs)}   pdf_url: {doc.pdf_url}")
        for p in doc.paragraphs[:3]:
            text = p.text if len(p.text) <= 400 else p.text[:400] + " ..."
            print(f"  [{p.id}] {text}")
        print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

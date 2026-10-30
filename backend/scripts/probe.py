"""M1 live probe. Fetches the three feeds, then the newest RBI and SEBI pages taken FROM those feeds.
Run from backend/:  python scripts/probe.py"""
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources.feeds import FEEDS, LABELS, fetch_feed, newest  # noqa: E402
from sources.http import FetchError  # noqa: E402
from sources.pagecheck import check_page  # noqa: E402


async def main() -> int:
    feeds = await asyncio.gather(*(fetch_feed(s) for s in FEEDS))
    failed = False
    for f in feeds:
        label = LABELS[f.source]
        if not f.ok:
            failed = True
            print(f"[{label}] FAILED: {f.error}")
            continue
        top = newest(f.items)
        print(f"[{label}] ok, {len(f.items)} items, newest date: {top.date or 'not in feed'}")
        for item in f.items[:3]:
            print(f"    - {item.title}")

    print("\nPages (newest item taken from each feed):")
    for f in feeds:
        if not f.ok:
            continue
        top = newest(f.items)
        label = LABELS[f.source]
        try:
            page = await check_page(top.url, label)
        except FetchError as e:
            failed = True
            print(f"[{label}] page FAILED: {e}\n    {top.url}")
            continue
        pdf = f"yes ({urlparse(page.pdf_url).netloc})" if page.pdf_url else "no"
        print(f"[{label}] HTTP {page.status}, body text {page.body_text_len} chars, PDF link: {pdf}\n    {top.url}")
        if page.pdf_url:
            print(f"    PDF: {page.pdf_url}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

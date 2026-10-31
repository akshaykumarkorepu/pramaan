"""M7 check: newest 3 RBI + 2 SEBI + 2 PIB items FROM THE LIVE FEEDS -> fetch -> extract -> verify -> applicability
for all five profiles. Prints a table (cell = value (rule|llm|-)), then the reasons for every "review".
Everything runs one step at a time (Groq rate limits).
Run from backend/:  python scripts/applies_demo.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

config.load_env()

from llm.errors import LLMError  # noqa: E402
from pipeline.applicability import OWN, check_applicability  # noqa: E402
from pipeline.extract import extract  # noqa: E402
from pipeline.fetch_document import fetch_document  # noqa: E402
from sources.errors import DocumentError  # noqa: E402
from sources.feeds import LABELS, fetch_feed, newest_n  # noqa: E402
from verify.verifier import verify  # noqa: E402

COUNTS = {"rbi": 3, "sebi": 2, "pib": 2}
PROFILES = list(OWN)


def short(text, n=150):
    return text if len(text) <= n else text[:n] + "..."


async def main() -> int:
    items = []
    for source, n in COUNTS.items():
        feed = await fetch_feed(source)
        if not feed.ok:
            print(f"[{LABELS[source]}] feed failed: {feed.error}")
            continue
        items += newest_n(feed.items, n)

    rows, reviews, failed = [], [], 0
    for item in items:
        label = f"[{LABELS[item.source]}] {short(item.title, 45)}"
        print(f"... {label}", flush=True)
        try:
            doc = await fetch_document(item.url)
            extraction, _ = await extract(doc)
        except (DocumentError, LLMError) as e:
            failed += 1
            print(f"    FAILED ({e.kind}): {e}", flush=True)
            continue
        verified, _ = verify(extraction.obligations, doc)
        cells = []
        for profile in PROFILES:  # sequential: each LLM call is small, but Groq limits are per minute
            result, meta = await check_applicability(profile, doc, extraction, verified)
            cells.append(f"{result.value} ({meta.method if meta.method != 'none' else '-'})")
            if result.value == "review":
                reviews.append((label, profile, result))
        rows.append((label, cells, extraction.kind))

    widths = [max(len(r[0]) for r in rows + [("document", [], "")])] + [max(len(p), 11) for p in PROFILES]
    print()
    print(" | ".join(h.ljust(w) for h, w in zip(["document", *PROFILES], widths)))
    print("-+-".join("-" * w for w in widths))
    for label, cells, _ in rows:
        print(" | ".join(c.ljust(w) for c, w in zip([label, *cells], widths)))
    if reviews:
        print("\nReasons for review:")
        for label, profile, r in reviews:
            print(f"  {label} / {profile}: {r.reason}")
    print(f"\n{len(rows)} documents checked, {failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

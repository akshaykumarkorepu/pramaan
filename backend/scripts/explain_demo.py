"""M8 check: newest RBI item (profile coop_bank) and newest SEBI circular (profile research_analyst) FROM THE LIVE FEEDS
-> fetch -> extract -> verify -> retry -> applicability -> explainer in te, hi and en. Prints each explainer with its
source (llm|template) and word count. Everything runs one step at a time (Groq rate limits).
Run from backend/:  python scripts/explain_demo.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

config.load_env()

from llm.errors import LLMError  # noqa: E402
from pipeline.applicability import check_applicability  # noqa: E402
from pipeline.explain import explain  # noqa: E402
from pipeline.extract import extract  # noqa: E402
from pipeline.fetch_document import fetch_document  # noqa: E402
from pipeline.retry import retry  # noqa: E402
from sources.errors import DocumentError  # noqa: E402
from sources.feeds import LABELS, fetch_feed, newest_n  # noqa: E402
from verify.verifier import verify  # noqa: E402

TARGETS = [("rbi", "coop_bank"), ("sebi", "research_analyst")]
LANGS = ["te", "hi", "en"]


async def main() -> int:
    failed = 0
    for source, profile in TARGETS:
        feed = await fetch_feed(source)
        if not feed.ok or not feed.items:
            failed += 1
            print(f"[{LABELS[source]}] feed failed: {feed.error}\n")
            continue
        item = newest_n(feed.items, 1)[0]
        print("=" * 100)
        print(f"[{LABELS[source]}] {item.title}\n{item.url}\nprofile: {profile}", flush=True)
        try:
            doc = await fetch_document(item.url)
            extraction, _ = await extract(doc)
            verified, _ = verify(extraction.obligations, doc)
            final, counts, _ = await retry(verified, doc)
            applies, _ = await check_applicability(profile, doc, extraction, final)
        except (DocumentError, LLMError) as e:
            failed += 1
            print(f"FAILED ({e.kind}): {e}\n")
            continue
        print(f"obligations: verified {counts.verified} / near {counts.near} / fixed {counts.fixed} / rejected {counts.rejected}")
        print(f"applies: {applies.value} - {applies.reason}\n", flush=True)
        for lang in LANGS:  # sequential
            out, meta = await explain(doc.title, final, applies, profile, lang)
            print(f"--- {lang} | source={out.source} | {len(out.text.split())} words | {meta.model or '-'} "
                  f"{meta.latency_ms} ms, calls={meta.llm_calls}, regenerated={meta.regenerated}"
                  + (f" | template because: {meta.reason}" if meta.reason else ""))
            print(out.text + "\n", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

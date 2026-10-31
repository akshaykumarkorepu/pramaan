"""M4 check: newest 3 RBI + newest 3 SEBI items FROM THE LIVE FEEDS -> fetch_document -> extract -> print.

The "quote found in source" line is only a plain normalized substring check. The real verifier is M5.
Run from backend/:  python scripts/extract_demo.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

config.load_env()

from llm.errors import LLMError  # noqa: E402
from pipeline.extract import extract  # noqa: E402
from pipeline.fetch_document import fetch_document  # noqa: E402
from sources.errors import DocumentError  # noqa: E402
from sources.feeds import LABELS, fetch_feed, newest_n  # noqa: E402
from verify.normalize import normalize  # noqa: E402

PER_SOURCE = 3


async def run_one(url: str):
    """Returns (doc, result, meta) or the typed error. Never raises for expected failures."""
    try:
        doc = await fetch_document(url)
        result, meta = await extract(doc)
        return doc, result, meta
    except (DocumentError, LLMError) as e:
        return e


async def main() -> int:
    items = []
    for source in ("rbi", "sebi"):
        feed = await fetch_feed(source)
        if not feed.ok:
            print(f"[{LABELS[source]}] feed failed: {feed.error}\n")
            continue
        items += newest_n(feed.items, PER_SOURCE)

    # One document at a time: Groq's free tier allows ~8000 tokens/min per model, so a concurrent burst gets rate limited.
    # The client waits out 429s (up to 30 s each), so this can take a minute or two.
    found_total = quotes_total = 0
    outcomes = []
    for item in items:
        print("=" * 100, flush=True)
        print(f"[{LABELS[item.source]}] {item.title}\n{item.url}", flush=True)
        outcome = await run_one(item.url)
        outcomes.append(outcome)
        if isinstance(outcome, Exception):
            print(f"FAILED ({outcome.kind}): {outcome}\n")
            continue
        doc, result, meta = outcome
        print(f"doc: {doc.char_count} chars, {len(doc.paragraphs)} paragraphs")
        print(f"kind: {result.kind}   obligations: {len(result.obligations)}")
        print(f"addressees: {'; '.join(result.addressees) or '(none)'}")
        print(
            f"llm: {meta.model_used}  {meta.latency_ms} ms  tokens {meta.prompt_tokens}+{meta.completion_tokens}"
            f"  attempts {meta.attempts}  fallback {meta.fallback_used}"
        )
        source_text = normalize(doc.full_text)
        found = 0
        for n, o in enumerate(result.obligations, 1):
            ok = bool(o.quote.strip()) and normalize(o.quote) in source_text
            found += ok
            print(f"\n  {n}. who: {o.who}")
            print(f"     must_do: {o.must_do}")
            print(f"     deadline: {o.deadline}   effective_from: {o.effective_from}   paragraph: {o.paragraph}")
            if o.penalty_or_consequence:
                print(f"     penalty_or_consequence: {o.penalty_or_consequence}")
            print(f'     quote: "{o.quote}"')
            print(f"     quote found in source: {'yes' if ok else 'NO'}")
        found_total += found
        quotes_total += len(result.obligations)
        print(f"\n  quotes found in this document: {found} of {len(result.obligations)}\n")

    print("=" * 100)
    print(f"TOTAL quotes found in source: {found_total} of {quotes_total}")
    failed = any(isinstance(o, Exception) for o in outcomes)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

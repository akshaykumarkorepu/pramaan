"""M6 check: newest 2 RBI + newest 2 SEBI items FROM THE LIVE FEEDS -> fetch -> extract -> verify -> retry.

One clearly labelled TEST fake (fabricated quote and deadline) is added to each document before the retry, to show it
is never retried and stays rejected. Documents run one at a time (Groq rate limits).
Run from backend/:  python scripts/retry_demo.py"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

config.load_env()

from llm.errors import LLMError  # noqa: E402
from pipeline.extract import extract  # noqa: E402
from pipeline.fetch_document import fetch_document  # noqa: E402
from pipeline.retry import retry  # noqa: E402
from sources.errors import DocumentError  # noqa: E402
from sources.feeds import LABELS, fetch_feed, newest_n  # noqa: E402
from verify.verifier import InjectedObligation, verify  # noqa: E402

PER_SOURCE = 2

FAKE = InjectedObligation(
    who="TEST ONLY - fabricated claim",
    must_do="TEST ONLY: pay a Rs. 25 lakh fee by 1 December 2026.",
    deadline="2026-12-01",
    effective_from=None,
    paragraph="1",
    quote="TEST ONLY: all regulated entities shall pay a one-time fee of Rs. 25 lakh to the regulator by December 1, 2026.",
    penalty_or_consequence=None,
)


def fmt(c) -> str:
    return f"verified {c.verified} / near {c.near} / rejected {c.rejected} / fixed {c.fixed}"


def tally(items):
    from pipeline.retry import RetryCounts
    return RetryCounts(**{s: sum(o.status == s for o in items) for s in ("verified", "near", "rejected", "fixed")})


def short(text, n=150):
    return text if len(text) <= n else text[:n] + "..."


async def main() -> int:
    items = []
    for source in ("rbi", "sebi"):
        feed = await fetch_feed(source)
        if not feed.ok:
            print(f"[{LABELS[source]}] feed failed: {feed.error}\n")
            continue
        items += newest_n(feed.items, PER_SOURCE)

    bad = False
    for item in items:
        print("=" * 100, flush=True)
        print(f"[{LABELS[item.source]}] {item.title}\n{item.url}", flush=True)
        try:
            doc = await fetch_document(item.url)
            result, _ = await extract(doc)
        except (DocumentError, LLMError) as e:
            bad = True
            print(f"FAILED ({e.kind}): {e}\n")
            continue

        before, _ = verify([*result.obligations, FAKE], doc)
        final, _, meta = await retry(before, doc)
        real_before = [o for o in before if not o.injected_test]
        real_after = [o for o in final if not o.injected_test]
        print(f"doc: {len(doc.paragraphs)} paragraphs | extracted {len(real_before)} real obligations")
        print(f"BEFORE: {fmt(tally(real_before))}")
        print(f"AFTER:  {fmt(tally(real_after))}")
        print(f"retry: llm_calls={meta.llm_calls} model={meta.model} {meta.latency_ms} ms, "
              f"{meta.prompt_tokens}+{meta.completion_tokens} tokens | sent {meta.rejected_sent} rejected + "
              f"{meta.quality_sent} quality | fixed {meta.fixed}, rewritten {meta.rewritten}, dropped {len(meta.dropped)}"
              f"{' | note: ' + meta.note if meta.note else ''}")

        # `before` and `final` line up except for dropped items, so match on the original quote
        after_by_quote = {}
        for o in final:
            after_by_quote.setdefault(o.quote, []).append(o)
        for o in real_before:
            new = next((c for c in after_by_quote.get(o.quote, []) if c.status != o.status or c.reason != o.reason), None)
            fixed_in_place = next((c for c in final if c.status == "fixed" and (c.reason or "").endswith(o.reason or "?") and c.quote != o.quote), None) if o.status == "rejected" else None
            if new:
                print(f"  CHANGED: {o.status} ({o.reason or '-'}) -> {new.status} ({new.reason or '-'})")
                print(f"     quote: \"{short(new.quote)}\"")
            elif fixed_in_place:
                print(f"  CHANGED: rejected ({o.reason}) -> fixed with a corrected quote")
                print(f"     old quote: \"{short(o.quote)}\"\n     new quote: \"{short(fixed_in_place.quote)}\"")
        for d in meta.dropped:
            print(f"  DROPPED: ({d.reason}) \"{short(d.quote)}\"")
        for o in real_before:
            for c in after_by_quote.get(o.quote, []):
                if c.must_do != o.must_do:
                    print(f"  REWRITTEN must_do:\n     old: {o.must_do}\n     new: {c.must_do}")

        fakes = [o for o in final if o.injected_test]
        ok = len(fakes) == 1 and fakes[0].status == "rejected" and fakes[0] == next(o for o in before if o.injected_test)
        print(f"TEST fake: {'stayed REJECTED and untouched' if ok else 'PROBLEM - changed or missing'} ({fakes[0].reason if fakes else '-'})")
        bad |= not ok or meta.llm_calls > 1
        print()

    print("=" * 100)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

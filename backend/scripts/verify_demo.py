"""M5 check: newest 2 RBI + newest 2 SEBI items FROM THE LIVE FEEDS -> fetch_document -> extract -> verify.

Then one clearly labelled TEST obligation (fabricated quote and fabricated deadline) is added to each document and
verified again, to show the guardrail rejects it. Documents run one at a time (Groq rate limits).
Run from backend/:  python scripts/verify_demo.py"""
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


def show(n, r):
    flag = "  [TEST - injected fake]" if r.injected_test else ""
    corrected = ""
    if r.paragraph_corrected:
        corrected = " (corrected)"
    print(f"  {n}. status: {r.status.upper()}{flag}")
    print(f"     reason: {r.reason or '-'}   score: {r.score}   paragraph: {r.paragraph}{corrected}")
    print(f"     must_do: {r.must_do}")
    print(f"     deadline: {r.deadline}   quote: \"{r.quote[:160]}{'...' if len(r.quote) > 160 else ''}\"")


async def main() -> int:
    items = []
    for source in ("rbi", "sebi"):
        feed = await fetch_feed(source)
        if not feed.ok:
            print(f"[{LABELS[source]}] feed failed: {feed.error}\n")
            continue
        items += newest_n(feed.items, PER_SOURCE)

    totals = {"verified": 0, "near": 0, "rejected": 0}
    fakes_total = fakes_rejected = 0
    failed = False
    for item in items:
        print("=" * 100, flush=True)
        print(f"[{LABELS[item.source]}] {item.title}\n{item.url}", flush=True)
        try:
            doc = await fetch_document(item.url)
            result, meta = await extract(doc)
        except (DocumentError, LLMError) as e:
            failed = True
            print(f"FAILED ({e.kind}): {e}\n")
            continue
        print(f"doc: {doc.char_count} chars, {len(doc.paragraphs)} paragraphs | extracted {len(result.obligations)} | "
              f"llm {meta.latency_ms} ms, attempts {meta.attempts}")

        verified, counts = verify(result.obligations, doc)
        print(f"\nREAL obligations -> verified {counts.verified} / near {counts.near} / rejected {counts.rejected}")
        for n, r in enumerate(verified, 1):
            show(n, r)
        for k in totals:
            totals[k] += getattr(counts, k)

        with_fake, _ = verify([*result.obligations, FAKE], doc)
        fake = with_fake[-1]
        print("\nINJECTED TEST (a fabricated quote with a fabricated deadline, added on purpose):")
        show(len(with_fake), fake)
        fakes_total += 1
        fakes_rejected += fake.status == "rejected"
        print()

    print("=" * 100)
    print(f"REAL totals: verified {totals['verified']} / near {totals['near']} / rejected {totals['rejected']}")
    print(f"injected fakes rejected: {fakes_rejected} of {fakes_total}")
    return 1 if failed or fakes_rejected != fakes_total else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""The guardrail. Pure code: no LLM, no network.

An obligation reaches the user as verified only if its quote is in the source (exact, or near at >= 92) and every
number and date it claims is in that source text. Anything else is kept and marked rejected with the reason."""
from typing import TYPE_CHECKING, Sequence

from pydantic import BaseModel

from api.schemas import MatchSpan, VerifiedObligation
from pipeline.models import ExtractedObligation
from verify.normalize import normalize, normalize_with_map
from verify.numbers import extract_facts, iso_date_facts, merge, missing_facts
from verify.quotes import find_quote, overlapping, paragraph_spans

if TYPE_CHECKING:  # typing only, so verify/ never imports the fetching stack
    from pipeline.fetch_document import FetchedDocument

MIN_QUOTE_CHARS = 30


class VerifyCounts(BaseModel):
    verified: int  # exact matches only; "near" is counted separately
    near: int
    rejected: int


class InjectedObligation(ExtractedObligation):
    """The deliberately fake claim of verifier_test=1. Not part of the LLM schema; verify() just carries the flag."""
    injected_test: bool = True


def _paragraph(spans, start: int, end: int, claimed: str | None):
    """(paragraph id, corrected?, MatchSpan) for a match at [start, end) in full_text."""
    if spans is None:
        return claimed, False, None
    hit = overlapping(spans, start, end)
    if not hit:
        return claimed, False, None
    pid, p_start, p_end = hit[0]
    span = MatchSpan(start=start, end=end, paragraph=pid, para_start=max(start, p_start) - p_start, para_end=min(end, p_end) - p_start)
    if claimed in {h[0] for h in hit}:
        return claimed, False, span
    return pid, True, span


def _verify_one(o: ExtractedObligation, doc: "FetchedDocument", src, spans) -> VerifiedObligation:
    fields = dict(
        who=o.who, must_do=o.must_do, deadline=o.deadline, effective_from=o.effective_from, paragraph=o.paragraph,
        quote=o.quote, penalty_or_consequence=o.penalty_or_consequence,
        injected_test=bool(getattr(o, "injected_test", False)),
    )

    def rejected(reason: str, **extra) -> VerifiedObligation:
        return VerifiedObligation(status="rejected", reason=reason, **fields, **extra)

    quote = normalize(o.quote)
    if len(quote) < MIN_QUOTE_CHARS:
        return rejected("quote too short to verify")

    prefer = next(((s, e) for pid, s, e in spans or [] if pid == o.paragraph), None)
    match, best_score = find_quote(src, quote, prefer)
    if match is None:
        return rejected("quote not found in source", score=round(best_score, 1))

    matched_text = doc.full_text[match.start:match.end]
    pid, corrected, span = _paragraph(spans, match.start, match.end, o.paragraph)
    shown = dict(match_span=span, matched_text=matched_text, score=round(match.score, 1))

    source_facts = extract_facts(matched_text, number_words=True)
    claim = merge(extract_facts(o.must_do), iso_date_facts(o.deadline), iso_date_facts(o.effective_from))
    missing = missing_facts(claim, source_facts)
    if not match.exact:
        # a near match may differ from the source in exactly the digits that matter, so the quote is checked too
        missing += [f"{m} (in the quote)" for m in missing_facts(extract_facts(o.quote), source_facts)]
    if missing:
        return rejected(f"number/date not in source: {', '.join(missing)}", **shown)

    fields["paragraph"] = pid
    return VerifiedObligation(
        status="verified" if match.exact else "near", paragraph_corrected=corrected, **fields, **shown
    )


def verify(obligations: Sequence[ExtractedObligation], doc: "FetchedDocument") -> tuple[list[VerifiedObligation], VerifyCounts]:
    src = normalize_with_map(doc.full_text)  # once per document
    spans = paragraph_spans(doc.paragraphs, doc.full_text)
    results = [_verify_one(o, doc, src, spans) for o in obligations]
    counts = VerifyCounts(
        verified=sum(r.status == "verified" for r in results),
        near=sum(r.status == "near" for r in results),
        rejected=sum(r.status == "rejected" for r in results),
    )
    return results, counts

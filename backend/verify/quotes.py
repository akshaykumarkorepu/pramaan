"""Finding a quote in the source: exact normalised substring first, then a fuzzy alignment."""
import bisect
from dataclasses import dataclass

from rapidfuzz import fuzz

from api.schemas import Paragraph
from verify.normalize import NormText

NEAR_MATCH_MIN_SCORE = 92.0
MAX_OCCURRENCES = 50


@dataclass
class Match:
    start: int  # offsets into the ORIGINAL text
    end: int
    score: float
    exact: bool


def paragraph_spans(paragraphs: list[Paragraph], full_text: str) -> list[tuple[str, int, int]] | None:
    """(id, start, end) of each paragraph inside full_text, which M2 builds with "\\n\\n" between paragraphs.
    None if the paragraphs don't reproduce full_text (then paragraph checks are skipped)."""
    spans, pos = [], 0
    for p in paragraphs:
        spans.append((p.id, pos, pos + len(p.text)))
        pos += len(p.text) + 2
    return spans if "\n\n".join(p.text for p in paragraphs) == full_text else None


def overlapping(spans: list[tuple[str, int, int]], start: int, end: int) -> list[tuple[str, int, int]]:
    i = max(bisect.bisect_right([s for _, s, _ in spans], start) - 1, 0)
    out = []
    while i < len(spans) and spans[i][1] < end:
        if spans[i][2] > start:
            out.append(spans[i])
        i += 1
    return out


def _word_bounds(text: str, a: int, b: int) -> tuple[int, int]:
    """Widen [a, b) to whole words so a fuzzy window never cuts a number or a date in half."""
    while a > 0 and text[a - 1] != " ":
        a -= 1
    while b < len(text) and text[b] != " ":
        b += 1
    return a, b


def find_quote(src: NormText, quote: str, prefer: tuple[int, int] | None = None) -> tuple[Match | None, float]:
    """Returns (match, best_score). `quote` is already normalised. If it occurs several times, the occurrence inside
    `prefer` (the claimed paragraph's original-text span) wins, else the first."""
    if not quote:
        return None, 0.0
    hits, pos = [], src.text.find(quote)
    while pos != -1 and len(hits) < MAX_OCCURRENCES:
        hits.append(pos)
        pos = src.text.find(quote, pos + 1)
    if hits:
        spans = [src.span(h, h + len(quote)) for h in hits]
        chosen = next((s for s in spans if prefer and s[0] < prefer[1] and s[1] > prefer[0]), spans[0])
        return Match(chosen[0], chosen[1], 100.0, True), 100.0
    if len(quote) > len(src.text):
        return None, 0.0
    alignment = fuzz.partial_ratio_alignment(quote, src.text)
    if alignment is None:
        return None, 0.0
    if alignment.score < NEAR_MATCH_MIN_SCORE:
        return None, float(alignment.score)
    a, b = _word_bounds(src.text, alignment.dest_start, alignment.dest_end)
    start, end = src.span(a, b)
    return Match(start, end, float(alignment.score), False), float(alignment.score)

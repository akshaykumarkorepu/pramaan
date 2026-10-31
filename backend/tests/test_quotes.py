from api.schemas import Paragraph
from verify.normalize import normalize, normalize_with_map
from verify.quotes import find_quote, overlapping, paragraph_spans

SRC = "Banks shall file the annual return. Depositories, custodians and DDPs shall make necessary changes in their systems and processes."


def find(src_text, quote, prefer=None):
    return find_quote(normalize_with_map(src_text), normalize(quote), prefer)


def test_exact_match_returns_original_offsets():
    m, score = find(SRC, "Depositories,  custodians and DDPs shall make necessary changes")
    assert m.exact and score == 100.0
    assert SRC[m.start:m.end].startswith("Depositories, custodians")


def test_near_match_scores_and_is_widened_to_whole_words():
    typo = "Depositories, custodians and DDPs shall make necessary changes in their systems and procesess."
    m, score = find(SRC, typo)
    assert not m.exact and 92 <= score < 100
    window = SRC[m.start:m.end]
    assert window.startswith("Depositories") and window.endswith("processes.")


def test_unrelated_quote_is_not_found_but_reports_its_best_score():
    m, score = find(SRC, "All regulated entities shall pay a one-time fee of Rs. 25 lakh by December 1, 2026.")
    assert m is None and 0 < score < 92


def test_quote_longer_than_source_and_empty_quote_are_not_found():
    assert find("short text", "x" * 200)[0] is None
    assert find("short text", "")[0] is None


def test_repeated_quote_prefers_the_claimed_paragraph_span():
    text = "Banks shall file the annual return.\n\nOther text here.\n\nBanks shall file the annual return."
    second = text.rindex("Banks")
    first_hit, _ = find(text, "Banks shall file the annual return.")
    preferred, _ = find(text, "Banks shall file the annual return.", prefer=(second, len(text)))
    assert first_hit.start == 0 and preferred.start == second


def test_paragraph_spans_follow_the_double_newline_join_and_detect_a_mismatch():
    paras = [Paragraph(id="a", text="One."), Paragraph(id="b", text="Two."), Paragraph(id="c", text="Three.")]
    full = "\n\n".join(p.text for p in paras)
    spans = paragraph_spans(paras, full)
    assert spans == [("a", 0, 4), ("b", 6, 10), ("c", 12, 18)]
    assert full[6:10] == "Two."
    assert paragraph_spans(paras, full + "x") is None


def test_overlapping_finds_every_paragraph_a_span_touches():
    spans = [("a", 0, 4), ("b", 6, 10), ("c", 12, 18)]
    assert [s[0] for s in overlapping(spans, 2, 8)] == ["a", "b"]
    assert [s[0] for s in overlapping(spans, 6, 10)] == ["b"]
    assert [s[0] for s in overlapping(spans, 10, 12)] == []  # only the separator
    assert [s[0] for s in overlapping(spans, 0, 18)] == ["a", "b", "c"]

import pytest

from verify.normalize import normalize


@pytest.mark.parametrize("raw,expected", [
    ("  Banks   SHALL\tcomply\n now ", "banks shall comply now"),
    ("the “final” date", 'the "final" date'),
    ("RBI’s circular", "rbi's circular"),
    ("5 – 10 and 5 — 10 and 5‑10", "5 - 10 and 5 - 10 and 5-10"),
    ("e ﬁnal ﬁlings", "e final filings"),  # non-breaking space and the PDF ligature "ﬁ"
    ("", ""),
])
def test_normalize_folds_formatting_only(raw, expected):
    assert normalize(raw) == expected


def test_normalize_keeps_numbers_and_meaningful_punctuation():
    assert normalize("Rs. 10,00,000 by 31.03.2027; (a) yes") == "rs. 10,00,000 by 31.03.2027; (a) yes"


def test_normalize_keeps_devanagari_and_telugu():
    assert normalize("सभी  बैंक  ప్రమాణం") == "सभी बैंक ప్రమాణం"


# ---------------------------------------------------------------- offset map and hyphen handling (M5)

from verify.normalize import normalize_with_map  # noqa: E402


def test_soft_hyphens_and_zero_width_characters_are_removed():
    assert normalize("regu­lation​ of banks") == "regulation of banks"


@pytest.mark.parametrize("raw", ["regu-\nlation", "regu- \n lation", "regu-lation", "regulation"])
def test_hyphens_inside_words_and_at_line_breaks_are_folded_on_both_sides(raw):
    assert normalize(raw) == "regulation"


def test_co_operative_is_the_same_word_with_or_without_the_hyphen():
    assert normalize("Co-operative Banks") == normalize("Cooperative banks")


def test_dashes_that_are_punctuation_or_between_digits_are_kept():
    assert normalize("word - word") == "word - word"
    assert normalize("5-10 and 2026-10-27 and (a)-(b)") == "5-10 and 2026-10-27 and (a)-(b)"


def test_map_slices_back_to_the_original_text_after_expansion_and_collapse():
    original = "The  ﬁnal \n date is Regu-\nlation 5."
    n = normalize_with_map(original)
    a = n.text.index("final date")
    b = n.text.index("regulation") + len("regulation")
    assert original[slice(*n.span(a, b))] == "ﬁnal \n date is Regu-\nlation"


def test_map_is_aligned_with_the_normalised_text():
    n = normalize_with_map("A  b­c\n\nD")
    assert len(n.text) == len(n.starts) == len(n.ends) and n.text == "a bc d"


def test_combining_marks_stay_with_their_base_character():
    n = normalize_with_map("क्षत्रिय ప్రమాణం")
    assert n.text == "क्षत्रिय ప్రమాణం" and n.span(0, len(n.text)) == (0, len("क्षत्रिय ప్రమాణం"))

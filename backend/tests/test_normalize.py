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

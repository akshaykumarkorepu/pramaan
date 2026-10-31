"""Text normalisation shared by extraction (de-dup) and, from M5, the verifier.

Only formatting differences are folded away: case, whitespace, curly quotes, dash variants and PDF ligatures.
Words, numbers and punctuation that carry meaning are left alone."""
import re
import unicodedata

_QUOTES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "“": '"', "”": '"', "„": '"', "‟": '"', "`": "'", "´": "'"})
_DASHES = re.compile(r"[‐‑‒–—―−]")  # hyphen, non-breaking hyphen, figure/en/em dash, horizontal bar, minus
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)  # folds ligatures ("ﬁ" -> "fi") and non-breaking spaces
    text = text.translate(_QUOTES)
    text = _DASHES.sub("-", text)
    return _SPACES.sub(" ", text).strip().lower()

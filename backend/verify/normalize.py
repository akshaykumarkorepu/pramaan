"""Text normalisation for verification, with an offset map back to the original text.

Only formatting differences are folded away: case, whitespace, curly quotes, dash variants, PDF ligatures, soft
hyphens, and hyphens inside words (which PDF line breaks introduce or remove). Words, numbers and punctuation that
carry meaning are left alone. Every normalised character remembers where it came from, so a match found in the
normalised text can be sliced back out of the original text exactly."""
import unicodedata
from dataclasses import dataclass

_QUOTES = {"‘": "'", "’": "'", "‚": "'", "‛": "'", "“": '"', "”": '"', "„": '"', "‟": '"', "`": "'", "´": "'"}
_DASHES = {c: "-" for c in "‐‑‒–—―−"}  # hyphen, non-breaking hyphen, figure/en/em dash, horizontal bar, minus
_DELETE = {c: None for c in "­​‌‍⁠﻿"}  # soft hyphen and zero-width characters
_TRANS = str.maketrans({**_QUOTES, **_DASHES, **_DELETE})
_MARKS = {"Mn", "Mc", "Me"}  # combining marks stay attached to their base character (Devanagari, Telugu...)
_cache: dict[str, str] = {}


@dataclass(frozen=True)
class NormText:
    text: str
    starts: list[int]  # original start offset of each normalised character
    ends: list[int]  # original end offset (exclusive)

    def span(self, start: int, end: int) -> tuple[int, int]:
        """Original (start, end) for the normalised range [start, end)."""
        return self.starts[start], self.ends[end - 1]


def _fold(piece: str) -> str:
    out = _cache.get(piece)
    if out is None:
        out = unicodedata.normalize("NFKC", piece).translate(_TRANS).lower()
        if any(c.isspace() for c in out):
            out = "".join("\n" if c in "\r\n" else " " if c.isspace() else c for c in out)
        if len(_cache) < 50_000:
            _cache[piece] = out
    return out


def normalize_with_map(text: str) -> NormText:
    # pass 1: fold each grapheme cluster (a base character plus its combining marks)
    chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    i, n = 0, len(text)
    while i < n:
        j = i + 1
        while j < n and unicodedata.category(text[j]) in _MARKS:
            j += 1
        for c in _fold(text[i:j]):
            chars.append(c)
            starts.append(i)
            ends.append(j)
        i = j

    # pass 2: collapse whitespace; drop a hyphen that sits between two letters (a PDF line-break artefact)
    out_c: list[str] = []
    out_s: list[int] = []
    out_e: list[int] = []
    i, n = 0, len(chars)
    while i < n:
        c = chars[i]
        if c in " \n":
            j, has_newline = i, False
            while j < n and chars[j] in " \n":
                has_newline |= chars[j] == "\n"
                j += 1
            if (has_newline and len(out_c) >= 2 and out_c[-1] == "-" and out_c[-2].isalpha()
                    and j < n and chars[j].isalpha()):
                out_c.pop(), out_s.pop(), out_e.pop()  # "regu-\nlation": remove the hyphen and the break
            elif out_c and j < n:  # no leading or trailing space
                out_c.append(" ")
                out_s.append(starts[i])
                out_e.append(ends[j - 1])
            i = j
            continue
        if c == "-" and out_c and out_c[-1].isalpha() and i + 1 < n and chars[i + 1].isalpha():
            i += 1  # "co-operative" == "cooperative"; digit hyphens (2026-10-27, 5-10) are untouched
            continue
        out_c.append(c)
        out_s.append(starts[i])
        out_e.append(ends[i])
        i += 1
    return NormText("".join(out_c), out_s, out_e)


def normalize(text: str) -> str:
    return normalize_with_map(text).text

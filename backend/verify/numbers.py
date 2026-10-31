"""Numbers and dates, compared by value.

Dates are found by regex and converted with dateparser (day-first, as Indian documents write them), so
"27 October 2026" == "October 27, 2026" == "27/10/2026" == 2026-10-27. Numbers fold units, so
"10 lakh" == "10,00,000". Paragraph-style ids ("3.1(a)", "14.06.001") and ordinals are ignored."""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Hashable

import dateparser

_MONTHS = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_MONTH_NUM = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_DATE_PATTERNS = [
    re.compile(rf"\b{_DAY}\s+(?:day\s+of\s+)?{_MONTHS}\.?,?\s+\d{{4}}\b", re.I),  # 27 October 2026, 1st February, 2024
    re.compile(rf"\b{_MONTHS}\.?\s+{_DAY},?\s+\d{{4}}\b", re.I),  # October 27, 2026
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # ISO
    re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}\b"),  # 27/10/2026, 27.10.2026, 27-10-2026
]
_MONTH_YEAR = re.compile(rf"\b({_MONTHS})\.?,?\s+(\d{{4}})\b", re.I)
_DP_SETTINGS = {"DATE_ORDER": "DMY", "PREFER_DAY_OF_MONTH": "first"}

_IGNORED = re.compile(
    r"\d+(?:\.\d+){2,}"  # multi-level ids and file numbers: 14.06.001
    r"|\d+(?:\.\d+)*\([a-z]{1,4}\)"  # paragraph ids: 3.1(a)
    r"|\b\d+(?:st|nd|rd|th)\b",  # ordinals
    re.I,
)
_UNITS = {
    "lakh": 10**5, "lakhs": 10**5, "lac": 10**5, "lacs": 10**5,
    "crore": 10**7, "crores": 10**7, "cr": 10**7,
    "thousand": 10**3, "million": 10**6, "mn": 10**6, "billion": 10**9, "bn": 10**9,
}
_NUMBER = re.compile(
    r"(?<![\w])(\d{1,3}(?:,\d{2,3})+|\d+)(\.\d+)?(?:\s?(" + "|".join(sorted(_UNITS, key=len, reverse=True)) + r")\b\.?)?(?![\w])",
    re.I,
)
_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
)}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_WORD_NUMBER = re.compile(
    r"\b(?:(" + "|".join(_TENS) + r")(?:[-\s](" + "|".join(list(_WORDS)[1:10]) + r"))?|(" + "|".join(_WORDS) + r")|(hundred))\b",
    re.I,
)

Fact = Hashable  # a date, ("ym", year, month), ("raw", text) or a Decimal


@dataclass
class Facts:
    """Facts found in one text: value -> the text as written (for messages)."""
    dates: dict[Fact, str] = field(default_factory=dict)
    numbers: dict[Decimal, str] = field(default_factory=dict)


@lru_cache(maxsize=4096)
def _parse_date(text: str) -> date | None:
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return date.fromisoformat(text)
        cleaned = re.sub(r"\bday\s+of\s+", "", text, flags=re.I)
        parsed = dateparser.parse(cleaned, languages=["en"], settings=_DP_SETTINGS)
        return parsed.date() if parsed else None
    except (ValueError, OverflowError):
        return None


def _extract_dates(text: str) -> tuple[dict[Fact, str], str]:
    """Returns the dates found and the text with date spans blanked out (so day/year digits aren't counted as numbers)."""
    found: dict[Fact, str] = {}
    claimed: list[tuple[int, int]] = []
    blanked = list(text)

    def free(m: re.Match) -> bool:
        return all(m.end() <= a or m.start() >= b for a, b in claimed)

    for pattern in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            if not free(m):
                continue
            parsed = _parse_date(m.group(0))
            found[parsed if parsed else ("raw", " ".join(m.group(0).lower().split()))] = m.group(0)
            claimed.append((m.start(), m.end()))
    for m in _MONTH_YEAR.finditer(text):
        if free(m):
            found[("ym", int(m.group(2)), _MONTH_NUM[m.group(1)[:3].lower()])] = m.group(0)
            claimed.append((m.start(), m.end()))
    for a, b in claimed:
        blanked[a:b] = " " * (b - a)
    return found, "".join(blanked)


def _extract_numbers(text: str, words: bool) -> dict[Decimal, str]:
    text = _IGNORED.sub(lambda m: " " * len(m.group(0)), text)
    found: dict[Decimal, str] = {}
    for m in _NUMBER.finditer(text):
        try:
            value = Decimal(m.group(1).replace(",", "") + (m.group(2) or ""))
        except InvalidOperation:
            continue
        if m.group(3):
            value *= _UNITS[m.group(3).lower()]
        found[value.normalize()] = m.group(0).strip()
    if words:  # source side only: "six months" supplies 6
        for m in _WORD_NUMBER.finditer(text):
            if m.group(1):
                value = _TENS[m.group(1).lower()] + (_WORDS[m.group(2).lower()] if m.group(2) else 0)
            elif m.group(3):
                value = _WORDS[m.group(3).lower()]
            else:
                value = 100
            found.setdefault(Decimal(value), m.group(0))
    return found


def extract_facts(text: str, *, number_words: bool = False) -> Facts:
    dates, rest = _extract_dates(text)
    return Facts(dates=dates, numbers=_extract_numbers(rest, number_words))


def _date_supported(fact: Fact, source: Facts) -> bool:
    if fact in source.dates:
        return True
    if isinstance(fact, tuple) and fact[0] == "ym":  # "March 2027" is satisfied by any date in that month
        return any(isinstance(d, date) and (d.year, d.month) == fact[1:] for d in source.dates)
    return False


def missing_facts(claim: Facts, source: Facts) -> list[str]:
    """Every date and number in `claim` that the source does not contain, as written in the claim."""
    missing = [shown for fact, shown in claim.dates.items() if not _date_supported(fact, source)]
    missing += [shown for value, shown in claim.numbers.items() if value not in source.numbers]
    return missing


def iso_date_facts(value: str | None) -> Facts:
    """A deadline/effective_from field: it must be a real YYYY-MM-DD date, else the raw text is the (unmatchable) fact."""
    facts = Facts()
    if value and value.strip():
        parsed = _parse_date(value.strip()) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()) else None
        facts.dates[parsed if parsed else ("raw", value.strip().lower())] = value.strip()
    return facts


def merge(*parts: Facts) -> Facts:
    out = Facts()
    for p in parts:
        out.dates.update(p.dates)
        out.numbers.update(p.numbers)
    return out

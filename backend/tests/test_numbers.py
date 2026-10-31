from datetime import date
from decimal import Decimal

import pytest

from verify.numbers import extract_facts, iso_date_facts, merge, missing_facts


def dates(text):
    return set(extract_facts(text).dates)


def numbers(text, words=False):
    return set(extract_facts(text, number_words=words).numbers)


@pytest.mark.parametrize("text", [
    "by 27 October 2026", "by October 27, 2026", "by 27th October, 2026", "by 27/10/2026", "by 27.10.2026",
    "by 27-10-2026", "by 2026-10-27", "by Oct 27, 2026", "on the 27th day of October 2026",
])
def test_every_date_format_resolves_to_the_same_value(text):
    assert dates(text) == {date(2026, 10, 27)}


def test_dd_mm_yyyy_is_read_day_first():
    assert dates("on 05/04/2027") == {date(2027, 4, 5)}


def test_month_year_is_kept_as_year_and_month_not_given_a_made_up_day():
    assert dates("by March 2027") == {("ym", 2027, 3)}


def test_date_digits_are_not_counted_as_numbers():
    assert numbers("by 27 October 2026 pay 15 days") == {Decimal(15)}


def test_invalid_calendar_date_is_kept_as_unmatchable_raw_text():
    assert dates("on 31/02/2026") == {("raw", "31/02/2026")}


@pytest.mark.parametrize("text,expected", [
    ("10 lakh", {Decimal(1_000_000)}),
    ("Rs. 10,00,000", {Decimal(1_000_000)}),
    ("₹10 lakh", {Decimal(1_000_000)}),
    ("INR 1,234,567", {Decimal(1_234_567)}),
    ("2 crore", {Decimal(20_000_000)}),
    ("3.5 crore", {Decimal(35_000_000)}),
    ("5%", {Decimal(5)}),
    ("05 entries", {Decimal(5)}),
    ("within 15 days and 30 days", {Decimal(15), Decimal(30)}),
    ("1.5 million", {Decimal(1_500_000)}),
])
def test_numbers_are_compared_by_value(text, expected):
    assert numbers(text) == expected


@pytest.mark.parametrize("text", [
    "see paragraph 3.1(a)", "Master Circular para 14.06.001", "the 3rd phase and 1st step", "RBI/2026-27/303x", "TAi007A",
])
def test_paragraph_ids_ordinals_and_codes_are_ignored(text):
    got = numbers(text)
    assert Decimal("3.1") not in got and Decimal(3) not in got and Decimal(1) not in got and Decimal(14) not in got


def test_number_words_count_only_on_the_source_side():
    assert numbers("within six months") == set()
    assert numbers("within six months", words=True) == {Decimal(6)}
    assert numbers("twenty-five percent and a hundred", words=True) >= {Decimal(25), Decimal(100)}


def test_missing_facts_reports_what_the_source_lacks_as_written_in_the_claim():
    source = extract_facts("pay Rs. 10,00,000 by October 27, 2026 within 15 days", number_words=True)
    assert missing_facts(extract_facts("pay 10 lakh by 27 Oct 2026 in 15 days"), source) == []
    assert missing_facts(extract_facts("pay 12 lakh by 28 Oct 2026"), source) == ["28 Oct 2026", "12 lakh"]


def test_month_year_claim_is_satisfied_by_a_full_date_in_that_month_but_not_the_reverse():
    assert missing_facts(extract_facts("by March 2027"), extract_facts("by 31 March 2027")) == []
    assert missing_facts(extract_facts("by 31 March 2027"), extract_facts("by March 2027")) == ["31 March 2027"]


def test_iso_field_must_be_a_real_iso_date():
    assert set(iso_date_facts("2026-10-27").dates) == {date(2026, 10, 27)}
    assert set(iso_date_facts("27 October 2026").dates) == {("raw", "27 october 2026")}  # wrong format: can't match
    assert set(iso_date_facts("2026-02-31").dates) == {("raw", "2026-02-31")}
    assert iso_date_facts(None).dates == {} and iso_date_facts("  ").dates == {}


def test_merge_combines_facts():
    both = merge(extract_facts("5 days"), iso_date_facts("2026-10-27"))
    assert both.numbers and both.dates

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from api.schemas import Paragraph
from pipeline.fetch_document import FetchedDocument
from pipeline.models import ExtractedObligation
from verify.verifier import InjectedObligation, VerifyCounts, verify

SENTENCE = "All Urban Co-operative Banks shall file the annual return by October 27, 2026 and pay Rs. 10,00,000 as the fee."


def make_doc(*paras) -> FetchedDocument:
    """paras: (id, text) pairs."""
    ps = [Paragraph(id=i, text=t) for i, t in paras]
    full = "\n\n".join(p.text for p in ps)
    return FetchedDocument(
        title="T", url="https://www.rbi.org.in/x", source="rbi", fetched_at=datetime.now(timezone.utc),
        paragraphs=ps, full_text=full, pdf_url=None, char_count=len(full),
    )


def ob(quote=SENTENCE, must_do="File the annual return", deadline=None, effective_from=None, paragraph="2", cls=ExtractedObligation, **kw):
    return cls(
        who="All Urban Co-operative Banks", must_do=must_do, deadline=deadline, effective_from=effective_from,
        paragraph=paragraph, quote=quote, penalty_or_consequence=None, **kw,
    )


DOC = make_doc(("p1", "To All Urban Co-operative Banks"), ("2", SENTENCE), ("3", "Banks shall act within six months of this circular."))


def one(obligation, doc=DOC):
    results, counts = verify([obligation], doc)
    assert len(results) == 1
    return results[0], counts


# ---------------------------------------------------------------- the quote

def test_exact_match_is_verified_with_a_span_that_slices_back_to_the_quote():
    r, counts = one(ob())
    assert r.status == "verified" and r.reason is None and r.score == 100.0
    assert DOC.full_text[r.match_span.start:r.match_span.end] == SENTENCE == r.matched_text
    assert (r.match_span.paragraph, r.match_span.para_start, r.match_span.para_end) == ("2", 0, len(SENTENCE))
    assert counts == VerifyCounts(verified=1, near=0, rejected=0)


def test_whitespace_and_case_differences_still_verify():
    r, _ = one(ob(quote="all urban   co-operative banks SHALL file the annual\nreturn by October 27, 2026 and pay Rs. 10,00,000 as the fee."))
    assert r.status == "verified"


def test_pdf_hyphenation_in_the_source_or_the_quote_still_verifies():
    doc = make_doc(("1", "Depositories shall make necessary changes in their regu-\nlation systems and processes to comply."))
    clean = "Depositories shall make necessary changes in their regulation systems and processes to comply."
    assert one(ob(quote=clean, must_do="Make changes", paragraph="1"), doc)[0].status == "verified"
    doc2 = make_doc(("1", clean))
    hyphenated = "Depositories shall make necessary changes in their regu-lation systems and processes to comply."
    assert one(ob(quote=hyphenated, must_do="Make changes", paragraph="1"), doc2)[0].status == "verified"


def test_soft_hyphen_and_ligature_in_the_source_verify_against_a_clean_quote():
    doc = make_doc(("1", "Banks shall ﬁle the re­turn with the regulator within the stated period."))
    r, _ = one(ob(quote="Banks shall file the return with the regulator within the stated period.", must_do="File", paragraph="1"), doc)
    assert r.status == "verified"
    assert doc.full_text[r.match_span.start:r.match_span.end] == doc.full_text  # slice is of the ORIGINAL text


def test_one_typo_is_a_near_match_with_score_and_the_source_text_shown():
    typo = SENTENCE.replace("annual", "anual")
    r, counts = one(ob(quote=typo))
    assert r.status == "near" and 92 <= r.score < 100
    assert r.matched_text == SENTENCE and r.quote == typo  # the user sees the source's words
    assert counts.near == 1 and counts.verified == 0


def test_fabricated_quote_is_rejected_with_a_low_score_and_no_match():
    r, counts = one(ob(quote="All regulated entities shall pay a one-time fee of Rs. 25 lakh to the regulator by December 1, 2026."))
    assert r.status == "rejected" and r.reason == "quote not found in source"
    assert r.match_span is None and r.matched_text is None and 0 < r.score < 92
    assert counts.rejected == 1


@pytest.mark.parametrize("quote", ["", "   ", "Banks shall file.", "x" * 29])
def test_quote_under_30_normalised_characters_is_rejected(quote):
    r, _ = one(ob(quote=quote))
    assert r.status == "rejected" and r.reason == "quote too short to verify"


def test_quote_of_exactly_30_characters_is_checked():
    thirty = "Banks shall file the return ok"
    assert len(thirty) == 30
    r, _ = one(ob(quote=thirty, must_do="x"), make_doc(("1", "Note: " + thirty + " please.")))
    assert r.status == "verified"


def test_hindi_exact_match_is_verified():
    text = "सभी शहरी सहकारी बैंकों को 31 मार्च 2027 तक वार्षिक विवरणी दाखिल करनी होगी।"
    doc = make_doc(("1", text), ("2", "अन्य जानकारी"))
    r, _ = one(ob(quote=text, must_do="File the annual return", paragraph="1"), doc)
    assert r.status == "verified" and doc.full_text[r.match_span.start:r.match_span.end] == text


# ---------------------------------------------------------------- numbers and dates

def test_correct_quote_with_a_wrong_number_in_must_do_is_rejected():
    r, _ = one(ob(must_do="Pay a fee of 30 lakh"))
    assert r.status == "rejected" and r.reason == "number/date not in source: 30 lakh"
    assert r.match_span is not None and r.score == 100.0  # still shows where the quote matched


def test_wrong_deadline_is_rejected():
    r, _ = one(ob(deadline="2026-10-28"))
    assert r.status == "rejected" and r.reason == "number/date not in source: 2026-10-28"


def test_deadline_matches_the_source_date_by_value():
    r, _ = one(ob(deadline="2026-10-27"))
    assert r.status == "verified"


@pytest.mark.parametrize("must_do", [
    "File by 27 October 2026", "File by October 27, 2026", "File by 27/10/2026", "File by 27th Oct 2026", "File by 27.10.2026",
])
def test_same_date_in_a_different_format_passes(must_do):
    assert one(ob(must_do=must_do, deadline="2026-10-27"))[0].status == "verified"


def test_amounts_compare_by_value_across_units_and_separators():
    assert one(ob(must_do="Pay 10 lakh as the fee"))[0].status == "verified"
    assert one(ob(must_do="Pay ₹1000000 as the fee"))[0].status == "verified"


def test_deadline_without_an_explicit_date_in_the_quote_is_rejected():
    doc = make_doc(("1", "Banks shall submit the compliance report within 30 days of the end of each quarter."))
    r, _ = one(ob(quote=doc.full_text, must_do="Submit the report within 30 days", deadline="2026-12-31", paragraph="1"), doc)
    assert r.status == "rejected" and "2026-12-31" in r.reason


def test_relative_timing_with_a_null_date_is_verified():
    doc = make_doc(("1", "Banks shall submit the compliance report within 30 days of the end of each quarter."))
    assert one(ob(quote=doc.full_text, must_do="Submit the report within 30 days", paragraph="1"), doc)[0].status == "verified"


def test_a_number_word_in_the_source_supports_the_digit_in_must_do():
    q = "Banks shall act within six months of this circular."
    assert one(ob(quote=q, must_do="Act within 6 months", paragraph="3"))[0].status == "verified"
    assert one(ob(quote=q, must_do="Act within 7 months", paragraph="3"))[0].status == "rejected"


def test_paragraph_style_ids_and_ordinals_in_must_do_are_ignored():
    doc = make_doc(("1", "Banks shall comply with the requirements of the Master Circular within the stated time."))
    r, _ = one(ob(quote=doc.full_text, must_do="Comply per paragraph 3.1(a) and the 2nd schedule", paragraph="1"), doc)
    assert r.status == "verified"


def test_month_year_in_must_do_is_satisfied_by_a_full_date_but_not_the_reverse():
    doc = make_doc(("1", "Banks shall complete the audit by 31 March 2027 without any further extension."))
    assert one(ob(quote=doc.full_text, must_do="Complete the audit by March 2027", paragraph="1"), doc)[0].status == "verified"
    doc2 = make_doc(("1", "Banks shall complete the audit by March 2027 without any further extension."))
    assert one(ob(quote=doc2.full_text, must_do="Complete the audit by 31 March 2027", paragraph="1"), doc2)[0].status == "rejected"


def test_near_match_whose_quote_changes_a_number_is_rejected():
    tampered = SENTENCE.replace("10,00,000", "20,00,000")  # tiny edit, still scores above 92
    r, _ = one(ob(quote=tampered, must_do="File the annual return"))
    assert r.status == "rejected" and "(in the quote)" in r.reason and "20,00,000" in r.reason
    assert r.score >= 92  # it matched, then failed the number check


def test_near_match_with_a_changed_date_in_the_quote_is_rejected():
    r, _ = one(ob(quote=SENTENCE.replace("October 27, 2026", "October 28, 2026")))
    assert r.status == "rejected" and "October 28, 2026 (in the quote)" in r.reason


# ---------------------------------------------------------------- paragraphs

def test_match_in_another_paragraph_corrects_the_paragraph_id():
    r, _ = one(ob(paragraph="3"))
    assert r.status == "verified" and r.paragraph == "2" and r.paragraph_corrected is True
    assert r.match_span.paragraph == "2"


def test_correct_paragraph_is_left_alone_and_a_missing_one_is_filled_in():
    assert one(ob(paragraph="2"))[0].paragraph_corrected is False
    r, _ = one(ob(paragraph=None))
    assert r.paragraph == "2" and r.paragraph_corrected is True


def test_repeated_quote_prefers_the_claimed_paragraph():
    doc = make_doc(("2", SENTENCE), ("3", "Something else entirely different here."), ("5", SENTENCE))
    r5, _ = one(ob(paragraph="5"), doc)
    assert r5.paragraph == "5" and r5.paragraph_corrected is False and r5.match_span.paragraph == "5"
    r9, _ = one(ob(paragraph="9"), doc)
    assert r9.paragraph == "2" and r9.paragraph_corrected is True  # not found where claimed: first occurrence


def test_quote_spanning_two_paragraphs_keeps_either_claimed_paragraph():
    doc = make_doc(("1", "Banks shall file the annual return."), ("2", "The return must reach the regulator by the due date."))
    quote = "Banks shall file the annual return. The return must reach the regulator by the due date."
    r1, _ = one(ob(quote=quote, must_do="File the return", paragraph="2"), doc)
    assert r1.status == "verified" and r1.paragraph == "2" and r1.paragraph_corrected is False
    assert r1.match_span.paragraph == "1"  # where the match starts
    r2, _ = one(ob(quote=quote, must_do="File the return", paragraph="1"), doc)
    assert r2.paragraph == "1" and r2.paragraph_corrected is False


# ---------------------------------------------------------------- injected flag, counts, robustness

def test_injected_flag_is_preserved_and_a_fabricated_injected_claim_is_rejected():
    fake = ob(
        quote="TEST ONLY: all regulated entities shall pay a one-time fee of Rs. 25 lakh by December 1, 2026.",
        must_do="Pay Rs. 25 lakh by 1 December 2026", deadline="2026-12-01", cls=InjectedObligation,
    )
    real = ob()
    results, counts = verify([real, fake], DOC)
    assert [r.injected_test for r in results] == [False, True]
    assert [r.status for r in results] == ["verified", "rejected"]
    assert counts == VerifyCounts(verified=1, near=0, rejected=1)


def test_injected_flag_survives_even_when_verified():
    r, _ = one(ob(cls=InjectedObligation))
    assert r.injected_test is True and r.status == "verified"


def test_counts_cover_all_three_statuses_and_order_is_preserved():
    items = [ob(), ob(quote=SENTENCE.replace("annual", "anual")), ob(quote="A completely made up sentence that is not in the document at all.")]
    results, counts = verify(items, DOC)
    assert [r.status for r in results] == ["verified", "near", "rejected"]
    assert counts == VerifyCounts(verified=1, near=1, rejected=1)


def test_no_obligations_gives_empty_results():
    assert verify([], DOC) == ([], VerifyCounts(verified=0, near=0, rejected=0))


def test_penalty_and_other_fields_are_carried_through():
    o = ExtractedObligation(who="W", must_do="M", deadline=None, effective_from=None, paragraph="2", quote=SENTENCE, penalty_or_consequence="Penalty applies")
    r, _ = one(o)
    assert (r.who, r.must_do, r.quote, r.penalty_or_consequence) == ("W", "M", SENTENCE, "Penalty applies")


def test_large_document_verifies_quickly():
    filler = [(f"{i}", "Banks shall maintain adequate records of every transaction they undertake. " * 8) for i in range(1, 500)]
    doc = make_doc(*filler, ("end", SENTENCE))
    assert len(doc.full_text) > 300_000
    start = time.perf_counter()
    r, _ = one(ob(paragraph="end"), doc)
    assert r.status == "verified" and time.perf_counter() - start < 3.0


def test_inconsistent_paragraphs_skip_the_paragraph_check_instead_of_crashing():
    doc = make_doc(("1", SENTENCE))
    doc = doc.model_copy(update={"full_text": doc.full_text + " "})  # paragraphs no longer reproduce full_text
    r, _ = one(ob(paragraph="9"), doc)
    assert r.status == "verified" and r.match_span is None and r.paragraph == "9" and r.paragraph_corrected is False


# ---------------------------------------------------------------- purity

def test_verify_package_imports_no_network_or_llm_code():
    backend = Path(__file__).resolve().parents[1]
    code = "import sys, verify.verifier; bad = [m for m in ('groq','httpx','llm','pdfplumber') if m in sys.modules]; print(bad)"
    out = subprocess.run([sys.executable, "-c", code], cwd=backend, capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]", f"verify/ pulled in {out}"

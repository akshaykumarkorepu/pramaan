from datetime import date, timedelta

import pytest

from api.schemas import Paragraph
from pipeline.fake_claim import TEMPLATES, make_fake_claim
from pipeline.fetch_document import FetchedDocument
from verify.verifier import verify


def doc_with(*texts: str) -> FetchedDocument:
    paras = [Paragraph(id=str(i + 1), text=t) for i, t in enumerate(texts)]
    return FetchedDocument(
        url="https://rbi.org.in/x", source="rbi", title="T", paragraphs=paras,
        full_text="\n".join(texts), fetched_at="2026-10-31T00:00:00+00:00", char_count=sum(map(len, texts)),
    )


@pytest.mark.parametrize("source", ["rbi", "sebi", "pib"])
def test_every_template_is_rejected_by_the_real_verifier(source):
    doc = doc_with("Banks shall maintain a Cash Reserve Ratio of 4.5 per cent of net demand and time liabilities.")
    for who, must_do, quote, days in TEMPLATES[source]:
        claim = make_fake_claim(source, doc)
        assert verify([claim], doc)[0][0].status == "rejected"
        assert len(quote) >= 30 and 7 <= days <= 60


def test_deadline_is_within_the_next_60_days():
    today = date(2026, 10, 31)
    claim = make_fake_claim("sebi", doc_with("Some other text that is long enough to be a paragraph."), today)
    assert today < date.fromisoformat(claim.deadline) <= today + timedelta(days=60)
    assert claim.injected_test is True


def test_a_template_that_matches_the_document_is_skipped():
    first_quote = TEMPLATES["rbi"][0][2]
    claim = make_fake_claim("rbi", doc_with(first_quote))  # the document really contains the first template
    assert claim.quote != first_quote
    assert claim.must_do != TEMPLATES["rbi"][0][1]


def test_unknown_source_still_gives_a_claim():
    assert make_fake_claim(None, doc_with("x" * 40)).quote

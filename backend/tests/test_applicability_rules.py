import asyncio

import pytest

from llm.client import CallMeta
from llm.errors import LLMError
from pipeline import applicability as ap
from pipeline.applicability import ApplicabilityLLM, check_applicability
from pipeline.models import ExtractedObligation, ExtractionResult
from test_verifier import make_doc
from verify.verifier import verify

BODY = "Banks shall report every fraud to the Reserve Bank within 21 days of detection."


def run(profile, to, *, kind="obligations", addressees=(), body=BODY, who="the entities", source="rbi"):
    doc = make_doc(("p1", to), ("2", body))
    doc.source = source
    ex = ExtractionResult(kind=kind, addressees=list(addressees), obligations=[])
    verified = verify([ExtractedObligation(
        who=who, must_do="Report fraud", deadline=None, effective_from=None, paragraph="2", quote=body, penalty_or_consequence=None)], doc)[0] if kind == "obligations" else []
    return doc, ex, verified


def check(profile, *a, **kw):
    doc, ex, verified = run(profile, *a, **kw)
    return asyncio.run(check_applicability(profile, doc, ex, verified))


@pytest.fixture
def no_llm(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("LLM must not be called")
    monkeypatch.setattr(ap, "call_json", boom)


def llm_says(monkeypatch, value="yes", reason="Addressed to the profile.", quote=None, error=None):
    calls = []

    async def fake(messages, schema, **kw):
        calls.append((messages, schema, kw))
        if error:
            raise error
        return ApplicabilityLLM(value=value, reason=reason, quote=quote), CallMeta(
            model_used="fast-m", fallback_used=False, latency_ms=40, prompt_tokens=10, completion_tokens=5, attempts=1)

    monkeypatch.setattr(ap, "call_json", fake)
    return calls


@pytest.mark.parametrize("profile,to", [
    ("nbfc", "To All Non-Banking Financial Companies and Housing Finance Companies"),
    ("coop_bank", "To All Urban Co-operative Banks and State Co-operative Banks"),
    ("research_analyst", "To all Research Analysts registered with SEBI"),
    ("stock_broker", "To all Stock Brokers and Trading Members"),
    ("citizen_msme", "Relief for MSMEs and farmers announced for the public"),
])
def test_rule_hit_per_profile(profile, to, no_llm):
    result, meta = check(profile, to)
    assert result.value == "yes" and meta.method == "rule" and meta.llm_calls == 0
    assert result.quote and result.quote in to


def test_regulated_entities_depends_on_regulator(no_llm):
    rbi, _ = check("nbfc", "To All Regulated Entities", source="rbi")
    sebi, _ = check("stock_broker", "To All Regulated Entities", source="sebi")
    assert rbi.value == "yes" and sebi.value == "yes"
    other, _ = check("stock_broker", "To All Regulated Entities", source="rbi")
    assert other.value != "yes"


def test_all_commercial_banks_is_not_nbfc(no_llm):
    result, meta = check("nbfc", "To All Commercial Banks")
    assert result.value == "no" and meta.method == "rule"


def test_addressees_listed_without_profile_is_no(no_llm):
    result, meta = check("research_analyst", "To All Scheduled Commercial Banks and Small Finance Banks")
    assert result.value == "no" and meta.method == "rule"
    assert result.quote in "To All Scheduled Commercial Banks and Small Finance Banks"


def test_who_field_gives_yes(no_llm):
    result, meta = check("nbfc", "Circular on fraud reporting", who="All NBFCs")
    assert result.value == "yes" and meta.method == "rule" and result.quote == BODY


def test_ambiguous_goes_to_llm_with_verified_quote(monkeypatch):
    calls = llm_says(monkeypatch, "yes", "Concerns banks' fraud reporting.", quote="Banks shall report every fraud to the Reserve Bank within 21 days")
    result, meta = check("coop_bank", "Master Direction on fraud")
    assert result.value == "yes" and meta.method == "llm" and meta.llm_calls == 1 and meta.model == "fast-m"
    assert result.quote in BODY
    assert len(calls) == 1 and calls[0][2]["model"] == "fast" and calls[0][2]["temperature"] == 0
    assert "[2]" not in calls[0][0][1]["content"]  # only the opening paragraphs go to the LLM, not the body


def test_llm_quote_not_found_is_review(monkeypatch):
    llm_says(monkeypatch, "yes", "x", quote="This sentence does not appear anywhere in the document at all.")
    result, _ = check("coop_bank", "Master Direction on fraud")
    assert (result.value, result.reason) == ("review", "could not verify the basis")


def test_llm_yes_without_quote_is_review(monkeypatch):
    llm_says(monkeypatch, "no", "x", quote=None)
    result, _ = check("coop_bank", "Master Direction on fraud")
    assert result.value == "review" and result.reason == "could not verify the basis"


def test_llm_review_passes_through(monkeypatch):
    llm_says(monkeypatch, "review", "Unclear who it covers.", quote=None)
    result, _ = check("coop_bank", "Master Direction on fraud")
    assert result.value == "review" and result.reason == "Unclear who it covers."


def test_llm_reason_truncated_to_25_words(monkeypatch):
    llm_says(monkeypatch, "review", " ".join(["word"] * 40))
    result, _ = check("coop_bank", "Master Direction on fraud")
    assert len(result.reason.split()) == 25 and result.reason.endswith("...")


def test_llm_failure_is_review(monkeypatch):
    llm_says(monkeypatch, error=LLMError("unavailable", "down"))
    result, meta = check("coop_bank", "Master Direction on fraud")
    assert (result.value, result.reason) == ("review", "AI check unavailable") and meta.llm_calls == 0


def test_unexpected_exception_never_escapes(monkeypatch):
    llm_says(monkeypatch, error=RuntimeError("boom"))
    result, _ = check("coop_bank", "Master Direction on fraud")
    assert result.value == "review"


def test_informational_other_profiles_no_without_llm(no_llm):
    for profile in ("nbfc", "coop_bank", "research_analyst", "stock_broker"):
        result, meta = check(profile, "To All NBFCs", kind="informational")
        assert (result.value, result.reason, meta.llm_calls) == ("no", "informational, no obligations", 0)


def test_informational_citizen_rule_then_llm(monkeypatch, no_llm):
    result, meta = check("citizen_msme", "Press note: scheme open to all citizens", kind="informational")
    assert result.value == "yes" and meta.method == "rule"
    llm_says(monkeypatch, "review", "Not clear whether it affects citizens.")
    result, meta = check("citizen_msme", "Press note on a bilateral meeting", kind="informational")
    assert result.value == "review" and meta.method == "llm"

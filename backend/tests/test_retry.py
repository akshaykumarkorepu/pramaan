import asyncio

import pytest

from api.schemas import Paragraph
from llm import prompts
from llm.client import CallMeta, strict_schema
from llm.errors import LLMError
from pipeline import retry as rt
from pipeline.models import ExtractedObligation
from pipeline.retry import RetryItem, RetryResponse
from test_verifier import make_doc, ob
from verify.verifier import InjectedObligation, verify

S1 = "All Urban Co-operative Banks shall file the annual return by October 27, 2026 and pay Rs. 10,00,000 as the fee."
S2 = "Banks shall report every fraud to the Reserve Bank within 21 days of detection."
FAKE_QUOTE = "All banks shall also deposit Rs. 50,00,000 with the regulator by November 1, 2026."
DOC = make_doc(("p1", "To All Urban Co-operative Banks"), ("2", S1), ("3", S2), ("4", "This circular is issued under section 35A."))
LONG = "File the annual return and also pay the fee of Rs. 10,00,000 together with all the supporting papers for the year, without any delay at all"


def meta():
    return CallMeta(model_used="fast-m", fallback_used=False, latency_ms=50, prompt_tokens=10, completion_tokens=5, attempts=1)


@pytest.fixture
def stub(monkeypatch):
    calls = []

    def install(*answers):
        async def fake(messages, schema, **kw):
            calls.append((messages, schema, kw))
            if isinstance(answers[0], BaseException):
                raise answers[0]
            return RetryResponse(items=list(answers)), meta()

        monkeypatch.setattr(rt, "call_json", fake)
        return calls

    return install


def verified(*obligations, doc=DOC):
    return verify(list(obligations), doc)[0]


def fix(id, **kw):
    return RetryItem(id=id, action="correct", obligation=ob(**kw), must_do=None)


def run(items, doc=DOC):
    return asyncio.run(rt.retry(items, doc))


def test_rejected_becomes_fixed_when_the_corrected_quote_is_valid(stub):
    items = verified(ob(quote="Banks must file the yearly return by 27 October 2026."))
    assert items[0].status == "rejected"
    calls = stub(fix(0, quote=S1, must_do="File the annual return by 27 October 2026", deadline="2026-10-27"))
    final, counts, meta_ = run(items)
    assert final[0].status == "fixed" and final[0].reason == "fixed: quote not found in source"
    assert final[0].match_span is not None and final[0].matched_text == S1
    assert (counts.fixed, counts.rejected, meta_.fixed, meta_.llm_calls) == (1, 0, 1, 1) and len(calls) == 1
    assert calls[0][2]["model"] == "fast" and calls[0][2]["temperature"] == 0


def test_rejected_stays_rejected_when_the_correction_is_still_fake(stub):
    items = verified(ob(quote="Banks must file the yearly return by 27 October 2026."))
    stub(fix(0, quote=FAKE_QUOTE))
    final, counts, _ = run(items)
    assert final[0].status == "rejected" and final[0].reason.startswith("quote not found in source (retry: ")
    assert (counts.rejected, counts.fixed) == (1, 0)


def test_a_correction_with_a_number_not_in_the_source_stays_rejected(stub):
    items = verified(ob(quote="Banks must file the yearly return by 27 October 2026."))
    stub(fix(0, quote=S1, must_do="Pay Rs. 99,00,000"))
    assert run(items)[0][0].status == "rejected"


def test_drop_removes_the_item_but_records_it(stub):
    items = verified(ob(quote="Banks must file the yearly return by 27 October 2026."), ob())
    stub(RetryItem(id=0, action="drop", obligation=None, must_do=None))
    final, counts, meta_ = run(items)
    assert [o.status for o in final] == ["verified"] and counts.rejected == 0
    assert meta_.dropped[0].quote.startswith("Banks must file") and meta_.dropped[0].reason == "quote not found in source"


def test_quality_rewrite_is_accepted_when_it_passes_the_number_check(stub):
    items = verified(ob(must_do=LONG))
    assert items[0].status == "verified"
    stub(RetryItem(id=0, action="rewrite", obligation=None, must_do="File the annual return and pay Rs. 10,00,000"))
    final, counts, meta_ = run(items)
    assert final[0].must_do == "File the annual return and pay Rs. 10,00,000" and final[0].status == "verified"
    assert meta_.rewritten == 1 and meta_.quality_sent == 1 and counts.verified == 1


def test_quality_rewrite_with_a_new_number_is_refused(stub):
    items = verified(ob(must_do=LONG))
    stub(RetryItem(id=0, action="rewrite", obligation=None, must_do="File the return and pay Rs. 25,00,000"))
    final, _, meta_ = run(items)
    assert final[0].must_do == LONG and meta_.rewritten == 0


def test_quality_rewrite_over_25_words_is_refused(stub):
    items = verified(ob(must_do=LONG))
    stub(RetryItem(id=0, action="rewrite", obligation=None, must_do=" ".join(["file"] * 26)))
    assert run(items)[0][0].must_do == LONG


def test_must_do_that_copies_the_quote_is_a_quality_item(stub):
    items = verified(ob(must_do=S1))
    calls = stub(RetryItem(id=0, action="rewrite", obligation=None, must_do="File the annual return by 27 October 2026"))
    final, _, _ = run(items)
    assert len(calls) == 1 and final[0].must_do == "File the annual return by 27 October 2026"


def test_injected_test_is_never_retried(stub):
    fake = InjectedObligation(who="T", must_do="TEST", deadline=None, effective_from=None, paragraph="2", quote=FAKE_QUOTE, penalty_or_consequence=None)
    items = verified(fake)
    calls = stub(fix(0, quote=S1))
    final, counts, meta_ = run(items)
    assert calls == [] and final == items and final[0].status == "rejected" and counts.rejected == 1 and meta_.llm_calls == 0


def test_injected_test_stays_rejected_next_to_a_retried_item(stub):
    fake = InjectedObligation(who="T", must_do="TEST", deadline=None, effective_from=None, paragraph="2", quote=FAKE_QUOTE, penalty_or_consequence=None)
    items = verified(fake, ob(quote="Banks must file the yearly return by 27 October 2026."))
    stub(fix(0, quote=S1))  # id 0 is the only problem sent, so it belongs to the second item
    final, _, _ = run(items)
    assert final[0] is items[0] and final[1].status == "fixed"


def test_llm_failure_returns_the_originals_with_a_note(stub):
    items = verified(ob(quote="Banks must file the yearly return by 27 October 2026."))
    stub(LLMError("unavailable", "The AI service is busy; try again."))
    final, counts, meta_ = run(items)
    assert final == items and counts.rejected == 1 and meta_.llm_calls == 0
    assert "originals kept" in meta_.note and "busy" in meta_.note


def test_nothing_to_fix_makes_no_call(stub):
    calls = stub()
    items = verified(ob())
    final, counts, meta_ = run(items)
    assert calls == [] and final == items and counts.verified == 1 and meta_.llm_calls == 0


def test_a_mixed_batch_makes_exactly_one_call_and_ignores_unknown_ids(stub):
    items = verified(
        ob(quote="Banks must file the yearly return by 27 October 2026."),
        ob(must_do=LONG),
        ob(quote="Banks must tell the RBI about frauds quickly, within 21 days."),
    )
    calls = stub(
        fix(0, quote=S1, must_do="File the annual return", deadline="2026-10-27"),
        RetryItem(id=1, action="rewrite", obligation=None, must_do="File the annual return and pay Rs. 10,00,000"),
        RetryItem(id=7, action="drop", obligation=None, must_do=None),
    )
    final, counts, meta_ = run(items)
    assert len(calls) == 1 and meta_.llm_calls == 1
    assert [o.status for o in final] == ["fixed", "verified", "rejected"]  # id 2 got no answer: unchanged
    assert (counts.fixed, counts.verified, counts.rejected) == (1, 1, 1)


def test_the_model_only_sees_the_relevant_paragraphs():
    paras = [Paragraph(id=str(i), text=f"Paragraph number {i} text") for i in range(1, 8)]
    items = verified(ob(quote="not in the doc at all, so it is rejected", paragraph="4"), doc=make_doc(*[(p.id, p.text) for p in paras]))
    msgs = rt.build_messages([("rejected", "x", items[0])], paras, "T")
    user = msgs[1]["content"]
    assert all(f"[{i}] " in user for i in (3, 4, 5)) and not any(f"[{i}] " in user for i in (1, 2, 6, 7))


def test_an_unknown_claimed_paragraph_falls_back_to_the_most_similar_one():
    items = verified(ob(quote=S1.replace("annual", "yearly"), paragraph="99"))
    user = rt.build_messages([("rejected", "x", items[0])], DOC.paragraphs, "T")[1]["content"]
    assert "[2] " in user


def test_the_prompt_carries_the_extract_rules_and_the_schema_is_strict_compatible():
    system = rt.build_messages([("rejected", "x", verified(ob(quote="nope nope nope nope nope nope nope"))[0])], DOC.paragraphs, "T")[0]["content"]
    assert prompts.load("extract").split("RULES", 1)[1] in system
    strict_schema(RetryResponse)  # raises if the schema can't be made strict

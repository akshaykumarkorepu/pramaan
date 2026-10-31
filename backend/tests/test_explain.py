import asyncio

import pytest

from api.schemas import Applicability, VerifiedObligation
from llm import prompts
from llm.client import CallMeta
from llm.errors import LLMError
from pipeline import explain as ex

TITLE = "Master Direction on KYC"
APPLIES = Applicability(value="yes", reason="Addressed to all Urban Co-operative Banks.")


def vo(status="verified", must_do="Complete re-KYC of high-risk customers within 30 days", deadline="2026-11-30", **kw):
    return VerifiedObligation(
        who=kw.pop("who", "All UCBs"), must_do=must_do, deadline=deadline, quote="q", status=status,
        injected_test=kw.pop("injected_test", False),
    )


def call_meta():
    return CallMeta(model_used="m", fallback_used=False, latency_ms=5, prompt_tokens=10, completion_tokens=5, attempts=1)


def stub(monkeypatch, *answers):
    """Each LLM call pops one answer (a string, or an LLMError to raise); the messages sent are recorded."""
    sent, script = [], list(answers)

    async def fake(messages, **kwargs):
        sent.append((messages, kwargs))
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, call_meta()

    monkeypatch.setattr(ex, "call_text", fake)
    return sent


def run(items, lang="en", applicability=APPLIES):
    return asyncio.run(ex.explain(TITLE, items, applicability, "coop_bank", lang))


def test_only_verified_near_fixed_are_sent(monkeypatch):
    sent = stub(monkeypatch, "This applies to you because it is addressed to UCBs. Complete the listed duties.")
    items = [
        vo("verified", must_do="Verified duty alpha"), vo("near", must_do="Near duty beta"), vo("fixed", must_do="Fixed duty gamma"),
        vo("rejected", must_do="Rejected duty delta"), vo("verified", must_do="Injected duty epsilon", injected_test=True),
    ]
    out, meta = run(items)
    prompt = " ".join(m["content"] for m in sent[0][0])
    for good in ("alpha", "beta", "gamma"):
        assert good in prompt
    for bad in ("delta", "epsilon"):
        assert bad not in prompt
    assert out.source == "llm" and meta.llm_calls == 1
    assert sent[0][1]["model"] == "primary" and sent[0][1]["temperature"] == 0.2


def test_markdown_and_emoji_stripped(monkeypatch):
    stub(monkeypatch, "## Summary\n**This applies** to you ✅\n- Complete re-KYC within `30` days.\n1. Do it by 30 November 2026.")
    out, _ = run([vo()])
    assert out.source == "llm"
    assert not any(c in out.text for c in "*#`✅\n") and "- " not in out.text
    assert "This applies to you" in out.text


def test_invented_number_regenerates_then_template(monkeypatch):
    sent = stub(monkeypatch, "Pay a fee of 500 rupees within 30 days.", "Pay a fee of 700 rupees within 30 days.")
    out, meta = run([vo()])
    assert len(sent) == 2 and meta.llm_calls == 2 and meta.regenerated
    assert out.source == "template" and meta.method == "template"
    assert "500" not in out.text and "700" not in out.text and "2026-11-30" in out.text
    assert "500" in sent[1][0][-1]["content"]  # the retry names the offending value


def test_regeneration_can_succeed(monkeypatch):
    stub(monkeypatch, "Pay 500 rupees.", "Complete re-KYC within 30 days.")
    out, meta = run([vo()])
    assert out.source == "llm" and meta.regenerated and meta.llm_calls == 2


def test_invented_date_caught(monkeypatch):
    stub(monkeypatch, "Do it by 15 December 2026.", "Do it by 15 December 2026.")
    out, _ = run([vo()])
    assert out.source == "template"


def test_dates_and_digits_compared_by_value(monkeypatch):
    stub(monkeypatch, "మీరు 30 November 2026 లోగా ౩౦ రోజుల్లో re-KYC పూర్తి చేయాలి.")
    out, _ = run([vo()], lang="te")
    assert out.source == "llm"
    assert "30 రోజుల్లో" in out.text  # Telugu digits folded to Western ones


def test_no_verified_duties_plain_text_without_llm(monkeypatch):
    sent = stub(monkeypatch)
    out, meta = run([vo("rejected")])
    assert sent == [] and out.source == "template" and "No verified duties" in out.text
    assert "original" in out.text
    hi, _ = run([], lang="hi")
    assert "verified duty" in hi.text


def test_llm_failure_gives_template(monkeypatch):
    stub(monkeypatch, LLMError("unavailable", "down"))
    out, meta = run([vo()], lang="hi")
    assert out.source == "template" and out.lang == "hi" and meta.llm_calls == 0
    assert "आप पर लागू" in out.text and "All UCBs" in out.text


def test_unexpected_error_gives_template(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr(ex, "call_text", boom)
    out, _ = run([vo()])
    assert out.source == "template"


def test_template_passes_its_own_check():
    items = [vo(), vo("near", must_do="Report 5 incidents", deadline=None)]
    text = ex.build_template("en", items, APPLIES)
    assert ex.check(text, TITLE, items, APPLIES) == []


def test_prompt_rules_present():
    p = prompts.load("explain")
    for phrase in ("one sentence saying whether this applies", "At most 120 words", "no markdown", "Keep regulatory and legal terms in English",
                   "Never add any fact", "If there are no verified duties", "Western digits"):
        assert phrase in p


# ---------------------------------------------------------------- M11: deadline phrasing

@pytest.mark.parametrize("lang,text,expected", [
    ("te", "మీరు re-KYC by 30 November 2026 పూర్తి చేయాలి.", "మీరు re-KYC 30 November 2026 లోపు పూర్తి చేయాలి."),
    ("hi", "आपको re-KYC by 30 November 2026 करना है।", "आपको re-KYC 30 November 2026 तक करना है।"),
    ("te", "Do it By 2026-11-30.", "Do it 2026-11-30 లోపు."),
    ("te", "Complete it by 30 November 2026 లోపు.", "Complete it 30 November 2026 లోపు."),  # no double suffix
    ("te", "30 November 2026 లోపు చేయాలి.", "30 November 2026 లోపు చేయాలి."),  # already right
    ("te", "Send the report by next week.", "Send the report by next week."),  # no date, untouched
    ("en", "Do it by 30 November 2026.", "Do it by 30 November 2026."),  # English keeps "by"
])
def test_fix_deadlines(lang, text, expected):
    assert ex.fix_deadlines(text, lang) == expected


def test_telugu_llm_answer_gets_the_deadline_word(monkeypatch):
    stub(monkeypatch, "ఈ circular మీకు వర్తిస్తుంది. UCBs re-KYC by 30 November 2026 పూర్తి చేయాలి.")
    out, _ = run([vo()], lang="te")
    assert out.source == "llm" and "30 November 2026 లోపు" in out.text and " by " not in out.text


# ---------------------------------------------------------------- M11: explainer must match the banner

@pytest.mark.parametrize("value", ["yes", "review", "no"])
@pytest.mark.parametrize("lang", ["en", "te", "hi"])
def test_template_opening_matches_applicability_and_lists_duties(value, lang):
    a = Applicability(value=value, reason="Addressed to FPIs.")
    text = ex.build_template(lang, [vo(who="FPIs")], a)
    assert text.startswith(ex.T[lang][value])
    assert "FPIs: Complete re-KYC" in text  # duties are listed for yes, review and no alike
    assert not ex.says_no_duties(text)
    assert ex.check(text, TITLE, [vo(who="FPIs")], a) == []


@pytest.mark.parametrize("value", ["yes", "review", "no"])
@pytest.mark.parametrize("lang", ["en", "te", "hi"])
def test_no_verified_duties_note_only_when_the_list_is_empty(value, lang):
    a = Applicability(value=value, reason="x")
    assert ex.build_template(lang, [], a) == ex.T[lang]["none"]
    assert ex.says_no_duties(ex.T[lang]["none"])


def test_openings_differ_per_value():
    for lang in ("en", "te", "hi"):
        assert len({ex.T[lang][v] for v in ("yes", "review", "no")}) == 3
    assert "not clear whether" in ex.T["en"]["review"] and "does not appear to apply" in ex.T["en"]["no"]


@pytest.mark.parametrize("lang,bad", [
    ("en", "This does not apply to you. There are no verified duties for your profile."),
    ("te", "ఈ circular మీకు వర్తించదు. verified duties ఏవీ లేవు."),
    ("hi", "यह circular आप पर लागू नहीं होता। आपके लिए कोई verified duty नहीं है।"),
])
def test_contradicting_answer_is_regenerated_then_good_one_used(monkeypatch, lang, bad):
    review = Applicability(value="review", reason="FPIs are named.")
    good = {"en": "It is not clear whether this applies to you; here is what it requires. All UCBs must complete re-KYC.",
            "te": "ఇది మీకు వర్తిస్తుందో లేదో స్పష్టంగా తెలియదు. All UCBs re-KYC పూర్తి చేయాలి.",
            "hi": "यह स्पष्ट नहीं है कि यह आप पर लागू होता है या नहीं। All UCBs को re-KYC पूरा करना है।"}[lang]
    sent = stub(monkeypatch, bad, good)
    out, meta = run([vo()], lang=lang, applicability=review)
    assert meta.llm_calls == 2 and meta.regenerated and out.source == "llm"
    assert "no verified duties" in sent[1][0][-1]["content"]


def test_contradicting_answer_twice_falls_back_to_template(monkeypatch):
    review = Applicability(value="review", reason="FPIs are named.")
    stub(monkeypatch, "There are no verified duties.", "No verified duties here.")
    out, meta = run([vo()], applicability=review)
    assert out.source == "template" and out.text.startswith(ex.T["en"]["review"]) and "All UCBs" in out.text
    assert not ex.says_no_duties(out.text)


def test_prompt_has_the_three_exact_openings():
    p = prompts.load("explain")
    for phrase in ("This applies to you because", "It is not clear whether this applies to you because",
                   "This does not appear to apply to you because", "here is what it requires of others",
                   "never say that there are none"):
        assert phrase in p


@pytest.mark.parametrize("lang,english,real", [
    ("te", "It is not clear whether this applies to you. FPIs must pay the fees.", "ఇది మీకు వర్తిస్తుందో లేదో తెలియదు. FPIs fees చెల్లించాలి."),
    ("hi", "It is not clear whether this applies to you. FPIs must pay the fees.", "यह आप पर लागू होता है या नहीं, स्पष्ट नहीं। FPIs को fees देनी है।"),
])
def test_english_answer_for_telugu_or_hindi_is_regenerated(monkeypatch, lang, english, real):
    sent = stub(monkeypatch, english, real)
    out, meta = run([vo()], lang=lang)
    assert meta.llm_calls == 2 and out.source == "llm" and out.text == real
    assert "not written in" in sent[1][0][-1]["content"]


def test_english_answer_twice_for_telugu_falls_back_to_template(monkeypatch):
    stub(monkeypatch, "This applies to you. Do re-KYC.", "This applies to you. Do re-KYC.")
    out, _ = run([vo()], lang="te")
    assert out.source == "template" and out.text.startswith(ex.T["te"]["yes"])


def test_in_language_allows_english_terms_inside_te_hi():
    assert ex.in_language("ఈ circular మీకు వర్తిస్తుంది. UCBs KYC పూర్తి చేయాలి.", "te")
    assert not ex.in_language("This circular applies to you.", "hi")
    assert ex.in_language("anything at all", "en")

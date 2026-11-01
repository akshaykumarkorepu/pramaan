"""Model split for the free Groq tier: each call site asks for the right role, and reasoning effort stays at its low default."""
import asyncio
import inspect

import pytest

from api.schemas import Applicability
from llm import client
from llm.errors import LLMError
from pipeline import applicability, explain, extract, retry
from pipeline.extract import ExtractionResult
from test_analyze import GOOD_QUOTE, PARAS, make_doc, obligation
from verify.verifier import verify


class Recorder:
    def __init__(self, monkeypatch, module, name):
        self.kwargs = None

        async def fake(*args, **kwargs):
            self.kwargs = kwargs
            raise LLMError("unavailable", "stop here")

        monkeypatch.setattr(module, name, fake)


def test_extraction_uses_the_primary_model(monkeypatch):
    rec = Recorder(monkeypatch, extract, "call_json")
    with pytest.raises(LLMError):
        asyncio.run(extract.extract(make_doc()))
    assert rec.kwargs["model"] == "primary"


def test_retry_uses_the_fast_model(monkeypatch):
    rec = Recorder(monkeypatch, retry, "call_json")
    rejected, _ = verify([obligation("This sentence was invented and is not in the notice at all.")], make_doc())
    assert rejected[0].status == "rejected"
    asyncio.run(retry.retry(rejected, make_doc()))
    assert rec.kwargs["model"] == "fast"


def test_applicability_llm_uses_the_fast_model(monkeypatch):
    rec = Recorder(monkeypatch, applicability, "call_json")
    extraction = ExtractionResult(kind="obligations", addressees=[], obligations=[])
    result = asyncio.run(applicability._ask_llm("nbfc", make_doc(), extraction, [], applicability.ApplicabilityMeta(method="llm")))
    assert rec.kwargs["model"] == "fast" and result.value == "review"


def test_explainer_stays_on_the_primary_model(monkeypatch):
    from test_explain import vo

    rec = Recorder(monkeypatch, explain, "call_text")
    asyncio.run(explain.explain("T", [vo()], Applicability(value="yes", reason="r"), "nbfc", "te"))
    assert rec.kwargs["model"] == "primary"


def test_nobody_overrides_the_low_reasoning_effort(monkeypatch):
    # the client default is "low" and none of the four call sites passes anything else
    for fn in (client.call_json, client.call_text):
        assert inspect.signature(fn).parameters["reasoning_effort"].default == "low"
    for module, name in ((extract, "call_json"), (retry, "call_json"), (applicability, "call_json"), (explain, "call_text")):
        assert "reasoning_effort" not in inspect.getsource(module), module.__name__

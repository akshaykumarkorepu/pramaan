import asyncio
import logging
from typing import Optional

import pytest
from pydantic import BaseModel, Field

from llm import client, usage_log
from llm.errors import LLMError
from llm_fakes import FakeGroq, connection_error, rate_limit, reply, status_error, timeout

KEY = "gsk_SENTINEL_not_a_real_key_123456"
PRIMARY, FAST = "openai/gpt-oss-120b", "openai/gpt-oss-20b"


class Answer(BaseModel):
    answer: str = Field(min_length=3)


class Item(BaseModel):
    who: str
    deadline: Optional[str] = None


class Out(BaseModel):
    items: list[Item]
    note: Optional[str] = None


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    monkeypatch.setenv("GROQ_MODEL_PRIMARY", PRIMARY)
    monkeypatch.setenv("GROQ_MODEL_FAST", FAST)
    usage_log.clear()


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []

    async def fake_sleep(s):
        recorded.append(s)

    monkeypatch.setattr(client, "_sleep", fake_sleep)
    return recorded


@pytest.fixture
def groq_with(monkeypatch, sleeps):
    def install(script, delay=0.0):
        fake = FakeGroq(script, delay)
        monkeypatch.setattr(client, "_client", lambda: fake)
        return fake
    return install


def json_call(**kw):
    return asyncio.run(client.call_json([{"role": "user", "content": "q"}], Answer, **kw))


def text_call(**kw):
    return asyncio.run(client.call_text([{"role": "user", "content": "q"}], **kw))


# ---------------------------------------------------------------- invalid output

def test_invalid_json_then_valid_takes_two_attempts_and_sends_the_error_back(groq_with):
    fake = groq_with([reply("not json", prompt=10), reply('{"answer": "hello"}', prompt=12, completion=7)])
    parsed, meta = json_call()
    assert parsed.answer == "hello"
    assert meta.attempts == 2 and meta.fallback_used is False and meta.model_used == PRIMARY
    assert (meta.prompt_tokens, meta.completion_tokens) == (22, 12)  # summed over both responses
    msgs = fake.calls[1]["messages"]
    assert msgs[-2] == {"role": "assistant", "content": "not json"}
    assert "not valid" in msgs[-1]["content"] and "JSON" in msgs[-1]["content"]
    assert fake.models == [PRIMARY, PRIMARY]  # same model re-asked, not a fallback


def test_pydantic_constraint_failure_is_retried_with_the_field_named(groq_with):
    fake = groq_with([reply('{"answer": "x"}'), reply('{"answer": "fine"}')])
    parsed, meta = json_call()
    assert parsed.answer == "fine" and meta.attempts == 2
    assert "answer" in fake.calls[1]["messages"][-1]["content"]


def test_invalid_twice_raises_invalid_output_with_a_user_message(groq_with):
    fake = groq_with([reply("nope"), reply("still nope")])
    with pytest.raises(LLMError) as e:
        json_call()
    assert e.value.kind == "invalid_output" and len(fake.calls) == 2
    assert "unexpected format" in str(e.value) and "Traceback" not in str(e.value)


def test_truncated_reply_is_retried_with_double_the_token_budget(groq_with):
    fake = groq_with([reply('{"answ', finish="length"), reply('{"answer": "fine"}')])
    _, meta = json_call(max_tokens=1000)
    assert [c["max_completion_tokens"] for c in fake.calls] == [1000, 2000]
    assert meta.attempts == 2


def test_empty_reply_from_reasoning_is_invalid_and_retried(groq_with):
    fake = groq_with([reply("", finish="length"), reply('{"answer": "fine"}')])
    json_call()
    assert len(fake.calls) == 2


def test_token_budget_doubling_is_capped(groq_with):
    fake = groq_with([reply("{", finish="length"), reply('{"answer": "fine"}')])
    json_call(max_tokens=client.MAX_TOKENS_CAP)
    assert fake.calls[1]["max_completion_tokens"] == client.MAX_TOKENS_CAP


# ---------------------------------------------------------------- transient errors, backoff, fallback

def test_429_twice_switches_to_the_fast_model(groq_with, sleeps):
    fake = groq_with([rate_limit(), rate_limit(), reply('{"answer": "hello"}')])
    parsed, meta = json_call()
    assert parsed.answer == "hello"
    assert fake.models == [PRIMARY, PRIMARY, FAST]
    assert sleeps == [1.0]  # one backoff before the second primary try, none when switching model
    assert meta.fallback_used is True and meta.model_used == FAST and meta.attempts == 3


def test_all_four_attempts_rate_limited_raises_rate_limit(groq_with, sleeps):
    fake = groq_with([rate_limit()] * 4)
    with pytest.raises(LLMError) as e:
        json_call()
    assert e.value.kind == "rate_limit" and "busy" in str(e.value)
    assert fake.models == [PRIMARY, PRIMARY, FAST, FAST] and sleeps == [1.0, 2.0]


@pytest.mark.parametrize("failure", [lambda: status_error(500), lambda: status_error(503), timeout, connection_error])
def test_server_errors_timeouts_and_connection_failures_are_unavailable(groq_with, failure):
    groq_with([failure() for _ in range(4)])
    with pytest.raises(LLMError) as e:
        text_call()
    assert e.value.kind == "unavailable"


def test_without_a_separate_fast_model_the_primary_gets_three_tries(groq_with, sleeps, monkeypatch):
    monkeypatch.delenv("GROQ_MODEL_FAST")
    fake = groq_with([rate_limit()] * 3)
    with pytest.raises(LLMError) as e:
        text_call()
    assert e.value.kind == "rate_limit" and fake.models == [PRIMARY] * 3 and sleeps == [1.0, 2.0]


def test_fast_equal_to_primary_is_not_treated_as_a_fallback(groq_with, monkeypatch):
    monkeypatch.setenv("GROQ_MODEL_FAST", PRIMARY)
    fake = groq_with([rate_limit()] * 3)
    with pytest.raises(LLMError):
        text_call()
    assert len(fake.calls) == 3


def test_retry_after_is_honoured_but_capped(groq_with, sleeps):
    groq_with([rate_limit(retry_after=5), reply("ok")])
    text_call()
    assert sleeps == [5.0]
    sleeps.clear()
    groq_with([rate_limit(retry_after=120), reply("ok")])
    text_call()
    assert sleeps == [client.MAX_RETRY_AFTER_S]


def test_fast_role_has_no_fallback(groq_with, sleeps):
    fake = groq_with([rate_limit()] * 3)
    with pytest.raises(LLMError):
        text_call(model="fast")
    assert fake.models == [FAST] * 3


def test_fast_fail_makes_exactly_one_attempt(groq_with, sleeps):
    fake = groq_with([rate_limit()])
    with pytest.raises(LLMError) as e:
        text_call(fast_fail=True)
    assert e.value.kind == "rate_limit" and len(fake.calls) == 1 and sleeps == []
    assert fake.calls[0]["timeout"] == client.FAST_FAIL_TIMEOUT_S


def test_fast_fail_does_not_retry_invalid_output(groq_with):
    fake = groq_with([reply("nope")])
    with pytest.raises(LLMError) as e:
        json_call(fast_fail=True)
    assert e.value.kind == "invalid_output" and len(fake.calls) == 1


# ---------------------------------------------------------------- config and fatal errors

def test_missing_api_key_is_a_config_error_and_makes_no_call(groq_with, monkeypatch):
    fake = groq_with([])
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(LLMError) as e:
        json_call()
    assert e.value.kind == "config" and "GROQ_API_KEY" in str(e.value) and fake.calls == []


def test_missing_primary_model_is_a_config_error(groq_with, monkeypatch):
    fake = groq_with([])
    monkeypatch.delenv("GROQ_MODEL_PRIMARY")
    with pytest.raises(LLMError) as e:
        text_call()
    assert e.value.kind == "config" and "GROQ_MODEL_PRIMARY" in str(e.value) and fake.calls == []


def test_missing_fast_model_is_a_config_error_for_the_fast_role(groq_with, monkeypatch):
    groq_with([])
    monkeypatch.delenv("GROQ_MODEL_FAST")
    with pytest.raises(LLMError) as e:
        text_call(model="fast")
    assert e.value.kind == "config"


@pytest.mark.parametrize("code", [400, 401, 404, 413])
def test_fatal_status_codes_are_config_errors_with_no_retry(groq_with, sleeps, code):
    fake = groq_with([status_error(code)] * 4)
    with pytest.raises(LLMError) as e:
        text_call()
    assert e.value.kind == "config" and len(fake.calls) == 1 and sleeps == []


def test_unexpected_exception_never_escapes_raw(groq_with):
    fake = groq_with([RuntimeError("boom internals")])
    with pytest.raises(LLMError) as e:
        text_call()
    assert e.value.kind == "unavailable" and "boom" not in str(e.value) and len(fake.calls) == 1


# ---------------------------------------------------------------- request shape

def test_strict_schema_is_sent_for_supported_models(groq_with):
    fake = groq_with([reply('{"items": [], "note": null}')])
    asyncio.run(client.call_json([{"role": "user", "content": "q"}], Out))
    kw = fake.calls[0]
    assert kw["model"] == PRIMARY and kw["temperature"] == 0 and kw["reasoning_effort"] == "low"
    rf = kw["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True and rf["json_schema"]["name"] == "Out"
    assert rf["json_schema"]["schema"]["additionalProperties"] is False


def test_unsupported_model_uses_json_object_mode_without_reasoning_effort(groq_with, monkeypatch):
    monkeypatch.setenv("GROQ_MODEL_PRIMARY", "some/other-model")
    fake = groq_with([reply('{"answer": "hello"}')])
    json_call()
    kw = fake.calls[0]
    assert kw["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in kw
    assert kw["messages"][0]["role"] == "system" and "JSON Schema" in kw["messages"][0]["content"]


def test_request_format_is_chosen_per_model_when_falling_back(groq_with, monkeypatch):
    monkeypatch.setenv("GROQ_MODEL_PRIMARY", "some/other-model")  # json_object mode
    fake = groq_with([rate_limit(), rate_limit(), reply('{"answer": "hello"}')])
    json_call()
    assert fake.calls[0]["response_format"]["type"] == "json_object"
    assert fake.calls[2]["response_format"]["type"] == "json_schema"  # FAST is gpt-oss: strict


def test_text_call_passes_effort_and_default_temperature(groq_with):
    fake = groq_with([reply("  hello  ")])
    text, meta = text_call(reasoning_effort="medium")
    assert text == "hello" and fake.calls[0]["reasoning_effort"] == "medium" and fake.calls[0]["temperature"] == 0.2
    assert "response_format" not in fake.calls[0]


def test_empty_text_twice_is_invalid_output(groq_with):
    groq_with([reply(""), reply("   ")])
    with pytest.raises(LLMError) as e:
        text_call()
    assert e.value.kind == "invalid_output"


# ---------------------------------------------------------------- strict_schema

def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_strict_schema_normalizes_nested_models_lists_and_optionals():
    s = client.strict_schema(Out)
    assert s["required"] == ["items", "note"] and s["additionalProperties"] is False
    item = s["$defs"]["Item"]
    assert item["required"] == ["who", "deadline"] and item["additionalProperties"] is False
    assert {"type": "null"} in item["properties"]["deadline"]["anyOf"]  # Optional stays nullable
    for node in _walk(s):
        assert "default" not in node
    assert "title" not in s


def test_strict_schema_keeps_a_field_that_is_literally_named_title_or_default():
    class Odd(BaseModel):
        title: str
        default: str

    s = client.strict_schema(Odd)
    assert set(s["properties"]) == {"title", "default"} and s["required"] == ["title", "default"]
    assert Out.model_json_schema()["properties"]["note"].get("default", "missing") is None  # raw schema had defaults


# ---------------------------------------------------------------- concurrency, logging, usage log

def test_never_more_than_four_requests_in_flight_even_across_event_loops(groq_with):
    fake = groq_with([], delay=0.03)

    async def burst():
        await asyncio.gather(*(client.call_text([{"role": "user", "content": "q"}]) for _ in range(10)))

    asyncio.run(burst())
    asyncio.run(burst())  # a second loop must get its own semaphore, not a stale one
    assert 2 <= fake.max_in_flight <= client.MAX_IN_FLIGHT
    assert len(fake.calls) == 20


def test_api_key_is_never_logged_or_put_in_an_error(groq_with, caplog):
    caplog.set_level(logging.DEBUG)
    groq_with([reply("ok")])
    text_call()
    groq_with([status_error(401)])
    with pytest.raises(LLMError) as e:
        text_call()
    groq_with([RuntimeError(f"leaky {KEY}")])  # even an exception that carries the key must not surface it
    with pytest.raises(LLMError) as e2:
        text_call()
    assert KEY not in caplog.text and KEY not in str(e.value) and KEY not in str(e2.value)
    assert "llm call ok" in caplog.text and "model=" in caplog.text  # meta is logged per call


def test_usage_log_records_successes_and_failures_without_content(groq_with):
    groq_with([reply("secret document text"), rate_limit(), rate_limit(), rate_limit(), rate_limit()])
    text_call()
    with pytest.raises(LLMError):
        text_call()
    ok, failed = usage_log.recent()[-2:]
    assert ok["kind"] == "text" and ok["error"] is None and ok["attempts"] == 1 and ok["model_used"] == PRIMARY
    assert failed["error"] == "rate_limit" and failed["attempts"] == 4
    assert "secret document text" not in str(usage_log.recent())

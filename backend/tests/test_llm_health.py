import asyncio

import pytest

from api.schemas import LLMHealth
from llm import client, health
from llm_fakes import FakeGroq, rate_limit, reply
from sources.cache import StatusCache


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GROQ_MODEL_PRIMARY", "openai/gpt-oss-120b")
    monkeypatch.setenv("GROQ_MODEL_FAST", "openai/gpt-oss-20b")
    monkeypatch.setattr(health, "_cache", StatusCache())

    async def no_sleep(_):
        pass

    monkeypatch.setattr(client, "_sleep", no_sleep)


def install(monkeypatch, script):
    fake = FakeGroq(script)
    monkeypatch.setattr(client, "_client", lambda: fake)
    return fake


def test_ping_ok_reports_the_model_used(monkeypatch):
    install(monkeypatch, [reply("ok")])
    assert asyncio.run(health.ping()) == LLMHealth(ok=True, model="openai/gpt-oss-120b")


def test_ping_is_cached(monkeypatch):
    fake = install(monkeypatch, [reply("ok")])
    asyncio.run(health.ping())
    asyncio.run(health.ping())
    assert len(fake.calls) == 1


def test_ping_failure_is_user_readable_and_makes_a_single_attempt(monkeypatch):
    fake = install(monkeypatch, [rate_limit()])
    result = asyncio.run(health.ping())
    assert result.ok is False and "busy" in result.error and result.model == "openai/gpt-oss-120b"
    assert len(fake.calls) == 1  # no retries or fallback for a health probe


def test_ping_without_key_says_what_is_missing(monkeypatch):
    install(monkeypatch, [])
    monkeypatch.delenv("GROQ_API_KEY")
    result = asyncio.run(health.ping())
    assert result.ok is False and "GROQ_API_KEY" in result.error

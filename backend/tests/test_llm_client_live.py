"""Live Groq calls. Skipped when GROQ_API_KEY isn't available (.env locally, env vars elsewhere)."""
import asyncio
import os
import re
from typing import Optional

import pytest
from pydantic import BaseModel

import config
from llm import client

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def live_env():
    config.load_env()
    if not (os.environ.get("GROQ_API_KEY") and os.environ.get("GROQ_MODEL_PRIMARY")):
        pytest.skip("GROQ_API_KEY / GROQ_MODEL_PRIMARY not set")


class Tiny(BaseModel):
    answer: str


class Duty(BaseModel):
    who: str
    deadline: Optional[str] = None


class Duties(BaseModel):
    duties: list[Duty]
    note: Optional[str] = None


def test_call_json_returns_valid_output_for_a_tiny_schema():
    parsed, meta = asyncio.run(client.call_json(
        [{"role": "user", "content": 'Reply with the answer "pong" to the question: ping?'}], Tiny
    ))
    assert isinstance(parsed, Tiny) and parsed.answer.strip()
    assert meta.model_used == os.environ["GROQ_MODEL_PRIMARY"] and meta.fallback_used is False
    assert meta.attempts == 1 and meta.latency_ms > 0 and meta.prompt_tokens > 0 and meta.completion_tokens > 0


def test_call_json_accepts_nested_optional_schemas_against_the_real_api():
    # proves strict_schema() output is what Groq actually accepts (raw Pydantic schemas get HTTP 400)
    parsed, _ = asyncio.run(client.call_json(
        [{"role": "user", "content": "List one duty: who is NBFCs, no deadline given. Leave note null."}], Duties
    ))
    assert len(parsed.duties) >= 1 and parsed.duties[0].deadline is None


def test_call_text_returns_telugu():
    text, meta = asyncio.run(client.call_text(
        [{"role": "user", "content": "Write one short sentence in Telugu about the Reserve Bank of India."}]
    ))
    assert text.strip() and re.search(r"[ఀ-౿]", text), f"no Telugu script in: {text!r}"
    assert meta.attempts == 1

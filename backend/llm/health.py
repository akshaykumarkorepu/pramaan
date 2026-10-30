"""Tiny Groq ping for /health. M3's llm/client.py will supersede this for real calls."""
import asyncio
import os

import groq

from api.schemas import LLMHealth
from sources.cache import StatusCache

_cache = StatusCache(ok_ttl=300, fail_ttl=30)


def _ping_sync(api_key: str, model: str) -> None:
    client = groq.Groq(api_key=api_key, timeout=10.0, max_retries=0)
    # reasoning_effort=low keeps gpt-oss from spending the whole budget thinking; we only need an HTTP 200
    client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "ping"}],
        max_completion_tokens=32,
        reasoning_effort="low",
    )


async def ping() -> LLMHealth:
    cached = _cache.get("ping")
    if cached:
        return cached
    model = os.environ.get("GROQ_MODEL_PRIMARY") or None
    key = os.environ.get("GROQ_API_KEY")
    if not key or not model:
        missing = "GROQ_API_KEY" if not key else "GROQ_MODEL_PRIMARY"
        result = LLMHealth(ok=False, model=model, error=f"{missing} not set")
    else:
        try:
            await asyncio.to_thread(_ping_sync, key, model)
            result = LLMHealth(ok=True, model=model)
        except groq.APIStatusError as e:
            result = LLMHealth(ok=False, model=model, error=f"Groq returned HTTP {e.status_code}")
        except groq.APIError as e:
            # message text can echo request details, so report only the exception class
            result = LLMHealth(ok=False, model=model, error=f"Groq unreachable ({type(e).__name__})")
    _cache.put("ping", result, result.ok)
    return result

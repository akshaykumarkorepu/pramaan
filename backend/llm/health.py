"""LLM health for /health: one tiny call through the real client, cached (5 min ok, 30 s failure)."""
import os

from api.schemas import LLMHealth
from llm import client
from llm.errors import LLMError
from sources.cache import StatusCache

_cache = StatusCache(ok_ttl=300, fail_ttl=30)


async def ping() -> LLMHealth:
    cached = _cache.get("ping")
    if cached:
        return cached
    try:
        # fast_fail: one attempt, no fallback, so /health reports the primary model's real state quickly
        _, meta = await client.call_text(
            [{"role": "user", "content": "Reply with: ok"}], max_tokens=256, fast_fail=True
        )
        result = LLMHealth(ok=True, model=meta.model_used)
    except LLMError as e:
        result = LLMHealth(ok=False, model=os.environ.get("GROQ_MODEL_PRIMARY") or None, error=e.message)
    _cache.put("ping", result, result.ok)
    return result

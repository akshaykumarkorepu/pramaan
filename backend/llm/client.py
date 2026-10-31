"""The only place that talks to Groq. Retry, fallback, rate-limit guard, logging and typed errors live here.

Attempt schedule for a transient failure (429, 5xx, timeout, connection error):
    primary -> (1 s) -> primary -> FAST -> (2 s) -> FAST -> LLMError
With no separate FAST model:  primary -> (1 s) -> primary -> (2 s) -> primary.
Invalid JSON gets one extra retry on the same model with the validation error included."""
import asyncio
import copy
import json
import logging
import os
import re
import time
import traceback
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Literal, TypeVar

import groq
from pydantic import BaseModel, ValidationError

from llm import usage_log
from llm.errors import LLMError

log = logging.getLogger("pramaan.llm")
T = TypeVar("T", bound=BaseModel)

Role = Literal["primary", "fast"]
Effort = Literal["low", "medium", "high"]

MAX_IN_FLIGHT = 4  # stay under Groq rate limits
REQUEST_TIMEOUT_S = 30.0
FAST_FAIL_TIMEOUT_S = 10.0
MAX_RETRY_AFTER_S = 30.0  # Groq's free tier allows 8000 tokens/min/model; waiting out the window beats failing
MAX_TOKENS_CAP = 16384
BAD_REPLY_ECHO_CHARS = 2000

# Models whose Groq endpoint supports strict JSON schema (Groq docs, checked 31 Oct 2026).
# This is a capability table only; which model is used always comes from env vars.
STRICT_JSON_MODELS = {
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "meta-models/muse-spark-open",
}


class CallMeta(BaseModel):
    model_used: str
    fallback_used: bool
    latency_ms: int  # wall time for the whole call, including backoff sleeps
    prompt_tokens: int  # summed over every response received, so it reflects real usage
    completion_tokens: int
    attempts: int  # HTTP requests made


# ---------------------------------------------------------------- config and test seams

@dataclass
class _Config:
    models: list[str]  # first is the model asked for; second (if any) is the fallback


def _config(role: Role) -> _Config:
    if not os.environ.get("GROQ_API_KEY"):
        raise LLMError("config", "The AI service isn't set up on the server (GROQ_API_KEY is missing).")
    primary, fast = os.environ.get("GROQ_MODEL_PRIMARY"), os.environ.get("GROQ_MODEL_FAST")
    if role == "fast":
        if not fast:
            raise LLMError("config", "The AI service isn't set up on the server (GROQ_MODEL_FAST is missing).")
        return _Config([fast])
    if not primary:
        raise LLMError("config", "The AI service isn't set up on the server (GROQ_MODEL_PRIMARY is missing).")
    return _Config([primary] + ([fast] if fast and fast != primary else []))


_cached_client: tuple[str, groq.Groq] | None = None


def _client() -> groq.Groq:
    """Seam for tests. max_retries=0 because retries are ours to schedule."""
    global _cached_client
    key = os.environ["GROQ_API_KEY"]
    if _cached_client is None or _cached_client[0] != key:
        _cached_client = (key, groq.Groq(api_key=key, timeout=REQUEST_TIMEOUT_S, max_retries=0))
    return _cached_client[1]


async def _sleep(seconds: float) -> None:  # replaced in tests
    await asyncio.sleep(seconds)


# One semaphore per running event loop: a module-level one would break across asyncio.run() calls in tests.
# In production there is a single loop, so this is exactly a module-level Semaphore(4).
_semaphores: dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}


def _semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    for old in [l for l in _semaphores if l.is_closed()]:
        del _semaphores[old]
    if loop not in _semaphores:
        _semaphores[loop] = asyncio.Semaphore(MAX_IN_FLIGHT)
    return _semaphores[loop]


# ---------------------------------------------------------------- schema

def strict_schema(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Pydantic schema -> what Groq's strict mode accepts: every object has additionalProperties:false and
    lists all its properties as required (Optional fields stay nullable via anyOf); defaults/titles removed."""
    schema = copy.deepcopy(model_cls.model_json_schema())

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if not isinstance(node, dict):
            return
        node.pop("default", None)
        node.pop("title", None)
        props = node.get("properties")
        if isinstance(props, dict):
            node["additionalProperties"] = False
            node["required"] = list(props)
            for sub in props.values():  # `props` holds field names, so recurse into its values only
                walk(sub)
        for key in ("$defs", "definitions"):
            for sub in node.get(key, {}).values():
                walk(sub)
        for key in ("items", "anyOf", "allOf", "oneOf", "prefixItems"):
            walk(node.get(key))

    walk(schema)
    return schema


# ---------------------------------------------------------------- one HTTP attempt

class _Transient(Exception):
    def __init__(self, error: LLMError, retry_after: float | None = None):
        super().__init__(error.message)
        self.error, self.retry_after = error, retry_after


def _redact(text: str) -> str:
    """Belt and braces: an exception message must never be able to carry the API key into a log line."""
    key = os.environ.get("GROQ_API_KEY")
    return text.replace(key, "***") if key else text


_TRY_AGAIN = re.compile(r"try again in (?:(\d+)m(?!s))?(?:([\d.]+)(ms|s))?", re.I)


def _retry_after(e: groq.APIStatusError) -> float | None:
    """Seconds Groq asks us to wait: the retry-after header, else the "Please try again in 26.6s" text."""
    try:
        return float(e.response.headers.get("retry-after"))
    except (TypeError, ValueError, AttributeError):
        pass
    m = _TRY_AGAIN.search(str(e))
    if not m or not (m.group(1) or m.group(2)):
        return None
    seconds = int(m.group(1) or 0) * 60
    if m.group(2):
        seconds += float(m.group(2)) / (1000 if m.group(3).lower() == "ms" else 1)
    return seconds


def _classify(e: groq.APIError) -> Exception:
    """_Transient -> worth retrying; LLMError -> final."""
    if isinstance(e, groq.APIStatusError):
        code, detail = e.status_code, _redact(f"HTTP {e.status_code}: {str(e)[:300]}")
        if code == 429:
            msg = "The AI service is busy right now (rate limit). Please try again in a minute."
            return _Transient(LLMError("rate_limit", msg, detail), _retry_after(e))
        if code >= 500 or code in (408, 409):
            return _Transient(LLMError("unavailable", "The AI service is temporarily unavailable. Please try again.", detail))
        if code in (401, 403):
            return LLMError("config", "The AI service rejected the server's credentials.", detail)
        if code == 404:
            return LLMError("config", "The configured AI model wasn't found on the AI service.", detail)
        if code == 413:
            return LLMError("config", "That request was too large for the AI service.", detail)
        return LLMError("config", f"The AI service rejected the request (HTTP {code}).", detail)
    # timeouts and connection failures
    return _Transient(LLMError("unavailable", "The AI service didn't respond. Please try again.", type(e).__name__))


@dataclass
class _State:
    started: float
    attempts: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    last_model: str = ""


async def _attempt(state: _State, kwargs: dict[str, Any], timeout_s: float):
    async with _semaphore():  # held for the HTTP call only, not for backoff sleeps
        state.attempts += 1
        state.last_model = kwargs["model"]
        try:
            resp = await asyncio.to_thread(_client().chat.completions.create, timeout=timeout_s, **kwargs)
        except groq.APIError as e:
            raise _classify(e)
        except Exception as e:  # SDK bug or anything unexpected: never leak it raw
            log.error("unexpected error calling Groq\n%s", _redact("".join(traceback.format_exception(e))))
            raise LLMError("unavailable", "The AI service failed unexpectedly. Please try again.", type(e).__name__)
    usage = getattr(resp, "usage", None)
    state.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
    state.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
    return resp


# ---------------------------------------------------------------- schedule

Step = tuple[str, float]  # (model, seconds to wait before this attempt)


def _plan(models: list[str], fast_fail: bool) -> list[Step]:
    if fast_fail:
        return [(models[0], 0.0)]
    if len(models) == 1:
        m = models[0]
        return [(m, 0.0), (m, 1.0), (m, 2.0)]
    primary, fast = models[0], models[1]
    return [(primary, 0.0), (primary, 1.0), (fast, 0.0), (fast, 2.0)]


def _plan_from(plan: list[Step], model: str) -> list[Step]:
    """Remaining steps starting at the first one for `model` (used when re-asking after invalid output)."""
    for i, (m, _) in enumerate(plan):
        if m == model:
            return [(m, 0.0)] + plan[i + 1:]
    return plan


async def _request(state: _State, plan: list[Step], build: Callable[[str], dict[str, Any]], timeout_s: float):
    last: LLMError | None = None
    floor = 0.0
    for model, delay in plan:
        if delay:
            await _sleep(max(delay, floor))  # honour a (capped) retry-after on the same model
        floor = 0.0
        try:
            return await _attempt(state, build(model), timeout_s), model
        except _Transient as t:
            last = t.error
            if t.retry_after:
                floor = min(t.retry_after, MAX_RETRY_AFTER_S)
    assert last is not None
    raise last


# ---------------------------------------------------------------- shared executor

class _Invalid(Exception):
    def __init__(self, reason: str, content: str = "", truncated: bool = False):
        super().__init__(reason)
        self.reason, self.content, self.truncated = reason, content, truncated


def _is_gpt_oss(model: str) -> bool:
    return model.startswith("openai/gpt-oss")


def _base_kwargs(model: str, messages: list[dict], temperature: float, effort: Effort, max_tokens: int) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }
    if _is_gpt_oss(model):  # other models reject reasoning_effort
        kw["reasoning_effort"] = effort
    return kw


def _meta(state: _State, used: str, first: str) -> CallMeta:
    return CallMeta(
        model_used=used,
        fallback_used=used != first,
        latency_ms=int((time.perf_counter() - state.started) * 1000),
        prompt_tokens=state.prompt_tokens,
        completion_tokens=state.completion_tokens,
        attempts=state.attempts,
    )


async def _execute(
    *,
    kind: str,
    role: Role,
    messages: list[dict],
    build: Callable[[str, list[dict], int], dict[str, Any]],
    parse: Callable[[str], Any],
    max_tokens: int,
    fast_fail: bool,
):
    cfg = _config(role)
    state = _State(started=time.perf_counter())
    plan = _plan(cfg.models, fast_fail)
    timeout_s = FAST_FAIL_TIMEOUT_S if fast_fail else REQUEST_TIMEOUT_S
    msgs, tokens, used = list(messages), max_tokens, cfg.models[0]
    try:
        for parse_try in range(1 if fast_fail else 2):
            resp, used = await _request(state, plan, partial(build, messages=msgs, tokens=tokens), timeout_s)
            choice = resp.choices[0]
            content, finish = (choice.message.content or ""), choice.finish_reason
            try:
                if finish == "length":
                    raise _Invalid("the reply was cut off before it was complete", content, truncated=True)
                if not content.strip():
                    raise _Invalid("the reply was empty", content)
                value = parse(content)
            except _Invalid as bad:
                if parse_try == (0 if fast_fail else 1):
                    raise LLMError(
                        "invalid_output",
                        "The AI returned an answer in an unexpected format, even after a retry. Please try again.",
                        bad.reason[:300],
                    )
                # one retry on the model that answered, error included; a cut-off reply gets twice the room
                msgs = list(messages)
                if bad.content.strip():
                    msgs.append({"role": "assistant", "content": bad.content[:BAD_REPLY_ECHO_CHARS]})
                msgs.append({
                    "role": "user",
                    "content": f"Your previous reply was not valid: {bad.reason}. Reply again, following the original instructions exactly.",
                })
                if bad.truncated:
                    tokens = min(tokens * 2, MAX_TOKENS_CAP)
                plan = _plan_from(plan, used)
                continue
            meta = _meta(state, used, cfg.models[0])
            log.info(
                "llm call ok kind=%s role=%s model=%s fallback=%s ms=%d prompt_tokens=%d completion_tokens=%d attempts=%d",
                kind, role, meta.model_used, meta.fallback_used, meta.latency_ms,
                meta.prompt_tokens, meta.completion_tokens, meta.attempts,
            )
            usage_log.record(kind, role, meta.model_dump())
            return value, meta
    except LLMError as e:
        meta = _meta(state, state.last_model or used, cfg.models[0])
        log.warning(
            "llm call failed kind=%s role=%s error=%s model=%s ms=%d attempts=%d detail=%s",
            kind, role, e.kind, meta.model_used, meta.latency_ms, meta.attempts, e.detail,
        )
        usage_log.record(kind, role, meta.model_dump(), error_kind=e.kind)
        raise
    raise AssertionError("unreachable")  # the loop always returns or raises


# ---------------------------------------------------------------- public API

async def call_json(
    messages: list[dict],
    schema: type[T],
    model: Role = "primary",
    temperature: float = 0,
    reasoning_effort: Effort = "low",
    max_tokens: int = 4096,
    *,
    fast_fail: bool = False,
) -> tuple[T, CallMeta]:
    """Structured output validated with Pydantic. Strict JSON schema where Groq supports it for the model."""
    name = re.sub(r"\W", "_", schema.__name__)[:64]

    def build(model_id: str, *, messages: list[dict], tokens: int) -> dict[str, Any]:
        kw = _base_kwargs(model_id, messages, temperature, reasoning_effort, tokens)
        if model_id in STRICT_JSON_MODELS:
            kw["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": name, "schema": strict_schema(schema), "strict": True},
            }
        else:  # no strict support: plain JSON mode, schema given in the prompt
            instruction = "Reply with only a JSON object matching this JSON Schema:\n" + json.dumps(schema.model_json_schema())
            kw["messages"] = [{"role": "system", "content": instruction}] + messages
            kw["response_format"] = {"type": "json_object"}
        return kw

    def parse(content: str) -> T:
        try:
            return schema.model_validate_json(content)
        except ValidationError as e:  # also covers malformed JSON
            problems = "; ".join(f"{'.'.join(map(str, err['loc'])) or 'root'}: {err['msg']}" for err in e.errors()[:5])
            raise _Invalid(f"it did not match the required JSON format ({problems})", content)

    return await _execute(
        kind="json", role=model, messages=messages, build=build, parse=parse, max_tokens=max_tokens, fast_fail=fast_fail
    )


async def call_text(
    messages: list[dict],
    model: Role = "primary",
    temperature: float = 0.2,
    reasoning_effort: Effort = "low",
    max_tokens: int = 2048,
    *,
    fast_fail: bool = False,
) -> tuple[str, CallMeta]:
    def build(model_id: str, *, messages: list[dict], tokens: int) -> dict[str, Any]:
        return _base_kwargs(model_id, messages, temperature, reasoning_effort, tokens)

    return await _execute(
        kind="text", role=model, messages=messages, build=build, parse=lambda c: c.strip(),
        max_tokens=max_tokens, fast_fail=fast_fail,
    )

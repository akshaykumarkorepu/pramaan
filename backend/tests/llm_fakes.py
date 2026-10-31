"""A scripted stand-in for the Groq SDK client, plus builders for its replies and errors."""
import threading
import time
from types import SimpleNamespace

import groq
import httpx

_REQ = httpx.Request("POST", "https://api.groq.test/v1/chat/completions")


def reply(content, finish="stop", prompt=10, completion=5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


def status_error(code, retry_after=None, message=None):
    headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    cls = {
        400: groq.BadRequestError, 401: groq.AuthenticationError, 404: groq.NotFoundError,
        413: groq.APIStatusError, 429: groq.RateLimitError, 500: groq.InternalServerError,
        503: groq.InternalServerError,
    }[code]
    return cls(message or f"error {code}", response=httpx.Response(code, headers=headers, request=_REQ), body=None)


def rate_limit(retry_after=None, message=None):
    return status_error(429, retry_after, message)


def timeout():
    return groq.APITimeoutError(request=_REQ)


def connection_error():
    return groq.APIConnectionError(request=_REQ)


class FakeGroq:
    """Pops one scripted item per call: a reply, or an exception to raise. Records every call's kwargs."""

    def __init__(self, script, delay=0.0):
        self.script, self.calls, self.delay = list(script), [], delay
        self.in_flight = self.max_in_flight = 0
        self._lock = threading.Lock()
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        with self._lock:
            self.calls.append(kwargs)
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            item = self.script.pop(0) if self.script else reply("ok")
        try:
            if self.delay:
                time.sleep(self.delay)
            if isinstance(item, BaseException):
                raise item
            return item
        finally:
            with self._lock:
                self.in_flight -= 1

    @property
    def models(self):
        return [c["model"] for c in self.calls]

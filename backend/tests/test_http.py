import asyncio

import httpx
import pytest

from sources import http
from sources.http import FetchError, get


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_):
        pass
    monkeypatch.setattr(http.asyncio, "sleep", instant)


def run(handler):
    return asyncio.run(get("https://example.test/x", "RBI", transport=httpx.MockTransport(handler)))


def test_retries_twice_then_readable_error():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(FetchError, match=r"RBI unreachable, retried 2 times \(HTTP 503\)"):
        run(handler)
    assert len(calls) == 3  # first try + 2 retries


def test_succeeds_after_one_failure():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(500) if len(calls) == 1 else httpx.Response(200, text="ok")

    assert run(handler).text == "ok"
    assert len(calls) == 2


def test_timeout_is_reported_as_timeout():
    def handler(req):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(FetchError, match="timeout"):
        run(handler)


def test_4xx_is_not_retried():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(403)

    with pytest.raises(FetchError, match="HTTP 403"):
        run(handler)
    assert len(calls) == 1


def test_sends_browser_user_agent():
    seen = {}

    def handler(req):
        seen["ua"] = req.headers["user-agent"]
        return httpx.Response(200)

    run(handler)
    assert "Mozilla" in seen["ua"]

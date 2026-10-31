"""Shared HTTP helper: every external call gets a 10 s timeout, 2 retries, a browser User-Agent
and a user-readable error. Tracebacks never leave this module."""
import asyncio
from collections.abc import Callable

import httpx

# Gov sites sometimes reject non-browser agents.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT_S = 10.0
RETRIES = 2
BACKOFF_S = (0.5, 1.0)


class FetchError(Exception):
    """Carries a message that is safe to show to the user."""


async def get(
    url: str,
    label: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    host_check: Callable[[str], None] | None = None,
) -> httpx.Response:
    """GET `url`; retry on timeouts, network errors and 5xx. 4xx is final (retrying won't help).
    `label` is the human name used in errors, e.g. "RBI". `transport` is only for tests.
    `host_check(url)` runs before every request, including redirect hops, and may raise to stop it."""
    last = "unknown error"

    async def _before_request(request: httpx.Request) -> None:
        host_check(str(request.url))

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_S,
        follow_redirects=True,
        transport=transport,
        event_hooks={"request": [_before_request]} if host_check else {},
    ) as client:
        for attempt in range(RETRIES + 1):
            try:
                resp = await client.get(url)
            except httpx.TimeoutException:
                last = "timeout"
            except httpx.HTTPError as e:
                last = f"network error ({type(e).__name__})"
            else:
                if resp.status_code < 400:
                    return resp
                if resp.status_code < 500:
                    raise FetchError(f"{label} refused the request (HTTP {resp.status_code})")
                last = f"HTTP {resp.status_code}"
            if attempt < RETRIES:
                await asyncio.sleep(BACKOFF_S[attempt])
    raise FetchError(f"{label} unreachable, retried {RETRIES} times ({last})")

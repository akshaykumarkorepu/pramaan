"""Small in-memory status cache: successes live 5 min, failures only 30 s so recovery shows up quickly."""
from typing import Any

from cachetools import TTLCache


class StatusCache:
    def __init__(self, ok_ttl: int = 300, fail_ttl: int = 30, maxsize: int = 32):
        self._ok: TTLCache = TTLCache(maxsize=maxsize, ttl=ok_ttl)
        self._fail: TTLCache = TTLCache(maxsize=maxsize, ttl=fail_ttl)

    def get(self, key: str) -> Any | None:
        return self._ok.get(key) or self._fail.get(key)

    def put(self, key: str, value: Any, ok: bool) -> None:
        self._ok.pop(key, None)
        self._fail.pop(key, None)
        (self._ok if ok else self._fail)[key] = value

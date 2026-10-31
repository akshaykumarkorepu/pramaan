"""In-memory ring buffer of per-call LLM usage (no message content). Feeds the Evidence page later."""
from collections import deque
from datetime import datetime, timezone
from typing import Any

_records: deque[dict[str, Any]] = deque(maxlen=500)


def record(kind: str, role: str, meta: dict[str, Any], error_kind: str | None = None) -> None:
    _records.append({"at": datetime.now(timezone.utc).isoformat(), "kind": kind, "role": role, "error": error_kind, **meta})


def recent(n: int = 50) -> list[dict[str, Any]]:
    return list(_records)[-n:]


def clear() -> None:
    _records.clear()

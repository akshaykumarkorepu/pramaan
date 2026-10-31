"""Typed LLM errors. The API layer only ever sees LLMError; `str(err)` is always safe to show to the user."""
from typing import Literal

Kind = Literal["rate_limit", "invalid_output", "unavailable", "config"]


class LLMError(Exception):
    def __init__(self, kind: Kind, message: str, detail: str | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.detail = detail  # raw status / provider text, for logs only, never shown to users

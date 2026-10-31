"""API models. Mirrors frontend/lib/types.ts; change both together. M1 only needs the /health models."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

SourceId = Literal["rbi", "sebi", "pib"]


class Paragraph(BaseModel):
    id: str  # the document's own numbering ("2", "2.1", "3.1(a)") or "p<index>" when unnumbered
    text: str  # original numbering stays in the text


class SourceHealth(BaseModel):
    # ok = feed has items AND the newest item's page could be fetched
    ok: bool
    last_fetch: Optional[datetime] = None
    count: int = 0
    error: Optional[str] = None  # user-readable, e.g. "RBI unreachable, retried 2 times (timeout)"


class LLMHealth(BaseModel):
    ok: bool
    model: Optional[str] = None  # value of GROQ_MODEL_PRIMARY
    error: Optional[str] = None


class HealthResponse(BaseModel):
    sources: dict[SourceId, SourceHealth]
    llm: LLMHealth

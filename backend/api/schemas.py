"""API models. Mirrors frontend/lib/types.ts; change both together. M1 only needs the /health models."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

SourceId = Literal["rbi", "sebi", "pib"]
ProfileId = Literal["nbfc", "coop_bank", "research_analyst", "stock_broker", "citizen_msme"]
Applies = Literal["yes", "no", "review"]
Lang = Literal["en", "te", "hi"]


class Paragraph(BaseModel):
    id: str  # the document's own numbering ("2", "2.1", "3.1(a)") or "p<index>" when unnumbered
    text: str  # original numbering stays in the text


ObligationStatus = Literal["verified", "near", "rejected", "fixed"]  # "fixed" is set by the M6 retry


class MatchSpan(BaseModel):
    start: int  # offsets into the document's full_text
    end: int
    paragraph: str  # id of the paragraph where the match starts
    para_start: int  # the same span as offsets inside that paragraph's own text (for highlighting)
    para_end: int


class VerifiedObligation(BaseModel):
    who: str
    must_do: str
    deadline: Optional[str] = None
    effective_from: Optional[str] = None
    paragraph: Optional[str] = None  # corrected to where the quote was actually found
    quote: str
    penalty_or_consequence: Optional[str] = None
    status: ObligationStatus
    reason: Optional[str] = None  # set when rejected
    match_span: Optional[MatchSpan] = None
    matched_text: Optional[str] = None  # the source text the quote matched (differs from quote for "near")
    score: Optional[float] = None  # 100 for exact; the fuzzy score otherwise
    paragraph_corrected: bool = False
    injected_test: bool = False  # true only for the verifier_test=1 fake claim


class Applicability(BaseModel):
    value: Applies
    reason: str
    quote: Optional[str] = None  # always text found in the document (checked by the M5 matcher)


class Explainer(BaseModel):
    lang: Lang
    text: str
    source: Literal["llm", "template"] = "llm"  # "template" = built in code from the verified items (LLM failed the check)


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


class RuntimeHealth(BaseModel):
    # ok = the document pipeline imports (catches a broken pdfplumber/selectolax install); no network involved
    ok: bool
    error: Optional[str] = None


class HealthResponse(BaseModel):
    sources: dict[SourceId, SourceHealth]
    llm: LLMHealth
    runtime: RuntimeHealth

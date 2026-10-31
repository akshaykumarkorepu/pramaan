"""The extraction output models. Kept apart from pipeline/extract.py so verify/ can use them without importing the LLM client."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ExtractedObligation(BaseModel):
    who: str = Field(description="The party exactly as the document names it")
    must_do: str = Field(description="Plain-English summary of the duty, at most 25 words")
    deadline: Optional[str] = Field(description="YYYY-MM-DD if an explicit date is in the quote, else null")
    effective_from: Optional[str] = Field(description="YYYY-MM-DD if an explicit date is in the quote, else null")
    paragraph: Optional[str] = Field(description="The [id] of the paragraph the quote comes from")
    quote: str = Field(description="Exact contiguous copy of at most 2 sentences from the document")
    penalty_or_consequence: Optional[str] = Field(description="Only if the document states one, else null")


class ExtractionResult(BaseModel):
    kind: Literal["obligations", "informational"]
    addressees: list[str]
    obligations: list[ExtractedObligation]

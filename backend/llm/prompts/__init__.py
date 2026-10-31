"""Prompt files (llm/prompts/*.md). They are plain text so the rules can be read and edited without touching code."""
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def load(name: str) -> str:
    return (Path(__file__).parent / f"{name}.md").read_text(encoding="utf-8").strip()

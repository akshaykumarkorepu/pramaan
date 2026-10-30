"""M1 Groq smoke test: explain the newest live RBI notice title in Telugu and Hindi.
Smoke test only: output is printed, never saved. The real explainer (M8) works from verified items only.
Run from backend/:  python scripts/groq_smoke.py"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import groq  # noqa: E402

import config  # noqa: E402
from sources.feeds import fetch_feed, newest  # noqa: E402

LANGS = {"Telugu": "Telugu (తెలుగు)", "Hindi": "Hindi (हिन्दी)"}


def explain(client: groq.Groq, model: str, title: str, lang: str) -> None:
    prompt = (
        f"Explain the title of this Indian regulator notice in simple {lang}, in about 60 words. "
        f"Write only in {lang}, except for names and abbreviations such as RBI.\n\nTitle: {title}"
    )
    start = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        # gpt-oss spends completion tokens on reasoning, and Telugu tokenizes heavily, so leave headroom
        max_completion_tokens=2048,
        reasoning_effort="low",
    )
    ms = int((time.perf_counter() - start) * 1000)
    text = (resp.choices[0].message.content or "").strip()
    u = resp.usage
    print(f"--- {lang} ---")
    print(f"model={resp.model} latency={ms}ms tokens: prompt={u.prompt_tokens} completion={u.completion_tokens} total={u.total_tokens}")
    if not text:
        print(f"WARNING: empty content (finish_reason={resp.choices[0].finish_reason})")
    print(text, "\n")


async def main() -> int:
    config.load_env()
    key, model = os.environ.get("GROQ_API_KEY"), os.environ.get("GROQ_MODEL_PRIMARY")
    if not key or not model:
        print("Set GROQ_API_KEY and GROQ_MODEL_PRIMARY in .env")
        return 1
    feed = await fetch_feed("rbi")
    if not feed.ok:
        print(f"Could not fetch the RBI feed: {feed.error}")
        return 1
    title = newest(feed.items).title
    print(f"Newest live RBI notice title: {title}\n")
    client = groq.Groq(api_key=key, timeout=30.0)
    try:
        for lang in LANGS.values():
            explain(client, model, title, lang)
    except groq.APIError as e:
        # print the class and status only; never the key or request details
        print(f"Groq call failed: {type(e).__name__} {getattr(e, 'status_code', '')}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

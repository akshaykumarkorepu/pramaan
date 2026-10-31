"""GET /tts (gTTS voice for Telugu/Hindi/English) and GET /ics (verified deadlines as a calendar file)."""
import asyncio
import hashlib
import logging
from io import BytesIO
from typing import get_args

from cachetools import TTLCache
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from gtts import gTTS

from api.analyze import run_analysis
from api.routes_notices import notice_id
from api.schemas import ProfileId, ResultEvent
from pipeline.ics_export import build_calendar
from sources.allowlist import check_allowed
from sources.errors import DocumentError

log = logging.getLogger("pramaan.media")
router = APIRouter()

MAX_TTS_CHARS = 1200
TTS_LANGS = ("en", "te", "hi")
_audio: TTLCache = TTLCache(maxsize=64, ttl=30 * 60)


def _error(message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _synthesize(text: str, lang: str) -> bytes:
    """Blocking (gTTS makes an HTTP call to Google). Run in a thread."""
    buf = BytesIO()
    gTTS(text=text, lang=lang).write_to_fp(buf)
    return buf.getvalue()


@router.get("/tts")
async def tts(text: str = "", lang: str = "en"):
    text = text.strip()
    if lang not in TTS_LANGS:
        return _error("Choose English, Telugu or Hindi.", 400)
    if not text:
        return _error("There is no text to read aloud.", 400)
    if len(text) > MAX_TTS_CHARS:
        return _error(f"That text is too long to read aloud ({len(text)} characters; the limit is {MAX_TTS_CHARS}). Try a shorter part.", 400)
    key = hashlib.sha256(f"{lang}\0{text}".encode()).hexdigest()
    audio = _audio.get(key)
    if audio is None:
        try:
            audio = await asyncio.to_thread(_synthesize, text, lang)
        except Exception:
            log.exception("gTTS failed (lang=%s, %d chars)", lang, len(text))
            return _error("The voice service isn't available right now. Please read the text instead.", 503)
        _audio[key] = audio
    return Response(audio, media_type="audio/mpeg")


@router.get("/ics")
async def ics(url: str = "", profile: str = ""):
    try:
        source = check_allowed(url or "")
    except DocumentError as e:
        return _error(str(e), 400)
    if profile not in get_args(ProfileId):
        return _error("Choose who you are (NBFC, co-operative bank, research analyst, stock broker or citizen/MSME) first.", 400)
    url = url.strip()
    result = await run_analysis(url, profile)  # type: ignore[arg-type]  # cached /analyze work is reused
    if not isinstance(result, ResultEvent):
        return _error(result.message, 502)
    text, count = build_calendar(result, url)
    return Response(
        text,
        media_type="text/calendar; charset=utf-8",
        headers={
            "X-Pramaan-Events": str(count),
            "Content-Disposition": f'attachment; filename="pramaan-{source}-{notice_id(url)}.ics"',
        },
    )

"""GET /warm/status (what the background pre-analysis is doing) and GET /doc (a cached document's paragraphs)."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api import analyze
from pipeline import warmer
from sources.allowlist import check_allowed
from sources.errors import DocumentError

router = APIRouter()


@router.get("/warm/status")
async def warm_status():
    return {
        "running": warmer.state.running,
        "queued": warmer.state.queued,
        "cached_count": analyze.cached_count(),
        "last_run_at": warmer.state.last_run_at.isoformat().replace("+00:00", "Z") if warmer.state.last_run_at else None,
    }


@router.get("/doc")
async def document(url: str = ""):
    """The official text of an already analysed document, straight from the cache (never fetches or re-analyses)."""
    try:
        check_allowed(url or "")
    except DocumentError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    doc = analyze.cached_document(url.strip())
    if doc is None:
        return JSONResponse({"error": "That notice is not in the cache any more. Open it again to read it."}, status_code=404)
    return doc

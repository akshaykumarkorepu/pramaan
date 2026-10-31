"""Environment loading. Secrets come from .env locally and from the Render dashboard in production."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"


def load_env() -> None:
    # override=False: real environment variables (Render) always win over a local .env file
    load_dotenv(_ROOT_ENV, override=False)


def allowed_origins() -> list[str]:
    """ALLOWED_ORIGIN may hold several origins separated by commas (local dev + the Vercel URL)."""
    raw = os.environ.get("ALLOWED_ORIGIN", "http://localhost:3000")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def setup_logging() -> None:
    """uvicorn only configures its own loggers, so without this our INFO lines (one per LLM call) are dropped."""
    app_log = logging.getLogger("pramaan")
    if not app_log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        app_log.addHandler(handler)
    app_log.setLevel(logging.INFO)

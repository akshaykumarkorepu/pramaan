"""Environment loading. Secrets come from .env locally and from the Render dashboard in production."""
import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"


def load_env() -> None:
    # override=False: real environment variables (Render) always win over a local .env file
    load_dotenv(_ROOT_ENV, override=False)


def allowed_origin() -> str:
    return os.environ.get("ALLOWED_ORIGIN", "http://localhost:3000")

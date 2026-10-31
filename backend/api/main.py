from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config

config.load_env()  # must run before anything reads os.environ
config.setup_logging()

from api.routes_health import router as health_router  # noqa: E402

app = FastAPI(title="Pramaan API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.allowed_origin()],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(health_router)

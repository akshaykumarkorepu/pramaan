from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config

config.load_env()  # must run before anything reads os.environ
config.setup_logging()

from api.analyze import router as analyze_router  # noqa: E402
from api.routes_health import router as health_router  # noqa: E402
from api.routes_media import router as media_router  # noqa: E402
from api.routes_notices import router as notices_router  # noqa: E402

app = FastAPI(title="Pramaan API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins(),
    allow_methods=["GET"],
    allow_headers=["*"],
    expose_headers=["X-Pramaan-Events", "Content-Disposition"],  # so the browser can read the .ics filename and count
)
app.include_router(health_router)
app.include_router(analyze_router)
app.include_router(notices_router)
app.include_router(media_router)

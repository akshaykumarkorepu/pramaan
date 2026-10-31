import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config

config.load_env()  # must run before anything reads os.environ
config.setup_logging()

from api.analyze import router as analyze_router  # noqa: E402
from api.routes_health import router as health_router  # noqa: E402
from api.routes_media import router as media_router  # noqa: E402
from api.routes_notices import router as notices_router  # noqa: E402
from api.routes_notices import warm_cache  # noqa: E402

WARM_EVERY_S = 600  # same as the /notices cache TTL, so a visitor almost always finds it warm


async def _keep_notices_warm() -> None:
    while True:
        await warm_cache()  # never raises
        await asyncio.sleep(WARM_EVERY_S)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_keep_notices_warm())  # in the background: startup is never blocked by slow feeds
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Pramaan API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins(),
    allow_origin_regex=config.VERCEL_ORIGIN_REGEX,
    allow_methods=["GET"],
    allow_headers=["*"],
    expose_headers=["X-Pramaan-Events", "Content-Disposition"],  # so the browser can read the .ics filename and count
)
app.include_router(health_router)
app.include_router(analyze_router)
app.include_router(notices_router)
app.include_router(media_router)

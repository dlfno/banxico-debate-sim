from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routes.agents import router as agents_router
from .routes.auth import router as auth_router
from .routes.chat import router as chat_router
from .routes.config import router as config_router
from .routes.meeting import router as meeting_router
from .routes.version import router as version_router
from .routes.world_map import router as world_map_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Banxico Sim", version="0.1.0", lifespan=lifespan)

# init_db at import time too, so things like TestClient and direct ASGI usage
# without explicit lifespan still get a populated database.
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True, "provider": settings.PROVIDER, "model": settings.MODEL}


# All API routes live under /api so a single Docker image can serve the SPA at /.
app.include_router(auth_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(meeting_router, prefix="/api")
app.include_router(version_router, prefix="/api")
app.include_router(world_map_router, prefix="/api")


# Serve the built frontend (when present, e.g. inside the production image).
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir() and (STATIC_DIR / "index.html").is_file():
    INDEX = STATIC_DIR / "index.html"
    if (STATIC_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(INDEX)

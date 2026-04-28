from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routes.agents import router as agents_router
from .routes.chat import router as chat_router
from .routes.meeting import router as meeting_router


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


app.include_router(agents_router)
app.include_router(chat_router)
app.include_router(meeting_router)

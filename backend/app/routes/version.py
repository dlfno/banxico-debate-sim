"""Endpoint público de información de versión y build.

Permite al frontend mostrar qué commit está corriendo y cuándo se desplegó.
Los valores `GIT_COMMIT`, `GIT_COMMIT_DATE` y `BUILD_TIME` se inyectan en el
contenedor vía build-args del Dockerfile (ver `deploy.sh`).

Sin auth: es info no sensible y útil tanto para usuarios como para soporte.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/version", tags=["version"])

# Hora de arranque del proceso. Útil cuando GIT_COMMIT/BUILD_TIME no se
# inyectaron (ej. desarrollo local sin deploy.sh).
_PROCESS_STARTED_AT = datetime.now(timezone.utc)


@router.get("")
def get_version() -> dict:
    return {
        "git_commit": os.environ.get("GIT_COMMIT", "unknown"),
        "git_commit_date": os.environ.get("GIT_COMMIT_DATE", "unknown"),
        "build_time": os.environ.get("BUILD_TIME", "unknown"),
        "process_started_at": _PROCESS_STARTED_AT.isoformat(),
    }

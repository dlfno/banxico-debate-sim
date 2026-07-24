"""Configuración pública de la instancia.

Sin auth: el frontend la consulta antes del login para adaptar la UI —
mostrar el acceso de invitado y los avisos de demo cuando `DEMO_MODE` está
activo, y ocultar el registro cuando `ALLOW_REGISTRATION` está apagado.
Solo expone flags no sensibles (nunca API keys ni secretos).
"""
from __future__ import annotations

from fastapi import APIRouter

from ..config import settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
def get_config() -> dict:
    return {
        "demo_mode": settings.DEMO_MODE,
        # En demo el registro queda bloqueado sin importar ALLOW_REGISTRATION:
        # la única puerta de entrada es el acceso de invitado.
        "allow_registration": settings.ALLOW_REGISTRATION and not settings.DEMO_MODE,
    }

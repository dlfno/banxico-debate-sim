"""Endpoint del mapa mundial: indicadores macro por país (World Bank),
rutas del petróleo y conflictos. Requiere autenticación."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import current_user
from ..models import User
from ..world_data import get_world_map_data

router = APIRouter(prefix="/world-map", tags=["world-map"])


@router.get("")
def world_map(_user: User = Depends(current_user)) -> dict:
    return get_world_map_data()

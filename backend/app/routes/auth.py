from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_access_token, current_user, hash_password, verify_password
from ..config import settings
from ..db import get_session
from ..models import User
from ..schemas import AuthOut, LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut, status_code=201)
def register(body: RegisterIn, session: Session = Depends(get_session)):
    # En el demo público solo existe el acceso de invitado (/auth/demo).
    if settings.DEMO_MODE or not settings.ALLOW_REGISTRATION:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registro deshabilitado")

    username = body.username.strip().lower()
    existing = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese usuario ya existe")

    user = User(
        username=username,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token(user.id)
    return AuthOut(token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthOut)
def login(body: LoginIn, session: Session = Depends(get_session)):
    username = body.username.strip().lower()
    user = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña inválidos")
    token = create_access_token(user.id)
    return AuthOut(token=token, user=UserOut.model_validate(user))


@router.post("/demo", response_model=AuthOut, status_code=201)
def demo_login(session: Session = Depends(get_session)):
    """Acceso de invitado en un clic, solo disponible con DEMO_MODE activo.

    Crea un usuario efímero con contraseña aleatoria irrecuperable: sirve para
    entrar a explorar el demo sin fricción de registro, pero no para volver a
    iniciar sesión (el token JWT emitido es la única credencial).
    """
    if not settings.DEMO_MODE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acceso de invitado solo disponible en modo demo")

    suffix = secrets.token_hex(3)
    user = User(
        username=f"invitado-{suffix}",
        display_name=f"Invitado {suffix[:4]}",
        password_hash=hash_password(secrets.token_urlsafe(24)),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token(user.id)
    return AuthOut(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut.model_validate(user)

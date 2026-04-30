from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Query, WebSocket, status
from sqlalchemy.orm import Session

from .config import settings
from .db import get_session
from .models import User

_ALG = "HS256"
_BCRYPT_MAX_BYTES = 72


def _truncate(password: str) -> bytes:
    """bcrypt only uses the first 72 bytes; truncate explicitly so longer
    passwords don't raise from the underlying library."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_truncate(password), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.JWT_EXPIRES_HOURS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALG)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALG])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido") from exc


def current_user(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta header Authorization Bearer")
    token = authorization.split(" ", 1)[1].strip()
    user_id = decode_access_token(token)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado")
    return user


async def authenticate_ws(ws: WebSocket, token: Optional[str]) -> Optional[User]:
    """Validate token from a WS query param. Closes the socket and returns None on failure."""
    if not token:
        await ws.close(code=4401)
        return None
    try:
        user_id = decode_access_token(token)
    except HTTPException:
        await ws.close(code=4401)
        return None
    from .db import SessionLocal

    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            await ws.close(code=4401)
            return None
        # Detach so caller can use without an open session.
        session.expunge(user)
        return user

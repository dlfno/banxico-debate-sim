from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..auth import authenticate_ws, current_user
from ..chat import handle_user_turn
from ..db import SessionLocal, get_session
from ..models import Agent, ChatSession, Message, User
from ..schemas import (
    ChatSessionCreate,
    ChatSessionOut,
    ChatSessionSummary,
    MessageOut,
    UserOut,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionOut)
def create_session(
    body: ChatSessionCreate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    agent = session.get(Agent, body.agent_id)
    if agent is None:
        raise HTTPException(404, "Agente no encontrado")
    cs = ChatSession(agent_id=agent.id, created_by_id=user.id)
    session.add(cs)
    session.commit()
    session.refresh(cs)
    return ChatSessionOut(
        id=cs.id,
        agent_id=cs.agent_id,
        started_at=cs.started_at,
        created_by=UserOut.model_validate(user),
    )


@router.get("/sessions", response_model=list[ChatSessionSummary])
def list_sessions(_user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = (
        session.execute(
            select(
                ChatSession,
                Agent.display_name,
                Agent.avatar,
                User,
                func.count(Message.id).label("msg_count"),
                func.max(Message.created_at).label("last_at"),
            )
            .join(Agent, Agent.id == ChatSession.agent_id)
            .join(User, User.id == ChatSession.created_by_id)
            .outerjoin(Message, Message.chat_session_id == ChatSession.id)
            .group_by(ChatSession.id, Agent.display_name, Agent.avatar, User.id)
            .order_by(desc(func.coalesce(func.max(Message.created_at), ChatSession.started_at)))
        )
        .all()
    )
    return [
        ChatSessionSummary(
            id=cs.id,
            agent_id=cs.agent_id,
            agent_name=agent_name,
            agent_avatar=agent_avatar,
            started_at=cs.started_at,
            last_message_at=last_at,
            message_count=msg_count,
            created_by=UserOut.model_validate(creator),
        )
        for (cs, agent_name, agent_avatar, creator, msg_count, last_at) in rows
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(
    session_id: int,
    _user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    cs = session.get(ChatSession, session_id)
    if cs is None:
        raise HTTPException(404, "Sesión no encontrada")
    return (
        session.execute(
            select(Message)
            .where(Message.chat_session_id == session_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        .scalars()
        .all()
    )


@router.websocket("/ws/{session_id}")
async def chat_ws(ws: WebSocket, session_id: int, token: str | None = Query(None)):
    user = await authenticate_ws(ws, token)
    if user is None:
        return
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "JSON inválido"})
                continue
            if data.get("type") != "user" or not data.get("content"):
                await ws.send_json({"type": "error", "message": "Se esperaba {type:'user', content:'...'}"})
                continue

            async def emit(ev: dict) -> None:
                await ws.send_json(ev)

            db = SessionLocal()
            try:
                await handle_user_turn(db, session_id, data["content"], emit)
            except Exception as exc:
                await ws.send_json({"type": "error", "message": str(exc)})
            finally:
                db.close()
    except WebSocketDisconnect:
        return

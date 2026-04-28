from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..chat import handle_user_turn
from ..db import SessionLocal, get_session
from ..models import Agent, ChatSession, Message
from ..schemas import ChatSessionCreate, ChatSessionOut, MessageOut

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionOut)
def create_session(body: ChatSessionCreate, session: Session = Depends(get_session)):
    agent = session.get(Agent, body.agent_id)
    if agent is None:
        raise HTTPException(404, "Agente no encontrado")
    cs = ChatSession(agent_id=agent.id)
    session.add(cs)
    session.commit()
    session.refresh(cs)
    return cs


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(session_id: int, session: Session = Depends(get_session)):
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
async def chat_ws(ws: WebSocket, session_id: int):
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

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..auth import authenticate_ws, current_user
from ..config import settings
from ..db import SessionLocal, get_session
from ..debate import run_meeting
from ..demo import run_meeting_demo
from ..models import Agent, Meeting, Message, User, Vote
from ..schemas import MeetingCreate, MeetingOut, MeetingSummary, MessageOut, UserOut, VoteOut

router = APIRouter(prefix="/meetings", tags=["meetings"])


_active_runs: dict[int, dict] = {}


@router.post("", response_model=MeetingOut)
def create_meeting(
    body: MeetingCreate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    if body.agent_ids:
        agents = session.execute(select(Agent).where(Agent.id.in_(body.agent_ids))).scalars().all()
    else:
        agents = session.execute(select(Agent).order_by(Agent.id.asc())).scalars().all()
    if len(agents) < 2:
        raise HTTPException(400, "Se requieren al menos 2 agentes")

    meeting = Meeting(topic=body.topic, created_by_id=user.id)
    session.add(meeting)
    session.commit()
    session.refresh(meeting)

    _active_runs[meeting.id] = {"agent_ids": [a.id for a in agents], "rounds": body.rounds, "queue": asyncio.Queue()}
    return _meeting_out(session, meeting)


@router.get("", response_model=list[MeetingSummary])
def list_meetings(_user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = (
        session.execute(
            select(Meeting, User)
            .join(User, User.id == Meeting.created_by_id)
            .order_by(desc(Meeting.started_at))
        )
        .all()
    )
    return [
        MeetingSummary(
            id=m.id,
            topic=m.topic,
            started_at=m.started_at,
            ended_at=m.ended_at,
            decision_bps=m.decision_bps,
            created_by=UserOut.model_validate(creator),
        )
        for (m, creator) in rows
    ]


@router.get("/{meeting_id}", response_model=MeetingOut)
def get_meeting(
    meeting_id: int,
    _user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    meeting = session.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Junta no encontrada")
    return _meeting_out(session, meeting)


@router.delete("/{meeting_id}", status_code=200)
def delete_meeting(
    meeting_id: int,
    _user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    meeting = session.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(404, "Junta no encontrada")
    _active_runs.pop(meeting_id, None)
    session.delete(meeting)
    session.commit()
    return {"deleted": True}


@router.websocket("/ws/{meeting_id}")
async def meeting_ws(ws: WebSocket, meeting_id: int, token: str | None = Query(None)):
    user = await authenticate_ws(ws, token)
    if user is None:
        return
    await ws.accept()
    cfg = _active_runs.get(meeting_id)
    if cfg is None:
        await ws.send_json({"type": "error", "message": "La junta no existe o ya terminó"})
        await ws.close()
        return

    queue: asyncio.Queue = cfg["queue"]

    async def emit(ev: dict) -> None:
        await queue.put(ev)
        await ws.send_json(ev)

    db = SessionLocal()

    async def runner():
        try:
            if settings.DEMO_MODE:
                # Deploy público $0: reproduce un debate pre-generado sin LLM.
                await run_meeting_demo(db, meeting_id, cfg["agent_ids"], emit)
            else:
                await run_meeting(db, meeting_id, cfg["rounds"], cfg["agent_ids"], emit)
        except Exception as exc:
            try:
                await ws.send_json({"type": "error", "message": str(exc)})
            except Exception:
                pass
        finally:
            db.close()
            _active_runs.pop(meeting_id, None)

    task = asyncio.create_task(runner())
    try:
        await task
    except WebSocketDisconnect:
        task.cancel()


def _meeting_out(session: Session, meeting: Meeting) -> MeetingOut:
    creator = session.get(User, meeting.created_by_id)
    votes = session.execute(select(Vote).where(Vote.meeting_id == meeting.id)).scalars().all()
    messages = (
        session.execute(
            select(Message)
            .where(Message.meeting_id == meeting.id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        .scalars()
        .all()
    )
    return MeetingOut(
        id=meeting.id,
        topic=meeting.topic,
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        decision_bps=meeting.decision_bps,
        minutes_md=meeting.minutes_md,
        created_by=UserOut.model_validate(creator),
        votes=[VoteOut.model_validate(v) for v in votes],
        messages=[MessageOut.model_validate(m) for m in messages],
    )

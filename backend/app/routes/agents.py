from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_session
from ..models import Agent, AgentMemory, User
from ..schemas import AgentOut, MemoryItemOut

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(current_user)])


@router.get("", response_model=list[AgentOut])
def list_agents(session: Session = Depends(get_session)):
    return session.execute(select(Agent).order_by(Agent.id.asc())).scalars().all()


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: int, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "Agente no encontrado")
    return agent


@router.get("/{agent_id}/memory", response_model=list[MemoryItemOut])
def get_agent_memory(agent_id: int, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "Agente no encontrado")
    return (
        session.execute(
            select(AgentMemory)
            .where(AgentMemory.agent_id == agent_id)
            .order_by(desc(AgentMemory.created_at))
        )
        .scalars()
        .all()
    )

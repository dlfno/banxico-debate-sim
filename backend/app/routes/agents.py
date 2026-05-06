from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_session
from ..models import Agent, AgentMemory
from ..personas import AGENT_DESCRIPTIONS
from ..schemas import AgentDescription, AgentOut, MemoryItemOut

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(current_user)])


def _to_agent_out(agent: Agent) -> AgentOut:
    """Construye AgentOut combinando datos de la BD con la descripción estática
    en `AGENT_DESCRIPTIONS` (indexada por slug). Si el slug no tiene descripción
    registrada, se devuelve `description=None`."""
    desc_dict = AGENT_DESCRIPTIONS.get(agent.slug)
    description = AgentDescription(**desc_dict) if desc_dict else None
    return AgentOut(
        id=agent.id,
        slug=agent.slug,
        display_name=agent.display_name,
        role=agent.role,
        stance=agent.stance,
        avatar=agent.avatar,
        description=description,
    )


@router.get("", response_model=list[AgentOut])
def list_agents(session: Session = Depends(get_session)):
    agents = session.execute(select(Agent).order_by(Agent.id.asc())).scalars().all()
    return [_to_agent_out(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: int, session: Session = Depends(get_session)):
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "Agente no encontrado")
    return _to_agent_out(agent)


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

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .llm import build_chat_model
from .models import Agent, AgentMemory, Message


def append_memory(
    session: Session,
    agent_id: int,
    kind: str,
    content: str,
    source_meeting_id: int | None = None,
) -> AgentMemory:
    item = AgentMemory(
        agent_id=agent_id,
        kind=kind,
        content=content.strip(),
        source_meeting_id=source_meeting_id,
    )
    session.add(item)
    session.flush()
    return item


def load_agent_context(session: Session, agent_id: int, k_meetings: int = 3, k_facts: int = 10) -> str:
    """Builds a textual context block to inject as a system message for an agent."""
    agent = session.get(Agent, agent_id)
    if agent is None:
        return ""

    facts = (
        session.execute(
            select(AgentMemory)
            .where(AgentMemory.agent_id == agent_id, AgentMemory.kind == "fact")
            .order_by(desc(AgentMemory.created_at))
            .limit(k_facts)
        )
        .scalars()
        .all()
    )
    summaries = (
        session.execute(
            select(AgentMemory)
            .where(AgentMemory.agent_id == agent_id, AgentMemory.kind == "meeting_summary")
            .order_by(desc(AgentMemory.created_at))
            .limit(k_meetings)
        )
        .scalars()
        .all()
    )

    parts: list[str] = []
    parts.append(f"=== Memoria persistente de {agent.display_name} ({agent.stance}) ===")
    if summaries:
        parts.append("\nÚltimas juntas en las que participaste (resúmenes desde tu perspectiva):")
        for s in summaries:
            ts = s.created_at.strftime("%Y-%m-%d") if s.created_at else ""
            parts.append(f"- [{ts}] {s.content}")
    if facts:
        parts.append("\nNotas/recuerdos personales acumulados:")
        for f in facts:
            parts.append(f"- {f.content}")
    if not summaries and not facts:
        parts.append("\n(Sin memoria previa; ésta es tu primera intervención registrada.)")
    parts.append(
        "\nUsa esta memoria para mantener consistencia con tus posturas y declaraciones previas. "
        "Si te preguntan sobre tu última intervención o voto, refiérete a estos resúmenes."
    )
    return "\n".join(parts)


def summarize_for_agent(session: Session, agent_id: int, meeting_id: int, transcript: str) -> AgentMemory | None:
    """Generates a short first-person summary for the agent and persists it."""
    agent = session.get(Agent, agent_id)
    if agent is None:
        return None
    model = build_chat_model(streaming=False, temperature=0.2)
    prompt = (
        f"Eres {agent.display_name} ({agent.stance}). A continuación está la transcripción de una junta "
        "de la Junta de Gobierno de Banxico en la que participaste. Resume EN PRIMERA PERSONA, en 4-6 oraciones, "
        "tu postura inicial, los argumentos principales que defendiste, tu voto final y la decisión colegiada. "
        "Esto es una nota personal para tu memoria; sé conciso y específico.\n\n"
        f"=== Transcripción ===\n{transcript}\n=== Fin ==="
    )
    resp = model.invoke([SystemMessage(content="Genera el resumen pedido."), HumanMessage(content=prompt)])
    text = resp.content if isinstance(resp.content, str) else _flatten(resp.content)
    return append_memory(session, agent_id, "meeting_summary", text, source_meeting_id=meeting_id)


def extract_facts(session: Session, agent_id: int, recent_messages: list[Message]) -> list[AgentMemory]:
    """Light-touch fact extraction from a chat session: extracts up to 3 stable preferences/observations
    that the agent should remember next time."""
    if not recent_messages:
        return []
    agent = session.get(Agent, agent_id)
    if agent is None:
        return []
    transcript = "\n".join(f"[{m.role}] {m.content}" for m in recent_messages)
    model = build_chat_model(streaming=False, temperature=0.1)
    prompt = (
        f"Eres un asistente que mantiene la memoria de {agent.display_name}. Lee la siguiente conversación "
        "y extrae hasta 3 hechos durables que el agente debería recordar la próxima vez (preferencias del usuario, "
        "compromisos hechos por el agente, datos clave mencionados). Devuelve UNA línea por hecho, sin numerar, "
        "sin viñetas, en español, máximo 25 palabras cada una. Si no hay nada útil, responde exactamente: NONE\n\n"
        f"=== Conversación ===\n{transcript}\n=== Fin ==="
    )
    resp = model.invoke([SystemMessage(content="Extrae los hechos."), HumanMessage(content=prompt)])
    text = resp.content if isinstance(resp.content, str) else _flatten(resp.content)
    text = text.strip()
    if not text or text.upper().startswith("NONE"):
        return []
    out: list[AgentMemory] = []
    for line in text.splitlines():
        clean = line.strip(" -•\t")
        if not clean or len(clean) < 6:
            continue
        out.append(append_memory(session, agent_id, "fact", clean))
    return out


def _flatten(content) -> str:
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)

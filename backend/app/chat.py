from __future__ import annotations

import json
from typing import Awaitable, Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from .agent_runtime import run_agent
from .llm import build_chat_model
from .memory import extract_facts, load_agent_context
from .models import Agent, ChatSession, Message

EventEmitter = Callable[[dict], Awaitable[None]]

FACT_EXTRACTION_EVERY = 6  # cada N mensajes de usuario se ejecuta extracción ligera


async def handle_user_turn(
    session: Session,
    chat_session_id: int,
    user_text: str,
    emit: EventEmitter,
) -> Message:
    chat = session.get(ChatSession, chat_session_id)
    if chat is None:
        raise ValueError("Sesión de chat no encontrada")
    agent = session.get(Agent, chat.agent_id)
    if agent is None:
        raise ValueError("Agente no encontrado")

    user_msg = Message(
        chat_session_id=chat_session_id,
        agent_id=agent.id,
        role="user",
        content=user_text,
    )
    session.add(user_msg)
    session.flush()

    history_msgs = (
        session.execute(
            select(Message)
            .where(Message.chat_session_id == chat_session_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        .scalars()
        .all()
    )

    context = load_agent_context(session, agent.id)
    convo: list[BaseMessage] = [SystemMessage(content=agent.system_prompt)]
    if context:
        convo.append(SystemMessage(content=context))
    for m in history_msgs:
        if m.role == "user":
            convo.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            convo.append(AIMessage(content=m.content))

    await emit({"type": "turn_start", "agent_id": agent.id, "agent": agent.display_name})

    model = build_chat_model(streaming=True)
    result = await run_agent(model, convo, emit=emit)

    assistant = Message(
        chat_session_id=chat_session_id,
        agent_id=agent.id,
        role="assistant",
        content=result.text,
        tool_calls_json=json.dumps(result.tool_calls, ensure_ascii=False) if result.tool_calls else None,
    )
    session.add(assistant)
    session.flush()

    user_count = sum(1 for m in history_msgs if m.role == "user") + 1
    if user_count % FACT_EXTRACTION_EVERY == 0:
        recent = history_msgs[-(FACT_EXTRACTION_EVERY * 2) :] + [user_msg, assistant]
        try:
            extract_facts(session, agent.id, recent)
        except Exception:
            # La extracción es best-effort; nunca debe romper el turno.
            pass

    session.commit()
    return assistant

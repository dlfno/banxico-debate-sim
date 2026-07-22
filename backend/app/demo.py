"""Modo demo: reproduce debates pre-generados SIN llamar al LLM.

Cuando `settings.DEMO_MODE` está activo, la Simulación de Junta no ejecuta la
orquestación real (que requeriría una API key de LLM y costaría dinero por cada
debate). En su lugar, `run_meeting_demo` reproduce una transcripción cacheada
desde `app/data/demo_meetings/*.json`, emitiendo exactamente los mismos eventos
WebSocket que `debate.run_meeting` (phase / turn_start / token / final / vote /
decision / minutes / done) y persistiendo la junta en la base de datos igual que
una real. Así el frontend no nota la diferencia y el deploy público es de costo $0.

Los textos se trocean en "tokens" al vuelo para conservar el efecto de streaming
en vivo; solo hay que redactar el texto completo de cada turno en el JSON.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session

from .debate import EventEmitter, _persist_message, _resolve_decision
from .models import Agent, Meeting, Vote

DEMO_DIR = Path(__file__).resolve().parent / "data" / "demo_meetings"

# Ritmo del replay (segundos). Valores pequeños = debate ágil pero con sensación
# de "en vivo". Configurable por si se quiere acelerar en tests.
_TOKEN_DELAY = 0.02
_TURN_GAP = 0.35
_TOKENS_PER_CHUNK = 5


def load_transcripts() -> list[dict]:
    """Carga y ordena las transcripciones demo disponibles."""
    if not DEMO_DIR.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DEMO_DIR.glob("*.json"))]


def _chunks(text: str) -> list[str]:
    """Trocea el texto en grupos de palabras para simular streaming de tokens."""
    words = text.split(" ")
    return [
        " ".join(words[i : i + _TOKENS_PER_CHUNK]) + (" " if i + _TOKENS_PER_CHUNK < len(words) else "")
        for i in range(0, len(words), _TOKENS_PER_CHUNK)
    ]


async def _stream_turn(agent: Agent, phase: str, text: str, emit: EventEmitter) -> None:
    """Emite turn_start -> tokens -> final para un turno, con ritmo de streaming."""
    await emit({"type": "turn_start", "agent_id": agent.id, "agent": agent.display_name, "phase": phase})
    for chunk in _chunks(text):
        await emit(
            {"type": "token", "delta": chunk, "agent_id": agent.id, "agent": agent.display_name, "phase": phase}
        )
        await asyncio.sleep(_TOKEN_DELAY)
    await emit({"type": "final", "text": text, "agent_id": agent.id, "agent": agent.display_name, "phase": phase})
    await asyncio.sleep(_TURN_GAP)


async def run_meeting_demo(
    session: Session,
    meeting_id: int,
    agent_ids: list[int],
    emit: EventEmitter,
) -> Meeting:
    """Reproduce una transcripción demo y la persiste como una junta real."""
    meeting = session.get(Meeting, meeting_id)
    if meeting is None:
        raise ValueError("Junta no encontrada")

    transcripts = load_transcripts()
    if not transcripts:
        raise RuntimeError("DEMO_MODE activo pero no hay transcripciones en app/data/demo_meetings/")
    # Rotación determinista para dar variedad entre juntas sucesivas.
    transcript = transcripts[meeting_id % len(transcripts)]

    # En demo el topic tecleado por el usuario se ignora (el debate es cacheado);
    # alineamos el topic persistido con el del transcript para que la lista de
    # juntas pasadas sea coherente con el contenido reproducido.
    if transcript.get("topic"):
        meeting.topic = transcript["topic"]

    agents = [session.get(Agent, aid) for aid in agent_ids]
    by_stance: dict[str, Agent] = {a.stance: a for a in agents if a is not None}

    def resolve(stance: str) -> Agent | None:
        return by_stance.get(stance)

    # --- Setup ---
    agenda = transcript.get("agenda") or f"Tema: {meeting.topic}"
    agenda = "🎬 (Demo — debate pre-generado, sin costo de LLM)\n\n" + agenda
    _persist_message(session, meeting_id, None, "moderator", "setup", agenda)
    await emit({"type": "phase", "phase": "setup", "content": agenda})
    await asyncio.sleep(_TURN_GAP)

    # --- Turnos (openings + debate) ---
    for turn in transcript.get("turns", []):
        agent = resolve(turn.get("stance", ""))
        if agent is None:
            continue
        phase = turn.get("phase", "debate")
        text = turn.get("text", "").strip()
        if not text:
            continue
        await _stream_turn(agent, phase, text, emit)
        _persist_message(session, meeting_id, agent.id, "assistant", phase, text)
        session.flush()

    # --- Votación ---
    votes: list[Vote] = []
    for v in transcript.get("votes", []):
        agent = resolve(v.get("stance", ""))
        if agent is None:
            continue
        decision_bps = int(v.get("decision_bps", 0))
        rationale = v.get("rationale", "")
        vote = Vote(meeting_id=meeting_id, agent_id=agent.id, decision_bps=decision_bps, rationale=rationale)
        session.add(vote)
        session.flush()
        votes.append(vote)
        await emit(
            {
                "type": "vote",
                "agent_id": agent.id,
                "agent": agent.display_name,
                "decision_bps": decision_bps,
                "rationale": rationale,
            }
        )
        await asyncio.sleep(_TURN_GAP)

    # --- Decisión (reutiliza la misma lógica de desempate que el debate real) ---
    valid_agents = [a for a in agents if a is not None]
    decision = _resolve_decision(votes, valid_agents) if votes else 0
    meeting.decision_bps = decision
    meeting.ended_at = datetime.utcnow()
    session.flush()
    await emit({"type": "decision", "decision_bps": decision})
    await asyncio.sleep(_TURN_GAP)

    # --- Minuta ---
    minutes_md = transcript.get("minutes_md", "").strip() or "_(sin minuta en el demo)_"
    meeting.minutes_md = minutes_md
    _persist_message(session, meeting_id, None, "secretario", "minutes", minutes_md)
    session.flush()
    await emit({"type": "minutes", "content": minutes_md})

    session.commit()
    await emit({"type": "done", "meeting_id": meeting_id})
    return meeting

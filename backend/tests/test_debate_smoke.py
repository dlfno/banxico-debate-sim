import asyncio

import pytest


def test_parse_vote_happy():
    from app.debate import _parse_vote

    assert _parse_vote("VOTO: -25 — riesgo a la baja") == (-25, "riesgo a la baja")
    assert _parse_vote("VOTO: +25 bps — preservar carry vs Fed") == (25, "preservar carry vs Fed")
    assert _parse_vote("VOTO: 0 — esperar más datos") == (0, "esperar más datos")


def test_parse_vote_rounding():
    from app.debate import _parse_vote

    parsed = _parse_vote("VOTO: -30 — agresivo")
    assert parsed is not None
    bps, _ = parsed
    assert bps == -25  # closest allowed


def test_parse_vote_none():
    from app.debate import _parse_vote

    assert _parse_vote("Prefiero mantener.") is None
    assert _parse_vote("") is None


def test_resolve_decision_majority():
    from app.debate import _resolve_decision
    from app.models import Agent, Vote

    agents = [
        Agent(id=1, slug="gobernadora", display_name="g", role="g", stance="centrista", system_prompt=""),
        Agent(id=2, slug="subg_halcon", display_name="h", role="s", stance="hawkish", system_prompt=""),
        Agent(id=3, slug="subg_paloma", display_name="p", role="s", stance="dovish", system_prompt=""),
    ]
    votes = [
        Vote(meeting_id=1, agent_id=1, decision_bps=-25, rationale=""),
        Vote(meeting_id=1, agent_id=2, decision_bps=0, rationale=""),
        Vote(meeting_id=1, agent_id=3, decision_bps=-25, rationale=""),
    ]
    assert _resolve_decision(votes, agents) == -25


def test_resolve_decision_tie_broken_by_governor():
    from app.debate import _resolve_decision
    from app.models import Agent, Vote

    agents = [
        Agent(id=1, slug="gobernadora", display_name="g", role="g", stance="centrista", system_prompt=""),
        Agent(id=2, slug="subg_halcon", display_name="h", role="s", stance="hawkish", system_prompt=""),
    ]
    votes = [
        Vote(meeting_id=1, agent_id=1, decision_bps=-25, rationale=""),
        Vote(meeting_id=1, agent_id=2, decision_bps=0, rationale=""),
    ]
    assert _resolve_decision(votes, agents) == -25  # gobernadora rompe el empate


@pytest.mark.asyncio
async def test_run_meeting_with_fake_llm(db_session, monkeypatch):
    """End-to-end del flujo de junta con un LLM fake; no llama a la red."""
    from langchain_core.messages import AIMessage

    from app import debate as debate_mod
    from app import memory as memory_mod
    from app.models import Agent, Meeting

    class FakeChunk:
        def __init__(self, text):
            self.content = text
            self.tool_calls = []

        def __add__(self, other):
            return FakeChunk(self.content + other.content)

    from langchain_core.messages import AIMessageChunk

    class FakeModel:
        def __init__(self, responses):
            self._responses = list(responses)
            self._idx = 0

        def bind_tools(self, _tools):
            return self

        async def astream(self, _messages):
            text = self._responses[min(self._idx, len(self._responses) - 1)]
            self._idx += 1
            yield AIMessageChunk(content=text)

        def invoke(self, _messages):
            text = self._responses[min(self._idx, len(self._responses) - 1)]
            self._idx += 1
            return AIMessage(content=text)

    # Construye respuestas en orden: 5 openings, 2 rondas * 5 debates, 5 votos, 1 minuta, + 5 resúmenes per-agente.
    openings = ["Posición inicial." for _ in range(5)]
    debates = ["Comentario de debate." for _ in range(5 * 2)]
    votes = [
        "VOTO: 0 — mantener",
        "VOTO: +25 — restrictivo",
        "VOTO: -25 — recortar",
        "VOTO: 0 — datos mixtos",
        "VOTO: 0 — preservar carry",
    ]
    minutes = ["# Minuta\nDecisión: mantener."]
    summaries = ["Resumen perspectiva." for _ in range(5)]
    fake = FakeModel(openings + debates + votes + minutes + summaries)

    monkeypatch.setattr(debate_mod, "build_chat_model", lambda **kw: fake)
    monkeypatch.setattr(memory_mod, "build_chat_model", lambda **kw: fake)

    agents = db_session.query(Agent).order_by(Agent.id.asc()).all()
    meeting = Meeting(topic="Test de smoke")
    db_session.add(meeting)
    db_session.commit()

    events = []

    async def emit(ev):
        events.append(ev)

    await debate_mod.run_meeting(db_session, meeting.id, rounds=2, agent_ids=[a.id for a in agents], emit=emit)

    db_session.refresh(meeting)
    assert meeting.minutes_md and "Minuta" in meeting.minutes_md
    assert meeting.decision_bps in {-50, -25, 0, 25, 50}
    assert meeting.ended_at is not None
    # Debe haber 5 votos persistidos
    assert len(meeting.votes) == 5
    # Debe existir un resumen por agente
    from app.models import AgentMemory
    summaries_rows = db_session.query(AgentMemory).filter_by(kind="meeting_summary").all()
    assert len(summaries_rows) == 5
    # Eventos de fase emitidos
    kinds = {e.get("type") for e in events}
    assert {"phase", "vote", "decision", "minutes", "done"} <= kinds

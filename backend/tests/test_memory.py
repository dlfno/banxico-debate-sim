from datetime import datetime, timedelta


def test_load_agent_context_includes_facts_and_summaries(db_session):
    from app.memory import append_memory, load_agent_context
    from app.models import Agent

    agent = db_session.query(Agent).filter_by(slug="subg_halcon").one()
    append_memory(db_session, agent.id, "fact", "El usuario prefiere análisis breve.")
    append_memory(db_session, agent.id, "meeting_summary", "Defendí mantener tasa por riesgo de servicios.", source_meeting_id=None)
    db_session.commit()

    ctx = load_agent_context(db_session, agent.id)
    assert "Memoria persistente" in ctx
    assert "El usuario prefiere análisis breve." in ctx
    assert "Defendí mantener tasa" in ctx


def test_load_agent_context_empty(db_session):
    from app.memory import load_agent_context
    from app.models import Agent

    agent = db_session.query(Agent).filter_by(slug="subg_paloma").one()
    ctx = load_agent_context(db_session, agent.id)
    assert "Sin memoria previa" in ctx


def test_meeting_summary_visible_in_subsequent_chat_context(db_session):
    """Junta → chat: un meeting_summary persistido tras una junta debe aparecer
    cuando el mismo agente carga su contexto en un chat posterior."""
    from app.memory import append_memory, load_agent_context
    from app.models import Agent

    agent = db_session.query(Agent).filter_by(slug="subg_halcon").one()
    summary = (
        "En la junta del jueves defendí +25 bps por riesgo de servicios; "
        "voté +25 y la decisión colegiada fue 0."
    )
    append_memory(db_session, agent.id, "meeting_summary", summary, source_meeting_id=99)
    db_session.commit()

    ctx = load_agent_context(db_session, agent.id)
    assert "Últimas juntas en las que participaste" in ctx
    assert "voté +25" in ctx
    assert "decisión colegiada fue 0" in ctx


def test_chat_fact_visible_in_meeting_context(db_session):
    """Chat → junta: un fact escrito desde modo chat debe aparecer cuando el
    mismo agente carga su contexto durante una junta (mismo helper que usa
    debate._agent_turn)."""
    from app.memory import append_memory, load_agent_context
    from app.models import Agent

    agent = db_session.query(Agent).filter_by(slug="subg_paloma").one()
    append_memory(db_session, agent.id, "fact", "El usuario sigue de cerca el spread MX-US 10y.")
    db_session.commit()

    ctx = load_agent_context(db_session, agent.id)
    assert "Notas/recuerdos personales" in ctx
    assert "spread MX-US 10y" in ctx


def test_extract_facts_persists_and_load_returns_them(db_session, monkeypatch):
    """Cierra el loop chat → DB → prompt: monkeypatchea el LLM extractor con
    un fake que devuelve dos hechos, ejecuta extract_facts, y verifica que
    quedaron en DB y son visibles vía load_agent_context."""
    from langchain_core.messages import AIMessage

    from app import memory as memory_mod
    from app.models import Agent, AgentMemory, Message

    class FakeModel:
        def invoke(self, _messages):
            return AIMessage(
                content="El usuario prefiere análisis breve y específicos en bps\nSe comprometió a publicar minutas más rápido"
            )

    monkeypatch.setattr(memory_mod, "build_chat_model", lambda **kw: FakeModel())

    agent = db_session.query(Agent).filter_by(slug="subg_datos").one()
    recent = [
        Message(role="user", content="¿Cómo ves la inflación subyacente?", agent_id=agent.id),
        Message(role="assistant", content="Subyacente sigue rígida; mejor mantener.", agent_id=agent.id),
    ]
    created = memory_mod.extract_facts(db_session, agent.id, recent)
    db_session.commit()

    assert len(created) == 2
    rows = db_session.query(AgentMemory).filter_by(agent_id=agent.id, kind="fact").all()
    assert len(rows) == 2

    ctx = memory_mod.load_agent_context(db_session, agent.id)
    assert "análisis breve" in ctx
    assert "minutas más rápido" in ctx


def test_extract_facts_returns_empty_on_NONE(db_session, monkeypatch):
    """Si el LLM responde NONE, no se debe insertar nada."""
    from langchain_core.messages import AIMessage

    from app import memory as memory_mod
    from app.models import Agent, AgentMemory, Message

    class FakeModel:
        def invoke(self, _messages):
            return AIMessage(content="NONE")

    monkeypatch.setattr(memory_mod, "build_chat_model", lambda **kw: FakeModel())

    agent = db_session.query(Agent).filter_by(slug="subg_externo").one()
    created = memory_mod.extract_facts(
        db_session, agent.id, [Message(role="user", content="hola", agent_id=agent.id)]
    )
    assert created == []
    assert db_session.query(AgentMemory).filter_by(agent_id=agent.id, kind="fact").count() == 0


def test_summarize_for_agent_persists_with_meeting_id(db_session, monkeypatch):
    """Cierra el loop junta → DB: el resumen queda asociado al meeting_id correcto."""
    from langchain_core.messages import AIMessage

    from app import memory as memory_mod
    from app.models import Agent, AgentMemory

    class FakeModel:
        def invoke(self, _messages):
            return AIMessage(content="Voté +25; defendí riesgo de servicios; resultado 0.")

    monkeypatch.setattr(memory_mod, "build_chat_model", lambda **kw: FakeModel())

    agent = db_session.query(Agent).filter_by(slug="subg_halcon").one()
    out = memory_mod.summarize_for_agent(
        db_session, agent.id, meeting_id=42, transcript="[Moderador] Tema: tasa\n..."
    )
    db_session.commit()

    assert out is not None
    rows = (
        db_session.query(AgentMemory)
        .filter_by(agent_id=agent.id, kind="meeting_summary")
        .all()
    )
    assert len(rows) == 1
    assert rows[0].source_meeting_id == 42
    assert "Voté +25" in rows[0].content


def test_load_agent_context_orders_recent_first(db_session):
    """load_agent_context ordena por created_at DESC y limita; los más recientes
    deben aparecer primero en la sección Notas/recuerdos."""
    from app.memory import append_memory, load_agent_context
    from app.models import Agent, AgentMemory

    agent = db_session.query(Agent).filter_by(slug="gobernadora").one()
    base = datetime(2026, 1, 1, 12, 0, 0)
    for i in range(12):
        item = append_memory(db_session, agent.id, "fact", f"hecho-{i:02d}-importante")
        # Forzar created_at incremental para evitar ambigüedad de microsegundos.
        item.created_at = base + timedelta(seconds=i)
    db_session.commit()

    ctx = load_agent_context(db_session, agent.id, k_facts=5)
    section = ctx.split("Notas/recuerdos personales")[1]
    # El más reciente (índice 11) debe aparecer ANTES que el más viejo (07).
    pos_recent = section.find("hecho-11-importante")
    pos_older = section.find("hecho-07-importante")
    assert pos_recent != -1, "el más reciente debe estar incluido"
    assert pos_older != -1, "los 5 más recientes (07-11) deben estar incluidos"
    assert pos_recent < pos_older, "el más reciente debe imprimirse primero"
    # El que quedó fuera del top-5 NO debe estar.
    assert "hecho-06-importante" not in section

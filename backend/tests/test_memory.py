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

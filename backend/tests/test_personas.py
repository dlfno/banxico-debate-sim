def test_personas_seeded(db_session):
    from app.models import Agent

    rows = db_session.query(Agent).all()
    slugs = {a.slug for a in rows}
    assert {"gobernadora", "subg_halcon", "subg_paloma", "subg_datos", "subg_externo"} <= slugs
    for a in rows:
        assert a.system_prompt
        assert a.stance
        assert a.display_name

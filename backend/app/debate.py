from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

AGENT_TURN_TIMEOUT = 900.0  # 15 minutos por turno de agente

log = logging.getLogger(__name__)

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from .agent_runtime import run_agent
from .banxico_context import get_institutional_context
from .llm import build_chat_model
from .memory import load_agent_context, summarize_for_agent
from .models import Agent, Meeting, Message, Vote
from .tools import get_macro_snapshot

EventEmitter = Callable[[dict], Awaitable[None]]

VOTE_REGEX = re.compile(r"VOTO\s*:\s*([+\-]?\d{1,3})\s*(?:bps)?\s*[—\-:]\s*(.+)", re.IGNORECASE)
# Regex secundario más permisivo: captura el número aunque falte el separador o haya markdown
_VOTE_REGEX_LAX = re.compile(r"\*{0,2}VOTO\*{0,2}\s*:?\s*\*{0,2}([+\-]?\d{1,3})\*{0,2}\s*(?:bps)?", re.IGNORECASE)
ALLOWED_BPS = {-50, -25, 0, 25, 50}


# ── Scratchpad de herramientas compartido en una junta ──────────────────────
# Cada llamada a una herramienta y su resultado se acumula aquí. Antes de cada
# turno de agente, el scratchpad se formatea como SystemMessage adicional para
# que los agentes posteriores reusen los datos en vez de re-llamar.
# Reduce queries duplicadas a Tavily, latencia y costos.

# Campos del macro snapshot que mostramos en el resumen (los más usados en debate).
_MACRO_KEY_FIELDS = (
    "as_of",
    "banxico_target_rate_pct",
    "fed_funds_upper_pct",
    "inpc_yoy_pct",
    "inpc_subyacente_yoy_pct",
    "expectativas_inflacion_12m_pct",
    "usd_mxn",
    "wti_usd_bbl",
    "brent_usd_bbl",
    "mezcla_mx_usd_bbl",
    "tasa_desempleo_pct",
    "pib_yoy_pct",
)


@dataclass
class ScratchpadEntry:
    agent_name: str
    phase: str
    tool_name: str
    args: dict
    output_summary: str = field(default="")


def _summarize_tool_output(name: str, output: Any) -> str:
    """Resume el output de una herramienta en una representación compacta para el
    scratchpad. Devuelve un string corto y legible."""
    text = output if isinstance(output, str) else str(output)

    if name == "get_macro_snapshot":
        # El output suele ser dict serializado a JSON. Extraemos campos clave.
        try:
            data = json.loads(text) if isinstance(text, str) else text
            if isinstance(data, dict):
                kvs = []
                for k in _MACRO_KEY_FIELDS:
                    if k in data:
                        v = data[k]
                        kvs.append(f"{k}={v}")
                return ", ".join(kvs) if kvs else text[:300]
        except Exception:
            pass
        return text[:300]

    if name == "web_search":
        # web_search devuelve líneas tipo "- Título\n  URL\n  contenido". Truncamos
        # cada bloque y mostramos top 3 resultados.
        blocks: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            if line.startswith("- "):
                if current:
                    blocks.append(" ".join(current))
                current = [line[2:].strip()]
            elif line.strip():
                current.append(line.strip())
        if current:
            blocks.append(" ".join(current))
        top = blocks[:3]
        truncated = [(b[:200] + "…") if len(b) > 200 else b for b in top]
        more = f" (+{len(blocks)-3} resultados omitidos)" if len(blocks) > 3 else ""
        return "\n  ".join(truncated) + more if truncated else text[:300]

    if name == "calculator":
        return text.strip()[:200]

    if name == "consult_banxico_history":
        # Output: "[fuente: ...]\n<párrafo>\n\n[fuente: ...]\n<párrafo>..." (hasta 3).
        # Para el scratchpad mostramos la línea de fuente del primero y un snippet
        # del párrafo, indicando cuántos bloques más se devolvieron.
        blocks = [b for b in text.split("\n\n") if b.strip()]
        if not blocks:
            return text[:200]
        first = blocks[0]
        head, _, body = first.partition("\n")
        snippet = (body[:180] + "…") if len(body) > 180 else body
        more = f" (+{len(blocks)-1} bloques)" if len(blocks) > 1 else ""
        return f"{head}\n  {snippet}{more}"

    return text[:300]


def format_scratchpad(entries: list[ScratchpadEntry]) -> str:
    """Formatea el scratchpad como un SystemMessage en markdown para inyectar
    en el convo de un turno de agente. Vacío si no hay entradas."""
    if not entries:
        return ""
    lines = [
        "=== Caja de herramientas (resultados ya disponibles en esta junta) ===",
        "ANTES de invocar una herramienta, revisa si los datos que necesitas ya",
        "están aquí. Si están, úsalos directamente y cita al miembro como referencia",
        "(ej. \"según consultó la Subgobernadora Vega…\"). Evita llamadas duplicadas.",
        "",
    ]
    for e in entries:
        args_str = ""
        if e.args:
            try:
                args_str = json.dumps(e.args, ensure_ascii=False)
            except Exception:
                args_str = str(e.args)
        head = f"[{e.agent_name} · {e.phase}] {e.tool_name}({args_str})"
        lines.append(head)
        # Indenta el resumen para legibilidad.
        for sub in e.output_summary.splitlines() or [e.output_summary]:
            lines.append(f"  → {sub}" if sub else "")
        lines.append("")
    return "\n".join(lines).rstrip()


async def run_meeting(
    session: Session,
    meeting_id: int,
    rounds: int,
    agent_ids: list[int],
    emit: EventEmitter,
) -> Meeting:
    meeting = session.get(Meeting, meeting_id)
    if meeting is None:
        raise ValueError("Junta no encontrada")
    agents = [session.get(Agent, aid) for aid in agent_ids]
    agents = [a for a in agents if a is not None]
    if len(agents) < 2:
        raise ValueError("Se requieren al menos 2 agentes")

    macro = get_macro_snapshot.invoke({})
    agenda = (
        f"Tema: {meeting.topic}\n"
        f"Snapshot macro al {macro['as_of']}: tasa Banxico {macro['banxico_target_rate_pct']}%, "
        f"Fed funds {macro['fed_funds_upper_pct']}%, INPC headline {macro['inpc_yoy_pct']}% YoY, "
        f"subyacente {macro['inpc_subyacente_yoy_pct']}% YoY, expectativas 12m "
        f"{macro['expectativas_inflacion_12m_pct']}%, USD/MXN {macro['usd_mxn']}.\n"
        f"Asistentes: {', '.join(a.display_name + ' (' + a.stance + ')' for a in agents)}."
    )
    _persist_message(session, meeting_id, None, "moderator", "setup", agenda)
    await emit({"type": "phase", "phase": "setup", "content": agenda})

    transcript: list[str] = [f"[Moderador] {agenda}"]
    # Scratchpad compartido: cada llamada a herramienta + su resultado, accesible
    # a los agentes posteriores para evitar redundancia. Se mutará en _agent_turn.
    scratchpad: list[ScratchpadEntry] = []

    # Phase: openings
    for agent in agents:
        text = await _agent_turn(
            session,
            meeting_id,
            agent,
            phase="opening",
            instruction=(
                f"Da tu posición INICIAL sobre: «{meeting.topic}». "
                "Máximo 200 palabras. Si necesitas datos macro, usa get_macro_snapshot o web_search. "
                "No emitas tu voto todavía."
            ),
            transcript=transcript,
            scratchpad=scratchpad,
            emit=emit,
        )
        entry = text.strip() or f"[{agent.display_name} no emitió posición inicial]"
        transcript.append(f"[{agent.display_name}] {entry}")

    # Phase: cross-talk rounds
    for r in range(rounds):
        order = await _pick_speakers_order(agents, transcript)
        for agent in order:
            text = await _agent_turn(
                session,
                meeting_id,
                agent,
                phase="debate",
                instruction=(
                    "Reacciona al debate hasta ahora. Identifica con quién coincides y con quién discrepas, "
                    "y por qué. Sé específico con datos. Máximo 180 palabras. No votes aún."
                ),
                transcript=transcript,
                scratchpad=scratchpad,
                emit=emit,
            )
            entry = text.strip() or f"[{agent.display_name} no emitió posición en esta ronda]"
            transcript.append(f"[{agent.display_name}] {entry}")

    # Phase: voting
    votes: list[Vote] = []
    for agent in agents:
        decision_bps, rationale = await _collect_vote(
            session, meeting_id, agent, transcript=transcript, scratchpad=scratchpad, emit=emit
        )
        v = Vote(meeting_id=meeting_id, agent_id=agent.id, decision_bps=decision_bps, rationale=rationale)
        session.add(v)
        session.flush()
        votes.append(v)
        transcript.append(f"[{agent.display_name}] VOTO: {decision_bps:+d} bps — {rationale}")
        await emit(
            {
                "type": "vote",
                "agent_id": agent.id,
                "agent": agent.display_name,
                "decision_bps": decision_bps,
                "rationale": rationale,
            }
        )

    decision = _resolve_decision(votes, agents)
    meeting.decision_bps = decision
    # Naive UTC, consistente con los server_default=func.now() de SQLite.
    meeting.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.flush()

    await emit({"type": "decision", "decision_bps": decision})

    # Phase: minutes
    try:
        minutes_md = await asyncio.wait_for(
            _generate_minutes(meeting.topic, transcript, votes, decision, agents),
            timeout=300.0,
        )
        if not minutes_md.strip():
            log.warning("Minuta vacía; usando fallback")
            minutes_md = _fallback_minutes(meeting.topic, votes, decision, agents)
    except Exception as exc:
        log.error("Error generando minuta: %s", exc)
        minutes_md = _fallback_minutes(meeting.topic, votes, decision, agents)
    meeting.minutes_md = minutes_md
    _persist_message(session, meeting_id, None, "secretario", "minutes", minutes_md)
    session.flush()
    await emit({"type": "minutes", "content": minutes_md})

    # Phase: per-agent memory
    full_transcript = "\n".join(transcript)
    for agent in agents:
        try:
            summarize_for_agent(session, agent.id, meeting_id, full_transcript)
        except Exception:
            # Memoria es best-effort
            log.exception("summarize_for_agent falló agent_id=%s meeting_id=%s", agent.id, meeting_id)

    session.commit()
    await emit({"type": "done", "meeting_id": meeting_id})
    return meeting


async def _agent_turn(
    session: Session,
    meeting_id: int,
    agent: Agent,
    *,
    phase: str,
    instruction: str,
    transcript: list[str],
    scratchpad: list[ScratchpadEntry] | None = None,
    emit: EventEmitter,
) -> str:
    context = load_agent_context(session, agent.id)
    convo: list[BaseMessage] = [SystemMessage(content=agent.system_prompt)]
    if context:
        convo.append(SystemMessage(content=context))
    # Contexto institucional Banxico: resumen de las decisiones reales recientes,
    # postura de los miembros, balance de riesgos. Aterriza el razonamiento de
    # los agentes en datos oficiales en lugar de invenciones.
    convo.append(SystemMessage(content=get_institutional_context()))
    convo.append(SystemMessage(content="Transcripción del debate hasta ahora:\n" + "\n".join(transcript)))
    # Inyecta scratchpad de herramientas YA consultadas en la junta — los agentes
    # posteriores leen esto antes de decidir si vuelven a llamar una herramienta.
    if scratchpad:
        scratch_md = format_scratchpad(scratchpad)
        if scratch_md:
            convo.append(SystemMessage(content=scratch_md))
    convo.append(HumanMessage(content=instruction))

    await emit({"type": "turn_start", "agent_id": agent.id, "agent": agent.display_name, "phase": phase})
    model = build_chat_model(streaming=True, temperature=0.6)

    async def relay(ev: dict) -> None:
        ev = {**ev, "agent_id": agent.id, "agent": agent.display_name, "phase": phase}
        await emit(ev)

    last_result = None
    for attempt in range(2):
        try:
            r = await asyncio.wait_for(
                run_agent(model, convo, emit=relay),
                timeout=AGENT_TURN_TIMEOUT,
            )
            last_result = r
            if r.text.strip():
                break
            log.warning(
                "Respuesta vacía de '%s' fase '%s' (intento %d)",
                agent.display_name, phase, attempt + 1,
            )
        except asyncio.TimeoutError:
            log.error(
                "Timeout (%.0fs) en turno de '%s' fase '%s' (intento %d)",
                AGENT_TURN_TIMEOUT, agent.display_name, phase, attempt + 1,
            )

    if last_result is None:
        placeholder = f"[{agent.display_name} no respondió — timeout]"
        await relay({"type": "final", "text": placeholder})
        _persist_message(session, meeting_id, agent.id, "assistant", phase, placeholder, tool_calls=[])
        session.flush()
        return placeholder

    # Acumula los tool calls de este turno en el scratchpad para los siguientes turnos.
    if scratchpad is not None and last_result.tool_results:
        for tr in last_result.tool_results:
            scratchpad.append(
                ScratchpadEntry(
                    agent_name=agent.display_name,
                    phase=phase,
                    tool_name=tr.get("name", "?"),
                    args=tr.get("args") or {},
                    output_summary=_summarize_tool_output(tr.get("name", ""), tr.get("output", "")),
                )
            )

    final_text = last_result.text.strip() or f"[{agent.display_name} no emitió posición]"
    _persist_message(
        session,
        meeting_id,
        agent.id,
        "assistant",
        phase,
        final_text,
        tool_calls=last_result.tool_calls,
    )
    session.flush()
    return final_text


async def _collect_vote(
    session: Session,
    meeting_id: int,
    agent: Agent,
    *,
    transcript: list[str],
    scratchpad: list[ScratchpadEntry] | None = None,
    emit: EventEmitter,
) -> tuple[int, str]:
    instruction = (
        "Es momento del voto. Emite tu voto SOLAMENTE en una línea con el formato exacto:\n"
        "VOTO: <bps> — <razón breve>\n"
        "donde <bps> ∈ {-50, -25, 0, +25, +50}. Sin texto adicional fuera de esa línea."
    )
    text = await _agent_turn(
        session,
        meeting_id,
        agent,
        phase="vote",
        instruction=instruction,
        transcript=transcript,
        scratchpad=scratchpad,
        emit=emit,
    )
    parsed = _parse_vote(text)
    if parsed is None:
        # Reintento único con énfasis en el formato
        retry = await _agent_turn(
            session,
            meeting_id,
            agent,
            phase="vote",
            instruction=(
                "Tu voto anterior no respetó el formato. Repite SOLAMENTE la línea:\n"
                "VOTO: <bps> — <razón breve>\n"
                "con <bps> ∈ {-50, -25, 0, +25, +50}."
            ),
            transcript=transcript + [f"[{agent.display_name}] {text}"],
            scratchpad=scratchpad,
            emit=emit,
        )
        parsed = _parse_vote(retry)
    if parsed is None:
        # Fallback conservador: mantener.
        return 0, "Voto no parseable; se asume mantener (default)."
    return parsed


def _parse_vote(text: str) -> tuple[int, str] | None:
    if not text:
        return None
    # Intento primario: formato exacto con separador y razón
    m = VOTE_REGEX.search(text)
    if m:
        try:
            bps = int(m.group(1))
        except ValueError:
            return None
        if bps not in ALLOWED_BPS:
            bps = min(ALLOWED_BPS, key=lambda x: abs(x - bps))
        return bps, m.group(2).strip()
    # Intento secundario: regex laxo (captura el número aunque falte separador o haya markdown)
    m2 = _VOTE_REGEX_LAX.search(text)
    if m2:
        try:
            bps = int(m2.group(1))
        except ValueError:
            return None
        if bps not in ALLOWED_BPS:
            bps = min(ALLOWED_BPS, key=lambda x: abs(x - bps))
        # Extraer la razón: todo lo que sigue al match
        rationale = text[m2.end():].strip().lstrip("—-:bps ").split("\n")[0][:200]
        return bps, rationale or "Sin razón especificada"
    return None


def _resolve_decision(votes: list[Vote], agents: list[Agent]) -> int:
    from collections import Counter

    counts = Counter(v.decision_bps for v in votes)
    top = counts.most_common()
    if not top:
        return 0
    max_n = top[0][1]
    tied = [bps for bps, n in top if n == max_n]
    if len(tied) == 1:
        return tied[0]
    # Empate: el voto de la gobernadora rompe el empate si está entre los empatados.
    gov = next((a for a in agents if a.slug == "gobernadora"), None)
    if gov is not None:
        gov_vote = next((v.decision_bps for v in votes if v.agent_id == gov.id), None)
        if gov_vote in tied:
            return gov_vote
    # Fallback: opción más conservadora (más cercana a 0).
    return min(tied, key=lambda x: (abs(x), x))


def _extract_text(content) -> str:
    """Extrae el contenido textual de un AIMessage (string directo o lista de bloques)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return str(content)


async def _generate_minutes(
    topic: str,
    transcript: list[str],
    votes: list[Vote],
    decision: int,
    agents: list[Agent],
) -> str:
    """Genera la minuta con el LLM. Reintenta una vez si la primera respuesta viene vacía,
    con backoff corto. Si ambos intentos fallan, devuelve "" y el caller cae al fallback.
    Loggea finish_reason y usage cuando viene vacía para diagnóstico."""
    agent_by_id = {a.id: a for a in agents}
    votes_block = "\n".join(
        f"- {agent_by_id[v.agent_id].display_name} ({agent_by_id[v.agent_id].stance}): "
        f"{v.decision_bps:+d} bps — {v.rationale}"
        for v in votes
    )
    secretary_prompt = (
        "Eres el Secretario de la Junta de Gobierno de Banxico. Redacta una MINUTA en Markdown, "
        "tono institucional, con las siguientes secciones: \n"
        "1. Contexto y agenda\n2. Posiciones por miembro (un párrafo cada uno, atribuido)\n"
        "3. Discusión y puntos de fricción\n4. Votación (tabla)\n5. Decisión final\n6. Riesgos y comunicación.\n"
        "Apégate a lo dicho en la transcripción; no inventes cifras. Máximo ~600 palabras."
    )
    user_msg = (
        f"Tema: {topic}\n"
        f"Decisión final: {decision:+d} bps.\n\n"
        f"Votos individuales:\n{votes_block}\n\n"
        f"=== Transcripción completa ===\n{chr(10).join(transcript)}\n=== Fin ==="
    )

    transcript_chars = sum(len(t) for t in transcript)
    log.info(
        "Generando minuta: transcript=%d chars, votos=%d, agentes=%d, prompt~%d chars",
        transcript_chars, len(votes), len(agents), len(secretary_prompt) + len(user_msg),
    )

    # max_tokens=6000: con modelos con extended thinking (Claude 4.x), el reasoning
    # interno consume 1500-2500 tokens antes de empezar a escribir. La minuta visible
    # son ~600 palabras (~1000 tokens). Con cap 2048 default, el modelo se cortaba
    # antes de generar nada visible (finish_reason=length).
    model = build_chat_model(streaming=False, temperature=0.2, max_tokens=6000)
    messages = [SystemMessage(content=secretary_prompt), HumanMessage(content=user_msg)]

    for attempt in range(2):
        resp = await model.ainvoke(messages)
        text = _extract_text(resp.content)
        if text.strip():
            if attempt > 0:
                log.info("Minuta generada en intento %d", attempt + 1)
            return text
        # Vino vacía: loggear metadata para diagnóstico (finish_reason, usage)
        meta = getattr(resp, "response_metadata", {}) or {}
        usage = meta.get("token_usage") or meta.get("usage") or getattr(resp, "usage_metadata", {}) or {}
        finish_reason = (
            meta.get("finish_reason")
            or meta.get("stop_reason")
            or meta.get("finishReason")
            or "?"
        )
        log.warning(
            "Minuta vacía (intento %d). finish_reason=%s usage=%s meta_keys=%s",
            attempt + 1, finish_reason, dict(usage) if usage else {}, list(meta.keys()),
        )
        if attempt < 1:
            await asyncio.sleep(2.0)  # backoff corto antes de reintentar

    return ""


def _fallback_minutes(topic: str, votes: list[Vote], decision: int, agents: list[Agent]) -> str:
    agent_by_id = {a.id: a for a in agents}
    rows = "\n".join(
        f"| {agent_by_id[v.agent_id].display_name} | {v.decision_bps:+d} bps | {v.rationale} |"
        for v in votes
        if v.agent_id in agent_by_id
    )
    return (
        f"# Minuta — Junta de Gobierno Banxico\n\n"
        f"## Tema\n{topic}\n\n"
        f"## Votación\n| Miembro | Voto | Razón |\n|---|---|---|\n{rows}\n\n"
        f"## Decisión final\n**{decision:+d} puntos base**\n\n"
        f"*La minuta detallada no pudo generarse automáticamente en esta sesión.*"
    )


async def _pick_speakers_order(agents: list[Agent], transcript: list[str]) -> list[Agent]:
    """Heurística simple: orden round-robin alterando hawkish/dovish primero."""
    priority = {"hawkish": 0, "dovish": 1, "centrista": 2, "data-dependent": 3, "externo/FX": 4}
    return sorted(agents, key=lambda a: priority.get(a.stance, 99))


def _persist_message(
    session: Session,
    meeting_id: int,
    agent_id: int | None,
    role: str,
    phase: str,
    content: str,
    tool_calls: list[dict] | None = None,
) -> Message:
    m = Message(
        meeting_id=meeting_id,
        agent_id=agent_id,
        role=role,
        phase=phase,
        content=content,
        tool_calls_json=json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
    )
    session.add(m)
    session.flush()
    return m

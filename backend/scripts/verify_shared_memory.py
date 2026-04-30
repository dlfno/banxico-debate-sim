#!/usr/bin/env python3
"""End-to-end verification of shared memory between meetings and 1-a-1 chats.

Run against a live backend (uvicorn) with valid LLM credentials in `.env`.
Usage:
    cd backend && . .venv/bin/activate
    BANXICO_URL=http://localhost:8000 python scripts/verify_shared_memory.py [--with-chat]

Steps:
  1. Register (or log in) a verifier user.
  2. Snapshot current memory of subg_halcon (agent_id=2).
  3. (--with-chat) Run a real 6-turn chat with halcon to trigger fact extraction.
  4. Create a 1-round meeting with halcon + paloma and drive it via WebSocket.
  5. Confirm halcon now has +1 meeting_summary tied to the new meeting.
  6. Print the final memory state.

Exit codes: 0 on full success, 1 on any failed assertion.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid

import requests
import websockets


BASE = os.environ.get("BANXICO_URL", "http://localhost:8000").rstrip("/")
WS_BASE = BASE.replace("http://", "ws://").replace("https://", "wss://")
HALCON_ID = 2
PALOMA_ID = 3


def log(step: str, ok: bool, detail: str = "") -> None:
    mark = "✓" if ok else "✗"
    print(f"  {mark} {step}{(': ' + detail) if detail else ''}")
    if not ok:
        sys.exit(1)


def register_or_login() -> tuple[str, dict]:
    suffix = uuid.uuid4().hex[:6]
    username = f"verif_{suffix}"
    res = requests.post(
        f"{BASE}/api/auth/register",
        json={"username": username, "display_name": "Verificador", "password": "verifpass123"},
        timeout=10,
    )
    if res.status_code == 201:
        body = res.json()
        return body["token"], body["user"]
    res.raise_for_status()
    raise RuntimeError(f"register fallo inesperado: {res.status_code} {res.text}")


def get_memory(token: str, agent_id: int) -> list[dict]:
    res = requests.get(
        f"{BASE}/api/agents/{agent_id}/memory",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    res.raise_for_status()
    return res.json()


async def run_meeting_ws(token: str, meeting_id: int) -> list[dict]:
    """Opens a WS to the meeting and collects events until 'done' or 'error'."""
    url = f"{WS_BASE}/api/meetings/ws/{meeting_id}?token={token}"
    events: list[dict] = []
    async with websockets.connect(url, max_size=2**22) as ws:
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=300)
            except asyncio.TimeoutError:
                raise RuntimeError("timeout esperando eventos de la junta (>5min)")
            ev = json.loads(raw)
            events.append(ev)
            if ev.get("type") == "done":
                return events
            if ev.get("type") == "error":
                raise RuntimeError(f"junta erró: {ev.get('message')}")


async def run_chat_ws(token: str, session_id: int, messages: list[str]) -> int:
    """Sends `messages` one at a time, waits for 'final' between each."""
    url = f"{WS_BASE}/api/chat/ws/{session_id}?token={token}"
    sent = 0
    async with websockets.connect(url, max_size=2**22) as ws:
        for msg in messages:
            await ws.send(json.dumps({"type": "user", "content": msg}))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=120)
                ev = json.loads(raw)
                if ev.get("type") == "final":
                    sent += 1
                    break
                if ev.get("type") == "error":
                    raise RuntimeError(f"chat erró: {ev.get('message')}")
    return sent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-chat",
        action="store_true",
        help="Ejercita además el flujo de chat (6 turnos) — más lento, requiere LLM key",
    )
    args = parser.parse_args()

    print(f"Verificando memoria compartida contra {BASE}\n")

    print("1. Registro de usuario verificador")
    try:
        token, user = register_or_login()
    except Exception as exc:
        log("register/login", False, str(exc))
        return
    log("register", True, f"user={user['username']}")

    print("\n2. Snapshot inicial de memoria de subg_halcon (id=2)")
    try:
        before = get_memory(token, HALCON_ID)
    except Exception as exc:
        log("GET memory", False, str(exc))
        return
    n_facts_before = sum(1 for m in before if m["kind"] == "fact")
    n_summ_before = sum(1 for m in before if m["kind"] == "meeting_summary")
    log("snapshot", True, f"facts={n_facts_before} summaries={n_summ_before}")

    if args.with_chat:
        print("\n3. Chat de 6 turnos con halcón (dispara extract_facts una vez)")
        try:
            res = requests.post(
                f"{BASE}/api/chat/sessions",
                headers={"Authorization": f"Bearer {token}"},
                json={"agent_id": HALCON_ID},
                timeout=10,
            )
            res.raise_for_status()
            session_id = res.json()["id"]
            log("create chat session", True, f"id={session_id}")
            mensajes = [
                "Hola, soy de la mesa de tasas. Recuerda: prefiero análisis breve, siempre en bps.",
                "¿Cómo ves la inflación subyacente?",
                "¿Y la dependencia con la Fed?",
                "Si tuvieras que decidir hoy, ¿qué votarías?",
                "¿Te preocupa el spread MX-US?",
                "Una palabra final sobre el balance de riesgos.",
            ]
            t0 = time.time()
            sent = asyncio.run(run_chat_ws(token, session_id, mensajes))
            log("chat 6 turnos", sent == 6, f"completados={sent} en {time.time()-t0:.1f}s")
            after_chat = get_memory(token, HALCON_ID)
            new_facts = sum(1 for m in after_chat if m["kind"] == "fact") - n_facts_before
            log("nuevos facts", new_facts >= 1, f"+{new_facts} facts (esperado ≥1)")
        except Exception as exc:
            log("chat flow", False, str(exc))
            return

    print("\n4. Junta (rounds=1, halcón + paloma)")
    try:
        res = requests.post(
            f"{BASE}/api/meetings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "topic": "Decisión de tasa — verificación de memoria",
                "rounds": 1,
                "agent_ids": [HALCON_ID, PALOMA_ID],
            },
            timeout=10,
        )
        res.raise_for_status()
        meeting_id = res.json()["id"]
        log("create meeting", True, f"id={meeting_id}")
        t0 = time.time()
        events = asyncio.run(run_meeting_ws(token, meeting_id))
        kinds = {e.get("type") for e in events}
        log(
            "junta corrió hasta done",
            {"phase", "vote", "decision", "minutes", "done"} <= kinds,
            f"en {time.time()-t0:.1f}s — eventos: {sorted(kinds)}",
        )
    except Exception as exc:
        log("meeting flow", False, str(exc))
        return

    print("\n5. Verificar que halcón ganó un meeting_summary tied al meeting")
    try:
        after = get_memory(token, HALCON_ID)
        new_summ = [
            m for m in after if m["kind"] == "meeting_summary" and m["source_meeting_id"] == meeting_id
        ]
        log("+1 meeting_summary", len(new_summ) == 1, f"source_meeting_id={meeting_id}")
        if new_summ:
            preview = new_summ[0]["content"][:160].replace("\n", " ")
            print(f"     preview: {preview}…")
    except Exception as exc:
        log("post-meeting check", False, str(exc))
        return

    print("\n6. Estado final de memoria de halcón:")
    final = get_memory(token, HALCON_ID)
    by_kind: dict[str, int] = {}
    for m in final:
        by_kind[m["kind"]] = by_kind.get(m["kind"], 0) + 1
    for kind, n in sorted(by_kind.items()):
        print(f"  - {kind}: {n}")

    print("\n✓ Memoria compartida verificada — chat y junta escriben/leen la misma tabla.")


if __name__ == "__main__":
    main()

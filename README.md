# Simulador de Debate Banxico

Simulador multi-agente de la Junta de Gobierno del Banco de México.

- Cinco agentes con posturas distintas (centrista, hawkish, dovish, data-dependent, externo/FX) que debaten entre sí.
- Sistema de votación (-50, -25, 0, +25, +50 bps) con desempate por la Gobernadora.
- Generación automática de minutas en Markdown por un agente Secretario.
- Herramientas: `web_search` (Tavily), `get_macro_snapshot`, `calculator`.
- Backend FastAPI + LangChain con switch Anthropic / OpenRouter.
- Frontend React + Vite + Tailwind con streaming por WebSocket.
- Dos modos: **Chat 1-a-1** y **Simulación de Junta**, con memoria persistente compartida (SQLite).

## Estructura

```
backend/   FastAPI + LangChain + SQLite
frontend/  React + Vite + Tailwind
```

## Backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # llena ANTHROPIC_API_KEY o OPENROUTER_API_KEY (y opcional TAVILY_API_KEY)
uvicorn app.main:app --reload
```

Endpoints:

- `GET /health`
- `GET /agents`, `GET /agents/{id}/memory`
- `POST /chat/sessions`, `WS /chat/ws/{session_id}`
- `POST /meetings`, `WS /meetings/ws/{id}`, `GET /meetings`, `GET /meetings/{id}`

Tests: `pytest -q` (incluye un smoke end-to-end del flujo de junta con un LLM fake).

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite proxyea `/api/*` y `/ws/*` al backend en `localhost:8000`.

## Provider

Cambiar `PROVIDER=anthropic|openrouter` en `backend/.env`. Para OpenRouter, `MODEL` debe ser un slug de OpenRouter (ej. `anthropic/claude-sonnet-4.6`). Si falta `TAVILY_API_KEY`, la herramienta de búsqueda devuelve un mensaje claro y los agentes siguen funcionando con `get_macro_snapshot`.

## Memoria persistente

La memoria vive a nivel `agent_id` en la tabla `agent_memory` (kinds: `fact`, `meeting_summary`). Tanto el modo chat como el modo junta leen y escriben sobre la misma tabla, así que lo aprendido en una junta queda disponible en los chats posteriores con cualquier miembro y viceversa.

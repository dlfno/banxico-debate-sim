from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from .config import settings

# Snapshot macro embebido para demos deterministas.
# TODO: cablear a INEGI / Banxico SIE cuando se requiera datos en vivo.
_MACRO_SNAPSHOT: dict[str, Any] = {
    "as_of": "2026-04-25",
    "banxico_target_rate_pct": 9.00,
    "fed_funds_upper_pct": 4.50,
    "inpc_yoy_pct": 4.10,
    "inpc_subyacente_yoy_pct": 3.85,
    "inpc_servicios_yoy_pct": 4.60,
    "inpc_mercancias_yoy_pct": 3.10,
    "expectativas_inflacion_12m_pct": 3.80,
    "usd_mxn": 18.20,
    "pib_yoy_pct": 1.40,
    "tasa_desempleo_pct": 2.80,
    "objetivo_inflacion_pct": 3.00,
    "fuente": "Snapshot ilustrativo (constantes embebidas)",
}


@tool("get_macro_snapshot", return_direct=False)
def get_macro_snapshot() -> dict:
    """Devuelve un snapshot reciente de variables macro relevantes para la decisión de política monetaria
    (tasa Banxico vigente, tasa Fed, INPC headline y subyacente, expectativas, USD/MXN, PIB, desempleo).
    Úsala antes de argumentar para anclar tus cifras."""
    return _MACRO_SNAPSHOT


@tool("calculator", return_direct=False)
def calculator(expression: str) -> str:
    """Evalúa una expresión aritmética simple. Acepta +, -, *, /, **, paréntesis y números.
    Útil para diferenciales de tasa, conversiones simples y porcentajes."""
    import numexpr

    try:
        value = numexpr.evaluate(expression).item()
        return str(value)
    except Exception as exc:  # pragma: no cover - defensive
        return f"calculator error: {exc}"


@tool("web_search", return_direct=False)
def web_search(query: str) -> str:
    """Busca en la web información reciente relevante (datos macro, declaraciones de la Fed, comunicados de Banxico,
    noticias de mercado). Devuelve título, URL y extracto de los principales resultados.
    Si no hay TAVILY_API_KEY configurada, devuelve un mensaje indicándolo."""
    if not settings.TAVILY_API_KEY:
        return "web_search no disponible: configurar TAVILY_API_KEY en el backend."
    try:
        from langchain_community.tools import TavilySearchResults

        searcher = TavilySearchResults(max_results=5, tavily_api_key=settings.TAVILY_API_KEY)
        results = searcher.invoke({"query": query})
        if not results:
            return "Sin resultados."
        lines = []
        for r in results:
            title = r.get("title", "(sin título)")
            url = r.get("url", "")
            content = (r.get("content") or "").strip().replace("\n", " ")
            if len(content) > 400:
                content = content[:400] + "…"
            lines.append(f"- {title}\n  {url}\n  {content}")
        return "\n".join(lines)
    except Exception as exc:  # pragma: no cover - network/dep dependent
        return f"web_search error: {exc}"


ALL_TOOLS = [get_macro_snapshot, calculator, web_search]


def tools_by_name() -> dict:
    return {t.name: t for t in ALL_TOOLS}

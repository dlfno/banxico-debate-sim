from __future__ import annotations

import logging
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
from langchain_core.tools import tool

from .config import settings

log = logging.getLogger(__name__)

# Series del SIE de Banxico que se consultan en vivo cuando BANXICO_TOKEN está configurado.
_SIE_BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1"
# SF61745 = Tasa objetivo Banxico, SF43718 = USD/MXN FIX, SL11578 = Desempleo
# (SF43936 NO se usa: es Cetes 28d, no Fed Funds — para Fed Funds usamos FRED.)
_SIE_RATES_SERIES = "SF61745,SF43718,SL11578"
# SP1 (INPC general índice, vía incremento=PorcAnual) + SP74662 (subyacente YoY ya pre-calculado)
_SIE_INPC_GENERAL_SERIES = "SP1"
_SIE_INPC_SUBYACENTE_SERIES = "SP74662"
# SI744 = Precio del Petróleo: Mezcla Mexicana (USD/barril, diario, fuente Pemex).
# Tiene huecos N/E en fines de semana y días sin publicación; se busca el último
# valor no-N/E mediante el endpoint /datos/{fechaInicio}/{fechaFin}.
_SIE_MEZCLA_MX_SERIES = "SI744"

# FRED (St. Louis Fed) — endpoint público CSV sin API key.
# Mapa: campo del snapshot → ID de serie en FRED.
#   DFEDTARU         = Federal Funds Target Range Upper (% diario)
#   CPALTT01USM659N  = CPI USA, all items, YoY % (mensual, OECD — variante "659N"
#                      = growth rate same period previous year. La "657N" es m/m,
#                      por eso devolvía ~0.6% en vez de ~2.4%.)
# Nota: WTI y Brent se obtenían antes desde FRED (DCOILWTICO/DCOILBRENTEU) pero
# ese feed tiene 3-5 días de lag. Ahora vienen de Yahoo Finance (cerca de
# tiempo real durante horas de mercado).
# La serie de Eurozona equivalente no existe en FRED; CPI Eurozona se mantiene
# en el snapshot estático.
_FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
_FRED_SERIES_MAP: dict[str, str] = {
    "fed_funds_upper_pct": "DFEDTARU",
    "inflacion_usa_yoy_pct": "CPALTT01USM659N",
}

# Yahoo Finance — JSON público para futures de commodities, sin API key.
#   CL=F = WTI Crude Oil Front Month Future (USD/bbl, intraday)
#   BZ=F = Brent Crude Oil Front Month Future (USD/bbl, intraday)
_YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
_YAHOO_SYMBOLS_MAP: dict[str, str] = {
    "wti_usd_bbl": "CL=F",
    "brent_usd_bbl": "BZ=F",
}

# Cache en memoria para el snapshot completo. Macro data no cambia minuto a minuto;
# en una junta los 5 agentes consultan el mismo snapshot, así una sola red trip
# basta para todos los turnos dentro de la ventana TTL.
_SNAPSHOT_CACHE: dict[str, Any] = {"data": None, "expires_at": 0.0}
_SNAPSHOT_TTL_SECONDS = 300  # 5 minutos

# Snapshot de respaldo con valores observados al 5 de mayo de 2026.
# Se usa cuando BANXICO_TOKEN no está configurado o la API del SIE falla.
_MACRO_SNAPSHOT_FALLBACK: dict[str, Any] = {
    "as_of": "2026-05-09",

    # Banxico — última decisión 26/mar/2026 (recorte sorpresa a 6.75 %).
    # Se anticipa un posible recorte adicional a 6.50 % en la reunión de mayo.
    "banxico_target_rate_pct": 6.75,

    # Fed — rango objetivo mantenido en 3.50–3.75 % en reunión del 29/abr/2026.
    "fed_funds_upper_pct": 3.75,

    # INPC general anual — marzo 2026 (dato mensual más reciente, INEGI 9/abr/2026).
    # 1Q-abril 2026 (quincenal) ya marcó 4.53 %; dato mensual de abril se publica 7/mayo.
    "inpc_yoy_pct": 4.59,

    # Subyacente anual — marzo 2026 (INEGI).
    "inpc_subyacente_yoy_pct": 4.45,

    # Servicios anual — marzo 2026 (INEGI, cuadro 1).
    "inpc_servicios_yoy_pct": 4.51,

    # Mercancías anual — marzo 2026 (INEGI, cuadro 1).
    "inpc_mercancias_yoy_pct": 4.38,

    # Expectativas inflación 12 meses — encuesta Banxico a analistas privados (may/2026).
    # Los analistas elevaron su estimación de inflación general 2026 a 4.35 %.
    "expectativas_inflacion_12m_pct": 4.35,

    # USD/MXN — cierre del 5/may/2026 (Infobae / Dow Jones).
    "usd_mxn": 17.38,

    # PIB a/a — estimación oportuna 1T-2026 (INEGI): +0.2 % a/a.
    # Consenso analistas privados para todo 2026: ~1.2 % (encuesta Banxico, may/2026).
    "pib_yoy_pct": 0.2,

    # Desempleo — marzo 2026, cifra desestacionalizada (ENOE/INEGI, 24/abr/2026).
    "tasa_desempleo_pct": 2.8,

    # Meta de inflación Banxico (sin cambio).
    "objetivo_inflacion_pct": 3.00,

    # ── Petróleo (referencia 09-may-2026) ──────────────────────────────────────
    # WTI — West Texas Intermediate, Cushing OK (USD/barril). Fuente live: Yahoo CL=F.
    "wti_usd_bbl": 95.42,
    # Brent — Europa (USD/barril). Fuente live: Yahoo BZ=F.
    "brent_usd_bbl": 101.29,
    # Mezcla Mexicana de exportación (USD/barril). Fuente live: Banxico SIE SI744.
    "mezcla_mx_usd_bbl": 98.50,

    # ── Inflación internacional (referencia mar-2026, último dato disponible) ──
    # CPI USA YoY — All Items (BLS, vía OECD/FRED).
    "inflacion_usa_yoy_pct": 2.40,
    # HICP Eurozona YoY — All Items (Eurostat, vía OECD/FRED).
    "inflacion_eurozona_yoy_pct": 2.00,

    "fuente": (
        "Datos observados al 09-may-2026. "
        "Fuentes: INEGI (INPC mar-2026, ENOE mar-2026, PIB 1T-2026 est. oportuna), "
        "Banxico (decisión 26-mar-2026, encuesta analistas may-2026), "
        "Fed FOMC (reunión 29-abr-2026), "
        "Banxico FIX (USD/MXN cierre 09-may-2026), "
        "Yahoo Finance / oilprice.com (WTI, Brent, Mezcla MX al 09-may-2026), "
        "BLS y Eurostat vía OECD (CPI USA y Eurozona mar-2026)."
    ),
}


def _fetch_fred_series(series_id: str) -> float | None:
    """Devuelve el último valor numérico publicado por FRED para `series_id`.
    Usa el endpoint CSV público (sin API key). None si la serie no existe o falla la red.

    FRED marca los valores faltantes como '.' (punto). Recorremos el CSV de atrás
    hacia adelante y devolvemos el primer renglón con un float válido.
    """
    url = f"{_FRED_BASE}{series_id}"
    try:
        with httpx.Client(timeout=6.0) as client:
            r = client.get(url)
            r.raise_for_status()
        for line in reversed(r.text.strip().splitlines()):
            parts = line.split(",")
            if len(parts) == 2 and parts[1] not in ("", ".", series_id):
                try:
                    return float(parts[1])
                except ValueError:
                    continue
        return None
    except Exception as exc:
        log.warning("FRED %s no disponible: %s", series_id, exc)
        return None


def _fetch_yahoo_quote(symbol: str) -> float | None:
    """Devuelve el último precio de mercado regular para un símbolo de Yahoo Finance.
    Endpoint JSON público sin API key. None si falla la red o el símbolo es inválido.

    Usa `regularMarketPrice` del meta object (precio actual durante mercado, último
    cierre fuera de horas). Si no está, walks back en el array `close` del histórico.
    """
    url = f"{_YAHOO_BASE}{symbol}?interval=1d&range=5d"
    try:
        with httpx.Client(timeout=6.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = client.get(url)
            r.raise_for_status()
        data = r.json()
        result = (data.get("chart") or {}).get("result") or []
        if not result:
            return None
        meta = result[0].get("meta") or {}
        price = meta.get("regularMarketPrice")
        if price is not None:
            return float(price)
        # Fallback: último close válido del histórico.
        closes = (
            ((result[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        )
        for v in reversed(closes):
            if v is not None:
                return float(v)
        return None
    except Exception as exc:
        log.warning("Yahoo %s no disponible: %s", symbol, exc)
        return None


def _fetch_sie_latest(token: str, series_id: str, days_back: int = 14) -> tuple[float, str] | None:
    """Trae los últimos `days_back` días de una serie del SIE y devuelve (valor, fecha)
    del último dato no-N/E. None si no hay valores publicados en la ventana o falla la API.

    Útil para series con publicación irregular (huecos en fines de semana o días sin
    dato). El endpoint /datos/oportuno devuelve solo el último día programado, que
    puede venir como N/E si Banxico aún no lo publica."""
    from datetime import date, timedelta
    fin = date.today()
    ini = fin - timedelta(days=days_back)
    url = f"{_SIE_BASE}/series/{series_id}/datos/{ini.isoformat()}/{fin.isoformat()}"
    try:
        r = httpx.get(
            url,
            headers={"Bmx-Token": token, "Accept": "application/json"},
            timeout=8.0,
        )
        r.raise_for_status()
        for serie in r.json()["bmx"]["series"]:
            if serie["idSerie"] != series_id:
                continue
            datos = serie.get("datos") or []
            for d in reversed(datos):
                raw = d.get("dato", "N/E")
                if raw in ("N/E", ""):
                    continue
                try:
                    return float(raw), d.get("fecha", "")
                except ValueError:
                    continue
        return None
    except Exception as exc:
        log.warning(
            "SIE %s rango %s/%s no disponible: %s",
            series_id, ini.isoformat(), fin.isoformat(), exc,
        )
        return None


def _fetch_sie_snapshot(token: str) -> dict | None:
    """Consulta la API REST del SIE de Banxico y devuelve un dict con los valores más recientes.
    Devuelve None si el token es inválido o la API no responde en 8 segundos."""
    headers = {"Bmx-Token": token, "Accept": "application/json"}
    result: dict[str, Any] = {}

    try:
        with httpx.Client(timeout=8.0) as client:
            # ── Tasas y tipo de cambio ──────────────────────────────────────────────
            r1 = client.get(
                f"{_SIE_BASE}/series/{_SIE_RATES_SERIES}/datos/oportuno",
                headers=headers,
            )
            r1.raise_for_status()
            for serie in r1.json()["bmx"]["series"]:
                sid = serie["idSerie"]
                datos = serie.get("datos") or []
                if not datos:
                    continue
                raw = datos[0].get("dato", "N/E")
                if raw in ("N/E", ""):
                    continue
                val = float(raw)
                fecha = datos[0].get("fecha", "")  # DD/MM/YYYY

                if sid == "SF61745":
                    result["banxico_target_rate_pct"] = val
                    if fecha:
                        d, m, y = fecha.split("/")
                        result["as_of"] = f"{y}-{m}-{d}"
                elif sid == "SF43718":
                    result["usd_mxn"] = val
                elif sid == "SL11578":
                    result["tasa_desempleo_pct"] = val

            # ── INPC general var. anual (vía SP1 + incremento=PorcAnual) ────────────
            r2 = client.get(
                f"{_SIE_BASE}/series/{_SIE_INPC_GENERAL_SERIES}/datos/oportuno",
                headers=headers,
                params={"incremento": "PorcAnual"},
            )
            r2.raise_for_status()
            for serie in r2.json()["bmx"]["series"]:
                if serie["idSerie"] != "SP1":
                    continue
                datos = serie.get("datos") or []
                if not datos:
                    continue
                raw = datos[0].get("dato", "N/E")
                if raw not in ("N/E", ""):
                    result["inpc_yoy_pct"] = float(raw)

            # ── INPC subyacente var. anual (SP74662 ya viene pre-calculada en %) ────
            r3 = client.get(
                f"{_SIE_BASE}/series/{_SIE_INPC_SUBYACENTE_SERIES}/datos/oportuno",
                headers=headers,
            )
            r3.raise_for_status()
            for serie in r3.json()["bmx"]["series"]:
                if serie["idSerie"] != "SP74662":
                    continue
                datos = serie.get("datos") or []
                if not datos:
                    continue
                raw = datos[0].get("dato", "N/E")
                if raw not in ("N/E", ""):
                    result["inpc_subyacente_yoy_pct"] = float(raw)

        # ── Fuentes externas en paralelo ───────────────────────────────────────────
        # FRED (Fed Funds, CPI USA), Yahoo Finance (WTI, Brent intra-day) y
        # SIE Banxico (Mezcla Mexicana SI744 con búsqueda hacia atrás del último
        # valor publicado). Cada fetch es best-effort: si falla, el campo cae
        # al snapshot estático sin afectar a los demás. Todos corren en paralelo
        # para que el costo total sea ~max(timeouts) en vez de la suma.
        total_jobs = len(_FRED_SERIES_MAP) + len(_YAHOO_SYMBOLS_MAP) + 1  # +1 SI744
        with ThreadPoolExecutor(max_workers=total_jobs) as pool:
            fred_futs = {
                field: pool.submit(_fetch_fred_series, sid)
                for field, sid in _FRED_SERIES_MAP.items()
            }
            yahoo_futs = {
                field: pool.submit(_fetch_yahoo_quote, sym)
                for field, sym in _YAHOO_SYMBOLS_MAP.items()
            }
            mezcla_fut = pool.submit(_fetch_sie_latest, token, _SIE_MEZCLA_MX_SERIES)

            for field, fut in fred_futs.items():
                val = fut.result()
                if val is not None:
                    result[field] = val
            for field, fut in yahoo_futs.items():
                val = fut.result()
                if val is not None:
                    result[field] = val
            mezcla_result = mezcla_fut.result()
            if mezcla_result is not None:
                value, _fecha = mezcla_result
                result["mezcla_mx_usd_bbl"] = value

        return result if result else None

    except Exception as exc:
        log.warning("SIE API no disponible, usando snapshot de respaldo: %s", exc)
        return None


def _build_snapshot() -> dict:
    """Construye un snapshot fresco combinando fallback estático + datos en vivo."""
    snapshot = dict(_MACRO_SNAPSHOT_FALLBACK)
    if settings.BANXICO_TOKEN:
        t0 = time.perf_counter()
        live = _fetch_sie_snapshot(settings.BANXICO_TOKEN)
        elapsed = time.perf_counter() - t0
        if live:
            snapshot.update(live)
            snapshot["fuente"] = (
                "Datos en vivo: Banxico SIE (tasa objetivo, USD/MXN, INPC general y "
                "subyacente, desempleo, Mezcla Mexicana SI744) + Yahoo Finance "
                "(WTI futures CL=F, Brent futures BZ=F) + FRED St. Louis (Fed Funds "
                "upper, CPI USA YoY). "
                "CPI Eurozona, mercancías/servicios YoY, expectativas, PIB y meta de "
                "inflación toman valores del snapshot observado al 9-may-2026."
            )
            log.info("macro snapshot fresco en %.2fs (%d campos en vivo)", elapsed, len(live))
        else:
            snapshot["fuente"] += " [SIE no disponible, usando respaldo]"
            log.warning("macro snapshot: SIE no respondió en %.2fs", elapsed)
    return snapshot


@tool("get_macro_snapshot", return_direct=False)
def get_macro_snapshot() -> dict:
    """Devuelve un snapshot reciente de variables macro relevantes para la decisión de política monetaria
    (tasa Banxico, Fed Funds, INPC México headline/subyacente, expectativas, USD/MXN, PIB, desempleo,
    precios del petróleo WTI/Brent/Mezcla MX, y CPI YoY de USA y Eurozona).
    Úsala antes de argumentar para anclar tus cifras."""
    now = time.time()
    cached = _SNAPSHOT_CACHE.get("data")
    if cached and now < _SNAPSHOT_CACHE.get("expires_at", 0):
        # Devolvemos copia para que el caller no mute el cache compartido.
        return dict(cached)
    snapshot = _build_snapshot()
    _SNAPSHOT_CACHE["data"] = snapshot
    _SNAPSHOT_CACHE["expires_at"] = now + _SNAPSHOT_TTL_SECONDS
    return dict(snapshot)


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


# ── consult_banxico_history ────────────────────────────────────────────────
# Búsqueda por keywords sobre los .md de minutas y análisis oficiales de
# Banxico (carpeta backend/app/data/banxico_history/). Sin red trip.

_BANXICO_HISTORY_DIR = Path(__file__).resolve().parent / "data" / "banxico_history"
# Cache: {filename: [paragraph, ...]} cargado al primer uso.
_BANXICO_HISTORY_CACHE: dict[str, list[str]] = {}


def _strip_accents(text: str) -> str:
    """Quita acentos para búsqueda case/diacrítico-insensitiva."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    return _strip_accents(text.lower())


def _load_banxico_history() -> dict[str, list[str]]:
    """Carga (con cache) todos los .md del directorio history como listas de
    párrafos. Un párrafo es un bloque separado por línea(s) en blanco.

    Las líneas que son solo un heading Markdown ('# Título') se fusionan con
    el párrafo siguiente para que la búsqueda no devuelva headers sueltos.
    """
    if _BANXICO_HISTORY_CACHE:
        return _BANXICO_HISTORY_CACHE
    if not _BANXICO_HISTORY_DIR.is_dir():
        log.warning("Carpeta banxico_history no existe: %s", _BANXICO_HISTORY_DIR)
        return {}
    for md in sorted(_BANXICO_HISTORY_DIR.glob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except Exception as exc:
            log.warning("No se pudo leer %s: %s", md.name, exc)
            continue
        # Quitamos front-matter YAML si existe.
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                text = parts[2]
        raw_blocks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        # Fusiona headings sueltos con el bloque siguiente.
        merged: list[str] = []
        pending_header = ""
        for block in raw_blocks:
            is_header_only = block.lstrip().startswith("#") and "\n" not in block
            if is_header_only:
                pending_header = block.lstrip("# ").strip()
                continue
            if pending_header:
                merged.append(f"[{pending_header}] {block}")
                pending_header = ""
            else:
                merged.append(block)
        if pending_header:  # header al final sin cuerpo
            merged.append(pending_header)
        _BANXICO_HISTORY_CACHE[md.name] = merged
    return _BANXICO_HISTORY_CACHE


@tool("consult_banxico_history", return_direct=False)
def consult_banxico_history(query: str) -> str:
    """Consulta las minutas y análisis oficiales recientes de la Junta de Gobierno
    de Banxico (decisiones de política monetaria de mar-2026 y may-2026).
    Devuelve hasta 2 párrafos relevantes con cita de la fuente y la fecha. Útil
    para citar literalmente decisiones, votos, argumentos de miembros disidentes
    (Heath, Borja Gómez), pronósticos o el balance de riesgos.

    IMPORTANTE: una sola llamada bien formulada basta. NO la invoques varias veces
    con queries parecidas — combina tus palabras clave en una query (nombres de
    miembros, conceptos macro, fechas). Ejemplos: "Heath Borja disidencia votación
    marzo", "decisión mayo cierre ciclo 6.50", "frutas verduras jitomate inflación"."""
    docs = _load_banxico_history()
    if not docs:
        return "No hay minutas disponibles en la base de conocimiento."

    norm_query = _normalize(query)
    keywords = [w for w in re.split(r"\W+", norm_query) if len(w) >= 3]
    if not keywords:
        return (
            "Query muy corta o vacía. Usa al menos una palabra clave de 3+ letras "
            "(ej. 'Heath disidente', 'votación marzo', 'frutas verduras')."
        )

    # Score cada párrafo: cuántos keywords distintos aparecen, ponderado por
    # densidad (matches / sqrt(palabras)). Ignora bloques muy cortos (headers,
    # separadores de tabla) que solo agregan ruido.
    scored: list[tuple[float, str, str]] = []
    for fname, paragraphs in docs.items():
        for para in paragraphs:
            if len(para) < 50:
                continue
            norm_para = _normalize(para)
            matches = sum(1 for kw in keywords if kw in norm_para)
            if matches == 0:
                continue
            words = max(len(norm_para.split()), 1)
            density = matches / (words ** 0.5)
            scored.append((density, fname, para))

    if not scored:
        return (
            f"No se encontraron pasajes que coincidan con: '{query}'. "
            "Probar palabras clave distintas (nombres de miembros, conceptos macro, fechas)."
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:2]  # 2 pasajes bastan; más solo infla el contexto y ralentiza
    out_lines: list[str] = []
    for _, fname, para in top:
        # fname suele ser '2026-05-07_decision.md' → extrae fecha legible.
        m = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
        fecha = m.group(1) if m else fname
        snippet = (para[:700] + "…") if len(para) > 700 else para
        out_lines.append(f"[fuente: {fname} · {fecha}]\n{snippet}")
    return "\n\n".join(out_lines)


ALL_TOOLS = [get_macro_snapshot, calculator, web_search, consult_banxico_history]


def tools_by_name() -> dict:
    return {t.name: t for t in ALL_TOOLS}

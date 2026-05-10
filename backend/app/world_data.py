"""Datos para el mapa mundial: indicadores macro por país (World Bank, en vivo
con cache), rutas/cuellos de botella del petróleo y lista curada de conflictos.

- Inflación y PIB: World Bank API (gratis, sin API key).
- Deuda externa total: World Bank (solo países de ingreso bajo/medio la reportan).
- Deuda pública % del PIB: World Bank (cobertura más amplia, métrica distinta).
- Rutas de petróleo: cifras aproximadas de la EIA (estáticas).
- Conflictos: lista curada — pendiente de definir con el usuario.

Datos REALES: si el World Bank no tiene un valor para un país, ese campo queda
en None y el frontend lo muestra como "—". No se inventan cifras.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

log = logging.getLogger(__name__)

# ── World Bank API ─────────────────────────────────────────────────────────
# mrnev=1 = "most recent non-empty value": una fila por país, el año más
# reciente con dato. per_page alto para traer todo en una página.
_WB_BASE = "https://api.worldbank.org/v2/country/all/indicator/{indicator}"
_WB_INDICATORS: dict[str, str] = {
    "inflation": "FP.CPI.TOTL.ZG",            # Inflación, precios al consumidor, anual %
    "gdp_usd": "NY.GDP.MKTP.CD",              # PIB, US$ corrientes
    "external_debt_usd": "DT.DOD.DECT.CD",    # Deuda externa total, US$ (ingreso bajo/medio)
    "public_debt_pct_gdp": "GC.DOD.TOTL.GD.ZS",  # Deuda del gobierno central, % del PIB
}
_WB_INDICATOR_META: dict[str, dict] = {
    "inflation": {"label": "Inflación anual (%)", "unit": "%", "source": "World Bank · FP.CPI.TOTL.ZG"},
    "gdp_usd": {"label": "PIB (US$ corrientes)", "unit": "USD", "source": "World Bank · NY.GDP.MKTP.CD"},
    "external_debt_usd": {"label": "Deuda externa total (US$)", "unit": "USD", "source": "World Bank · DT.DOD.DECT.CD"},
    "public_debt_pct_gdp": {"label": "Deuda pública (% del PIB)", "unit": "%", "source": "World Bank · GC.DOD.TOTL.GD.ZS"},
}

# Cache del payload completo. World Bank publica datos anuales -> TTL largo.
_WORLD_CACHE: dict[str, Any] = {"data": None, "expires_at": 0.0}
_WORLD_TTL_SECONDS = 6 * 3600  # 6 horas


def _fetch_wb_indicator(indicator: str) -> dict[str, dict]:
    """Devuelve {iso3: {value, year}} para el indicador WB dado (último año con dato).
    Si la API falla devuelve {} (best-effort)."""
    url = _WB_BASE.format(indicator=indicator)
    params = {"format": "json", "per_page": "400", "mrnev": "1"}
    try:
        with httpx.Client(timeout=12.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
            return {}
        out: dict[str, dict] = {}
        for row in payload[1]:
            iso3 = (row.get("countryiso3code") or "").strip()
            val = row.get("value")
            year = row.get("date")
            if not iso3 or len(iso3) != 3 or val is None:
                continue
            try:
                out[iso3] = {"value": float(val), "year": year}
            except (TypeError, ValueError):
                continue
        return out
    except Exception as exc:
        log.warning("World Bank %s no disponible: %s", indicator, exc)
        return {}


def _fetch_wb_country_names() -> dict[str, str]:
    """Devuelve {iso3: nombre del país} del listado del WB. Excluye agregados
    (regiones, grupos de ingreso)."""
    try:
        with httpx.Client(timeout=12.0) as client:
            r = client.get(
                "https://api.worldbank.org/v2/country",
                params={"format": "json", "per_page": "400"},
            )
            r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
            return {}
        out: dict[str, str] = {}
        for row in payload[1]:
            iso3 = (row.get("id") or "").strip()
            name = (row.get("name") or "").strip()
            region = (row.get("region") or {}).get("value", "")
            if iso3 and name and region and region != "Aggregates":
                out[iso3] = name
        return out
    except Exception as exc:
        log.warning("World Bank country list no disponible: %s", exc)
        return {}


# ── Rutas / cuellos de botella del petróleo ────────────────────────────────
# Cifras aproximadas de la EIA (U.S. Energy Information Administration), en
# millones de barriles diarios (mbd) de petróleo y productos. Coords [lon, lat].
OIL_CHOKEPOINTS: list[dict] = [
    {"name": "Estrecho de Ormuz", "coord": [56.3, 26.6], "flow_mbd": 21.0,
     "note": "~21% del petróleo líquido mundial. Entre Irán y Omán/EAU. Sin ruta alterna."},
    {"name": "Estrecho de Malaca", "coord": [101.0, 2.5], "flow_mbd": 17.0,
     "note": "Conecta el Índico con Asia oriental. Indonesia/Malasia/Singapur."},
    {"name": "Canal de Suez + oleoducto SUMED", "coord": [32.5, 30.0], "flow_mbd": 9.0,
     "note": "~9% del petróleo marítimo. Egipto. Alternativa: rodear el Cabo de Buena Esperanza."},
    {"name": "Bab el-Mandeb", "coord": [43.4, 12.6], "flow_mbd": 8.0,
     "note": "Entrada sur del Mar Rojo. Entre Yemen y Yibuti/Eritrea."},
    {"name": "Estrechos Turcos (Bósforo y Dardanelos)", "coord": [29.0, 41.0], "flow_mbd": 3.0,
     "note": "Salida del Mar Negro al Mediterráneo. Crudo ruso y del Caspio."},
    {"name": "Estrechos Daneses", "coord": [11.0, 56.0], "flow_mbd": 3.0,
     "note": "Salida del Báltico hacia el Atlántico. Exportaciones rusas."},
    {"name": "Canal de Panamá", "coord": [-79.7, 9.0], "flow_mbd": 1.5,
     "note": "Conecta Atlántico y Pacífico. Productos refinados y GLP."},
    {"name": "Cabo de Buena Esperanza", "coord": [18.5, -34.4], "flow_mbd": 6.0,
     "note": "Ruta alterna (más larga) al Suez/Bab el-Mandeb. Sudáfrica."},
]

# ── Países en conflicto armado / tensión geopolítica ───────────────────────
# LISTA CURADA — pendiente de que el usuario la proporcione.
# Formato de cada entrada:
#   {"iso3": "XXX", "name": "...", "status": "Conflicto armado activo" | "Tensión geopolítica",
#    "note": "descripción breve", "source": "fuente"}
CONFLICT_COUNTRIES: list[dict] = [
    # El usuario proporcionará la lista. Mientras esté vacía, el mapa no marca
    # ningún país en rojo (todo lo demás funciona igual).
]


def get_world_map_data() -> dict:
    """Ensambla el payload del mapa mundial. Cachea 6h. Best-effort: si World
    Bank falla parcialmente, devuelve los países que sí se obtuvieron."""
    now = time.time()
    cached = _WORLD_CACHE.get("data")
    if cached and now < _WORLD_CACHE.get("expires_at", 0):
        return cached

    t0 = time.perf_counter()
    # Fetch de los 4 indicadores + el listado de nombres, en paralelo.
    with ThreadPoolExecutor(max_workers=len(_WB_INDICATORS) + 1) as pool:
        ind_futs = {key: pool.submit(_fetch_wb_indicator, ind) for key, ind in _WB_INDICATORS.items()}
        names_fut = pool.submit(_fetch_wb_country_names)
        results = {key: fut.result() for key, fut in ind_futs.items()}
        names = names_fut.result()

    all_iso3: set[str] = set()
    for d in results.values():
        all_iso3.update(d.keys())

    countries: dict[str, dict] = {}
    for iso3 in sorted(all_iso3):
        entry: dict[str, Any] = {"name": names.get(iso3, iso3)}
        has_any = False
        for key in _WB_INDICATORS:
            d = results[key].get(iso3)
            if d:
                entry[key] = d["value"]
                entry[f"{key}_year"] = d["year"]
                has_any = True
            else:
                entry[key] = None
                entry[f"{key}_year"] = None
        if has_any:
            countries[iso3] = entry

    elapsed = time.perf_counter() - t0
    log.info("world map data: %d países en %.2fs (cache 6h)", len(countries), elapsed)

    payload = {
        "countries": countries,
        "indicators": _WB_INDICATOR_META,
        "oil_chokepoints": OIL_CHOKEPOINTS,
        "conflicts": CONFLICT_COUNTRIES,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
    }
    _WORLD_CACHE["data"] = payload
    _WORLD_CACHE["expires_at"] = now + _WORLD_TTL_SECONDS
    return payload

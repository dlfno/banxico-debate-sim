import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { WorldCountry, WorldMapData } from "../types";

// ECharts se carga desde CDN en index.html → disponible como window.echarts.
declare global {
  interface Window {
    echarts: any;
  }
}

// GeoJSON mundial: cada feature tiene `id` = ISO3 y `properties.name` = nombre.
// Lo pre-procesamos para que la "región" de ECharts sea el ISO3 (así casa
// directamente con los datos del World Bank, que vienen keyed por ISO3).
const WORLD_GEOJSON_URL =
  "https://cdn.jsdelivr.net/gh/johan/world.geo.json@master/countries.geo.json";

type MetricKey = "inflation" | "gdp_usd" | "external_debt_usd" | "public_debt_pct_gdp";

function formatUSD(v: number): string {
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)} billones`; // 10^12
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)} mil M`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)} M`;
  return `$${v.toLocaleString("es-MX")}`;
}

// Color del país según la intensidad del conflicto.
const TENSION_COLOR: Record<"alta" | "media" | "baja", string> = {
  alta: "#991b1b",
  media: "#dc2626",
  baja: "#f87171",
};
const TENSION_LABEL: Record<"alta" | "media" | "baja", string> = {
  alta: "Alta — conflicto armado activo",
  media: "Media — conflicto / inestabilidad",
  baja: "Baja — tensión latente",
};
const TENSION_ORDER: Array<"alta" | "media" | "baja"> = ["alta", "media", "baja"];

const METRICS: Record<
  MetricKey,
  {
    label: string;
    short: string;
    log: boolean;
    get: (c: WorldCountry) => number | null;
    year: (c: WorldCountry) => string | null;
    format: (v: number) => string;
    colors: string[];
  }
> = {
  inflation: {
    label: "Inflación anual (%)",
    short: "Inflación",
    log: false,
    get: (c) => c.inflation,
    year: (c) => c.inflation_year,
    format: (v) => `${v.toFixed(1)} %`,
    colors: ["#1d7a7a", "#7fc4b8", "#f4ede0", "#f0a868", "#dc2626"],
  },
  gdp_usd: {
    label: "PIB (US$ corrientes)",
    short: "PIB",
    log: true,
    get: (c) => c.gdp_usd,
    year: (c) => c.gdp_usd_year,
    format: (v) => formatUSD(v),
    colors: ["#f4ede0", "#cde3df", "#7fc4b8", "#1d7a7a", "#0f4847"],
  },
  external_debt_usd: {
    label: "Deuda externa total (US$)",
    short: "Deuda ext.",
    log: true,
    get: (c) => c.external_debt_usd,
    year: (c) => c.external_debt_usd_year,
    format: (v) => formatUSD(v),
    colors: ["#f4ede0", "#f0d8a8", "#f0a868", "#e07b3a", "#b85c1a"],
  },
  public_debt_pct_gdp: {
    label: "Deuda pública (% del PIB)",
    short: "Deuda púb. %",
    log: false,
    get: (c) => c.public_debt_pct_gdp,
    year: (c) => c.public_debt_pct_gdp_year,
    format: (v) => `${v.toFixed(0)} %`,
    colors: ["#1d7a7a", "#7fc4b8", "#f4ede0", "#f0a868", "#dc2626"],
  },
};

function useWorldGeoJson() {
  const [geo, setGeo] = useState<any | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    fetch(WORLD_GEOJSON_URL)
      .then((r) => r.json())
      .then((json) => {
        if (cancelled) return;
        // Reescribe properties.name = id (ISO3) para que ECharts indexe por ISO3.
        for (const f of json.features || []) {
          f.properties = { ...(f.properties || {}), name: f.id };
        }
        setGeo(json);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, []);
  return { geo, error };
}

export default function WorldMapPage() {
  const data = useQuery({ queryKey: ["world-map"], queryFn: api.getWorldMap });
  const { geo, error: geoError } = useWorldGeoJson();
  const [metric, setMetric] = useState<MetricKey>("inflation");
  const [search, setSearch] = useState("");
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstance = useRef<any>(null);

  const conflictsByIso = useMemo(() => {
    const m = new Map<string, WorldMapData["conflicts"][number]>();
    for (const c of data.data?.conflicts || []) m.set(c.iso3, c);
    return m;
  }, [data.data]);

  // Lista de países para el buscador.
  const countryList = useMemo(() => {
    const entries = Object.entries(data.data?.countries || {});
    return entries
      .map(([iso3, c]) => ({ iso3, name: c.name }))
      .sort((a, b) => a.name.localeCompare(b.name, "es"));
  }, [data.data]);

  const filteredCountries = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return [];
    return countryList.filter((c) => c.name.toLowerCase().includes(q)).slice(0, 8);
  }, [countryList, search]);

  // Construye la opción de ECharts.
  const option = useMemo(() => {
    if (!data.data || !geo) return null;
    const cfg = METRICS[metric];
    const countries = data.data.countries;

    // Datos del choropleth (keyed por ISO3). Para los conflictos sobreescribimos
    // el color del item según la intensidad (override del visualMap).
    const seriesData: any[] = [];
    const seen = new Set<string>();
    let min = Infinity;
    let max = -Infinity;
    for (const [iso3, c] of Object.entries(countries)) {
      const raw = cfg.get(c);
      if (raw === null || raw === undefined) continue;
      const mapped = cfg.log ? Math.log10(Math.max(raw, 1)) : raw;
      if (mapped < min) min = mapped;
      if (mapped > max) max = mapped;
      const conf = conflictsByIso.get(iso3);
      seriesData.push({
        name: iso3,
        value: mapped,
        rawValue: raw,
        itemStyle: conf ? { areaColor: TENSION_COLOR[conf.tension], borderColor: "#fff" } : undefined,
      });
      seen.add(iso3);
    }
    if (!Number.isFinite(min)) {
      min = 0;
      max = 1;
    }
    // Países en conflicto sin dato de la métrica: igual los pintamos en su color
    // de tensión (con value = min para que ECharts no los deje sin pintar).
    for (const [iso3, conf] of conflictsByIso) {
      if (seen.has(iso3)) continue;
      seriesData.push({
        name: iso3,
        value: min,
        rawValue: null,
        itemStyle: { areaColor: TENSION_COLOR[conf.tension], borderColor: "#fff" },
      });
      seen.add(iso3);
    }

    const chokepoints = data.data.oil_chokepoints.map((cp) => ({
      name: cp.name,
      value: [cp.coord[0], cp.coord[1], cp.flow_mbd],
      note: cp.note,
    }));

    const tooltipFormatter = (p: any) => {
      // effectScatter (rutas de petróleo)
      if (p.seriesType === "effectScatter") {
        return `<div style="max-width:240px"><b>🛢 ${p.name}</b><br/>` +
          `Flujo aprox.: <b>${p.value[2]} M bbl/día</b><br/>` +
          `<span style="color:#666;font-size:11px">${p.data.note}</span></div>`;
      }
      // Choropleth (país). p.name = ISO3.
      const iso3 = p.name;
      const c = countries[iso3];
      const conf = conflictsByIso.get(iso3);
      const displayName = c?.name || conf?.name || iso3;
      const confLine = conf
        ? `<div style="margin-top:6px;padding:4px 6px;background:#fee2e2;border-radius:4px;color:#991b1b;font-size:11px">` +
          `⚠️ ${conf.status} (tensión ${conf.tension}): ${conf.note}</div>`
        : "";
      if (!c) {
        // País sin datos macro del World Bank (ej. Taiwán). Mostramos solo nombre + conflicto.
        return `<div style="min-width:200px"><b style="font-size:13px">${displayName}</b>` +
          `<div style="color:#888;font-size:11px;margin-top:2px">Sin datos macro del World Bank.</div>${confLine}</div>`;
      }
      const row = (label: string, raw: number | null, year: string | null, fmt: (v: number) => string) =>
        raw === null || raw === undefined
          ? `<tr><td style="color:#888">${label}</td><td style="text-align:right;color:#aaa">—</td><td></td></tr>`
          : `<tr><td style="color:#555">${label}</td><td style="text-align:right;font-weight:600">${fmt(raw)}</td>` +
            `<td style="color:#aaa;font-size:10px;padding-left:6px">${year ?? ""}</td></tr>`;
      return (
        `<div style="min-width:230px"><b style="font-size:13px">${displayName}</b>` +
        `<table style="font-size:12px;margin-top:4px;width:100%">` +
        row("Inflación anual", c.inflation, c.inflation_year, (v) => `${v.toFixed(1)} %`) +
        row("PIB", c.gdp_usd, c.gdp_usd_year, formatUSD) +
        row("Deuda externa total", c.external_debt_usd, c.external_debt_usd_year, formatUSD) +
        row("Deuda pública", c.public_debt_pct_gdp, c.public_debt_pct_gdp_year, (v) => `${v.toFixed(0)} % PIB`) +
        `</table>${confLine}</div>`
      );
    };

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        confine: true,
        borderColor: "#d6c9a4",
        formatter: tooltipFormatter,
      },
      visualMap: {
        type: "continuous",
        min,
        max,
        calculable: true,
        left: 16,
        bottom: 16,
        itemHeight: 160,
        text: ["alto", "bajo"],
        textStyle: { color: "#444", fontSize: 11 },
        inRange: { color: cfg.colors },
        // Etiquetas del eje del visualMap: si la métrica es log, mostramos el valor real.
        formatter: cfg.log
          ? (v: number) => formatUSD(Math.pow(10, v))
          : (v: number) => cfg.format(v),
        seriesIndex: 0,
      },
      geo: {
        map: "world",
        roam: true,
        scaleLimit: { min: 1, max: 8 },
        itemStyle: { areaColor: "#ece4d2", borderColor: "#fff", borderWidth: 0.5 },
        emphasis: { itemStyle: { areaColor: "#114a2a" }, label: { show: false } },
        select: { itemStyle: { areaColor: "#196239" }, label: { show: false } },
      },
      series: [
        {
          name: cfg.label,
          type: "map",
          map: "world",
          geoIndex: 0,
          data: seriesData,
          selectedMode: "single",
        },
        {
          name: "Rutas / cuellos de botella del petróleo",
          type: "effectScatter",
          coordinateSystem: "geo",
          geoIndex: 0,
          zlevel: 2,
          data: chokepoints,
          symbolSize: (val: number[]) => Math.max(8, Math.min(28, val[2] * 1.1)),
          rippleEffect: { brushType: "stroke", scale: 2.6 },
          itemStyle: { color: "#0c1d3a", shadowBlur: 6, shadowColor: "rgba(0,0,0,0.3)" },
          label: {
            show: true,
            formatter: "{b}",
            position: "right",
            color: "#0c1d3a",
            fontSize: 9,
            fontWeight: 600,
          },
        },
      ],
    };
  }, [data.data, geo, metric, conflictsByIso]);

  // Inicializa / actualiza el chart.
  useEffect(() => {
    if (!chartRef.current || !geo || !window.echarts || !option) return;
    window.echarts.registerMap("world", geo);
    if (!chartInstance.current) {
      chartInstance.current = window.echarts.init(chartRef.current);
    }
    chartInstance.current.setOption(option, true);
    const onResize = () => chartInstance.current?.resize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [geo, option]);

  useEffect(() => {
    return () => {
      chartInstance.current?.dispose();
      chartInstance.current = null;
    };
  }, []);

  function focusCountry(iso3: string, name: string) {
    setSearch(name);
    const ch = chartInstance.current;
    if (!ch) return;
    ch.dispatchAction({ type: "downplay", seriesIndex: 0 });
    ch.dispatchAction({ type: "highlight", seriesIndex: 0, name: iso3 });
    ch.dispatchAction({ type: "showTip", seriesIndex: 0, name: iso3 });
  }

  const loading = data.isLoading || (!geo && !geoError);
  const hasError = data.isError || geoError;

  return (
    <div>
      {/* Encabezado */}
      <div className="bg-white border-b border-sand-200">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="text-[10px] uppercase tracking-[0.22em] text-accent-600 font-semibold mb-1">
            Contexto global
          </div>
          <h1 className="font-serif text-2xl text-banxico-700">Mapa mundial macro</h1>
          <p className="text-sm text-stone-600 mt-2 max-w-3xl leading-relaxed">
            Inflación, PIB y deuda por país (datos del World Bank, último año disponible),
            países en conflicto marcados en rojo y los principales cuellos de botella del
            transporte de petróleo. Pasa el cursor sobre un país para ver sus indicadores.
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 md:px-6 py-6 grid grid-cols-12 gap-4">
        {/* Panel de control */}
        <aside className="col-span-12 lg:col-span-3 space-y-4">
          <div className="institutional-card p-4">
            <h3 className="section-title mb-3">Colorear el mapa por</h3>
            <div className="space-y-1.5">
              {(Object.keys(METRICS) as MetricKey[]).map((k) => (
                <button
                  key={k}
                  onClick={() => setMetric(k)}
                  className={`w-full text-left px-3 py-2 rounded-md text-sm border transition ${
                    metric === k
                      ? "bg-banxico-700 text-white border-banxico-700"
                      : "bg-white border-sand-200 text-stone-700 hover:border-accent-500"
                  }`}
                >
                  {METRICS[k].label}
                </button>
              ))}
            </div>
          </div>

          <div className="institutional-card p-4">
            <h3 className="section-title mb-2">Buscar país</h3>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Ej. México, Brasil…"
              className="input-institutional text-sm"
            />
            {filteredCountries.length > 0 && (
              <ul className="mt-2 border border-sand-200 rounded-md divide-y divide-sand-100 overflow-hidden">
                {filteredCountries.map((c) => (
                  <li key={c.iso3}>
                    <button
                      onClick={() => focusCountry(c.iso3, c.name)}
                      className="w-full text-left px-3 py-1.5 text-sm hover:bg-accent-50 transition"
                    >
                      {c.name} <span className="text-stone-400 text-xs">({c.iso3})</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-stone-500 mt-2">
              Click en un resultado para resaltarlo en el mapa. También puedes hacer zoom y
              arrastrar el mapa con el mouse.
            </p>
          </div>

          {/* Cuellos de botella del petróleo */}
          {data.data && (
            <div className="institutional-card p-4">
              <h3 className="section-title mb-2">🛢 Rutas del petróleo</h3>
              <ul className="text-xs text-stone-700 space-y-2">
                {data.data.oil_chokepoints.map((cp) => (
                  <li key={cp.name}>
                    <span className="font-medium text-banxico-700">{cp.name}</span>{" "}
                    <span className="text-accent-700">· ~{cp.flow_mbd} M bbl/día</span>
                    <div className="text-stone-500 leading-snug">{cp.note}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Conflictos */}
          {data.data && (
            <div className="institutional-card p-4">
              <h3 className="section-title mb-2">
                ⚠️ Países en conflicto ({data.data.conflicts.length})
              </h3>
              {data.data.conflicts.length === 0 ? (
                <p className="text-xs text-stone-500">
                  Lista pendiente de definir — aún no hay países marcados en rojo.
                </p>
              ) : (
                <div className="space-y-3">
                  {TENSION_ORDER.map((t) => {
                    const items = data.data!.conflicts.filter((c) => c.tension === t);
                    if (items.length === 0) return null;
                    return (
                      <div key={t}>
                        <div className="flex items-center gap-1.5 mb-1">
                          <span
                            className="inline-block w-2.5 h-2.5 rounded-sm"
                            style={{ background: TENSION_COLOR[t] }}
                          />
                          <span className="text-[10px] uppercase tracking-wider font-semibold text-stone-600">
                            {TENSION_LABEL[t]} ({items.length})
                          </span>
                        </div>
                        <ul className="text-xs text-stone-700 space-y-1.5 pl-1">
                          {items.map((c) => (
                            <li key={c.iso3}>
                              <button
                                onClick={() => focusCountry(c.iso3, c.name)}
                                className="font-medium text-banxico-700 hover:underline text-left"
                              >
                                {c.name}
                              </button>
                              <div className="text-stone-500 leading-snug">{c.note}</div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                  <p className="text-[10px] text-stone-400 pt-1 border-t border-sand-200">
                    Fuente: {data.data.conflicts[0]?.source}
                  </p>
                </div>
              )}
            </div>
          )}
        </aside>

        {/* Mapa */}
        <section className="col-span-12 lg:col-span-9">
          <div className="institutional-card overflow-hidden">
            <div className="px-5 py-3 bg-banxico-700 text-white border-b-2 border-accent-600 flex items-center justify-between">
              <span className="font-serif text-base">{METRICS[metric].label}</span>
              {data.data && (
                <span className="text-[10px] text-white/60">
                  Fuente: {data.data.indicators[metric]?.source} · datos al{" "}
                  {data.data.generated_at?.slice(0, 10)}
                </span>
              )}
            </div>
            {loading && (
              <div className="h-[70vh] min-h-[480px] flex items-center justify-center text-stone-500 text-sm">
                Cargando mapa…
              </div>
            )}
            {hasError && !loading && (
              <div className="h-[70vh] min-h-[480px] flex items-center justify-center text-red-700 text-sm">
                No se pudo cargar el mapa. (¿Bloqueo de CDN o del World Bank API?)
              </div>
            )}
            {!loading && !hasError && (
              <div ref={chartRef} className="h-[70vh] min-h-[480px] w-full bg-sand-50/40" />
            )}
          </div>
          <p className="text-xs text-stone-500 mt-2">
            Países en gris claro: el World Bank no reporta el indicador seleccionado para ese
            país. Países en rojo: conflicto armado / tensión geopolítica (ver panel). Datos
            reales del World Bank y la EIA — no se muestran cifras estimadas.
          </p>
        </section>
      </div>
    </div>
  );
}

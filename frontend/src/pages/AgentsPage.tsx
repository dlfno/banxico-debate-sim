import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Agent } from "../types";

const STANCE_TONE: Record<string, string> = {
  hawkish: "bg-red-50 text-red-700 border-red-200",
  dovish: "bg-sky-50 text-sky-700 border-sky-200",
  centrista: "bg-amber-50 text-amber-700 border-amber-200",
  "data-dependent": "bg-violet-50 text-violet-700 border-violet-200",
  "externo/FX": "bg-accent-50 text-accent-700 border-accent-100",
};

function AgentDetailCard({ agent }: { agent: Agent }) {
  const desc = agent.description;
  const tone = STANCE_TONE[agent.stance] || "bg-stone-50 text-stone-700 border-stone-200";

  return (
    <article className="institutional-card overflow-hidden flex flex-col">
      <header className="bg-banxico-700 text-white px-5 py-4 border-b-4 border-accent-600 flex items-start gap-4">
        <div className="text-4xl leading-none">{agent.avatar || "👤"}</div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/60 font-medium">
            {agent.role}
          </div>
          <h3 className="font-serif text-xl text-white leading-tight">{agent.display_name}</h3>
          {desc?.tagline && (
            <p className="text-sm text-white/80 italic mt-0.5">{desc.tagline}</p>
          )}
        </div>
        <span
          className={`text-[10px] uppercase tracking-wide font-semibold px-2 py-0.5 rounded-full border ${tone}`}
        >
          {agent.stance}
        </span>
      </header>

      <div className="p-5 flex-1 flex flex-col gap-4 bg-white">
        {desc ? (
          <>
            <p className="text-sm text-stone-700 leading-relaxed">{desc.summary}</p>

            <section>
              <h4 className="section-title mb-2">Foco principal</h4>
              <ul className="text-sm text-stone-700 space-y-1">
                {desc.focus.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="text-accent-600 mt-0.5">▸</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h4 className="section-title mb-2">Habilidades técnicas</h4>
              <ul className="text-sm text-stone-700 space-y-1">
                {desc.skills.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="text-accent-600 mt-0.5">▸</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h4 className="section-title mb-2">Datos que prioriza</h4>
              <ul className="flex flex-wrap gap-1.5">
                {desc.data_sources.map((item) => (
                  <li
                    key={item}
                    className="text-[11px] bg-sand-50 border border-sand-200 text-stone-700 px-2 py-0.5 rounded"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </section>
          </>
        ) : (
          <p className="text-sm text-stone-500 italic">
            Sin descripción registrada para este miembro.
          </p>
        )}

        <div className="mt-auto pt-3 border-t border-sand-200 flex justify-end">
          <Link to={`/chat/${agent.id}`} className="btn-accent text-sm py-1.5 px-3">
            Iniciar chat 1-a-1 →
          </Link>
        </div>
      </div>
    </article>
  );
}

export default function AgentsPage() {
  const agents = useQuery({ queryKey: ["agents"], queryFn: api.listAgents });

  return (
    <div>
      <div className="bg-white border-b border-sand-200">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="text-[10px] uppercase tracking-[0.22em] text-accent-600 font-semibold mb-1">
            Junta de Gobierno
          </div>
          <h1 className="font-serif text-2xl text-banxico-700">
            Miembros del simulador
          </h1>
          <p className="text-sm text-stone-600 mt-2 max-w-3xl leading-relaxed">
            Cada agente del simulador representa una postura diferenciada de política
            monetaria con habilidades técnicas y prioridades de datos distintas. Conoce
            su perfil antes de iniciar una junta o un chat 1-a-1.
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {agents.isLoading && (
          <p className="text-stone-500 text-sm">Cargando perfiles…</p>
        )}
        {agents.isError && (
          <p className="text-red-700 text-sm">
            No se pudo cargar la lista de agentes.
          </p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {agents.data?.map((a) => (
            <AgentDetailCard key={a.id} agent={a} />
          ))}
        </div>
      </div>
    </div>
  );
}

import type { Agent } from "../types";

export type VoteEntry = { agent_id: number; agent: string; decision_bps: number; rationale: string };

const formatBps = (bps: number) => (bps > 0 ? `+${bps}` : `${bps}`);

export default function VoteTally({
  votes,
  agents,
  decision,
}: {
  votes: VoteEntry[];
  agents: Agent[];
  decision: number | null;
}) {
  if (!votes.length && decision === null) return null;
  const byId = Object.fromEntries(agents.map((a) => [a.id, a]));
  return (
    <div className="institutional-card overflow-hidden">
      <div className="px-4 py-2.5 bg-banxico-700 text-white flex items-center gap-2 border-b-2 border-accent-600">
        <span className="text-base">🗳️</span>
        <h3 className="font-serif text-sm">Votación</h3>
      </div>
      <div className="p-4">
        <ul className="text-sm space-y-3">
          {votes.map((v) => {
            const a = byId[v.agent_id];
            const isFallback = v.rationale?.startsWith("Voto no parseable");
            const bpsTone =
              v.decision_bps > 0
                ? "text-red-700 bg-red-50 border-red-200"
                : v.decision_bps < 0
                ? "text-accent-700 bg-accent-50 border-accent-100"
                : "text-stone-700 bg-stone-50 border-stone-200";
            return (
              <li key={v.agent_id} className="border-b border-sand-200 pb-2 last:border-0 last:pb-0">
                <div className="flex items-baseline gap-2">
                  <span className="text-base w-6">{a?.avatar}</span>
                  <span className="flex-1 truncate font-medium text-banxico-700">{v.agent}</span>
                  <span
                    className={`font-mono font-semibold text-xs px-2 py-0.5 rounded border ${
                      isFallback ? "text-amber-700 bg-amber-50 border-amber-200" : bpsTone
                    }`}
                  >
                    {formatBps(v.decision_bps)} bps
                  </span>
                </div>
                {v.rationale && (
                  <p
                    className={`text-xs ml-8 mt-1 leading-snug ${
                      isFallback ? "text-amber-700 italic" : "text-stone-500"
                    }`}
                  >
                    {v.rationale}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
        {decision !== null && (
          <div className="mt-4 pt-4 border-t-2 border-accent-100 bg-accent-50/40 -mx-4 -mb-4 px-4 py-3">
            <div className="text-[10px] uppercase tracking-[0.18em] text-accent-700 font-semibold">
              Decisión final
            </div>
            <div className="font-serif text-3xl font-semibold text-banxico-700 mt-0.5">
              {formatBps(decision)} <span className="text-base text-stone-500">bps</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

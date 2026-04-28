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
    <div className="rounded-lg border border-stone-200 bg-white p-3">
      <h3 className="font-semibold text-sm mb-2">Votación</h3>
      <ul className="text-sm space-y-1">
        {votes.map((v) => {
          const a = byId[v.agent_id];
          return (
            <li key={v.agent_id} className="flex items-baseline gap-2">
              <span className="text-stone-500 w-6">{a?.avatar}</span>
              <span className="flex-1 truncate">{v.agent}</span>
              <span className="font-mono font-semibold">{formatBps(v.decision_bps)} bps</span>
            </li>
          );
        })}
      </ul>
      {decision !== null && (
        <div className="mt-3 pt-3 border-t border-stone-200">
          <div className="text-xs text-stone-500">Decisión final</div>
          <div className="text-2xl font-semibold text-banxico-700">{formatBps(decision)} bps</div>
        </div>
      )}
    </div>
  );
}

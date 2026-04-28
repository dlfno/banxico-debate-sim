import type { Agent } from "../types";

const STANCE_COLOR: Record<string, string> = {
  hawkish: "bg-red-100 text-red-800 border-red-300",
  dovish: "bg-sky-100 text-sky-800 border-sky-300",
  centrista: "bg-amber-100 text-amber-800 border-amber-300",
  "data-dependent": "bg-violet-100 text-violet-800 border-violet-300",
  "externo/FX": "bg-emerald-100 text-emerald-800 border-emerald-300",
};

export default function AgentCard({
  agent,
  selected,
  onClick,
}: {
  agent: Agent;
  selected?: boolean;
  onClick?: () => void;
}) {
  const tone = STANCE_COLOR[agent.stance] || "bg-stone-100 text-stone-800 border-stone-300";
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-lg border p-3 transition ${
        selected ? "border-banxico-600 ring-2 ring-banxico-200 bg-white" : "border-stone-200 bg-white hover:border-stone-400"
      }`}
    >
      <div className="flex items-center gap-3">
        <div className="text-2xl">{agent.avatar || "👤"}</div>
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">{agent.display_name}</div>
          <div className="text-xs text-stone-500">{agent.role}</div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full border ${tone}`}>{agent.stance}</span>
      </div>
    </button>
  );
}

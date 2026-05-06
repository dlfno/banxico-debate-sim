import type { Agent } from "../types";

const STANCE_COLOR: Record<string, string> = {
  hawkish: "bg-red-50 text-red-700 border-red-200",
  dovish: "bg-sky-50 text-sky-700 border-sky-200",
  centrista: "bg-amber-50 text-amber-700 border-amber-200",
  "data-dependent": "bg-violet-50 text-violet-700 border-violet-200",
  "externo/FX": "bg-accent-50 text-accent-700 border-accent-100",
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
  const tone = STANCE_COLOR[agent.stance] || "bg-stone-50 text-stone-700 border-stone-200";
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-md border p-3 transition ${
        selected
          ? "border-accent-500 ring-2 ring-accent-100 bg-white shadow-sm"
          : "border-sand-200 bg-white hover:border-accent-500/60 hover:shadow-sm"
      }`}
    >
      <div className="flex items-center gap-3">
        <div className="text-2xl">{agent.avatar || "👤"}</div>
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate text-banxico-700">{agent.display_name}</div>
          <div className="text-xs text-stone-500">{agent.role}</div>
        </div>
        <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full border font-semibold ${tone}`}>
          {agent.stance}
        </span>
      </div>
    </button>
  );
}

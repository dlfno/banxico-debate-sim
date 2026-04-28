import ReactMarkdown from "react-markdown";
import ToolCallTrace, { type ToolTrace } from "./ToolCallTrace";

export default function MessageBubble({
  who,
  avatar,
  role,
  content,
  phaseLabel,
  trace,
  pending,
}: {
  who: string;
  avatar?: string;
  role: "user" | "assistant" | "moderator" | "secretario";
  content: string;
  phaseLabel?: string;
  trace?: ToolTrace[];
  pending?: boolean;
}) {
  const isUser = role === "user";
  const isMod = role === "moderator" || role === "secretario";
  const align = isUser ? "items-end" : "items-start";
  const bubble = isUser
    ? "bg-banxico-600 text-white"
    : isMod
    ? "bg-amber-50 border border-amber-200 text-stone-800"
    : "bg-white border border-stone-200 text-stone-800";

  return (
    <div className={`flex flex-col ${align} my-2`}>
      <div className="flex items-center gap-2 text-xs text-stone-500 mb-1">
        {avatar && <span>{avatar}</span>}
        <span className="font-medium">{who}</span>
        {phaseLabel && (
          <span className="px-1.5 py-0.5 rounded bg-stone-200 text-stone-700 text-[10px] uppercase tracking-wide">
            {phaseLabel}
          </span>
        )}
      </div>
      <div className={`max-w-[85%] rounded-2xl px-4 py-2 shadow-sm ${bubble}`}>
        <div className="markdown text-sm">
          <ReactMarkdown>{content || (pending ? "…" : "")}</ReactMarkdown>
        </div>
        {trace && <ToolCallTrace trace={trace} />}
      </div>
    </div>
  );
}

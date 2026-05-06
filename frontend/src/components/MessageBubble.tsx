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
  const isMod = role === "moderator";
  const isSec = role === "secretario";

  const align = isUser ? "items-end" : "items-start";

  let bubble: string;
  if (isUser) {
    bubble = "bg-banxico-700 text-white border border-banxico-800";
  } else if (isMod) {
    bubble = "bg-sand-50 border border-sand-200 text-stone-800";
  } else if (isSec) {
    bubble = "bg-accent-50 border border-accent-100 text-stone-800";
  } else {
    bubble = "bg-white border border-sand-200 text-stone-800 shadow-sm";
  }

  return (
    <div className={`flex flex-col ${align} my-3`}>
      <div className="flex items-center gap-2 text-xs text-stone-500 mb-1">
        {avatar && <span className="text-base">{avatar}</span>}
        <span className="font-semibold text-banxico-700">{who}</span>
        {phaseLabel && (
          <span className="px-1.5 py-0.5 rounded-sm bg-accent-50 border border-accent-100 text-accent-700 text-[10px] uppercase tracking-wider font-semibold">
            {phaseLabel}
          </span>
        )}
      </div>
      <div className={`max-w-[85%] rounded-md px-4 py-2.5 ${bubble}`}>
        <div className={`markdown text-sm ${isUser ? "text-white" : ""}`}>
          <ReactMarkdown>{content || (pending ? "…" : "")}</ReactMarkdown>
        </div>
        {trace && <ToolCallTrace trace={trace} />}
      </div>
    </div>
  );
}

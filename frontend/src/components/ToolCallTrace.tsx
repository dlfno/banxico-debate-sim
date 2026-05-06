import { useState } from "react";

export type ToolTrace = {
  id: string;
  name: string;
  args: any;
  output?: string;
};

export default function ToolCallTrace({ trace }: { trace: ToolTrace[] }) {
  const [open, setOpen] = useState(false);
  if (!trace.length) return null;
  return (
    <div className="mt-2 text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-accent-700 hover:text-accent-600 font-medium underline-offset-2 hover:underline"
      >
        {open ? "▾" : "▸"} {trace.length} llamada{trace.length > 1 ? "s" : ""} a herramientas
      </button>
      {open && (
        <ul className="mt-1.5 space-y-1">
          {trace.map((t) => (
            <li key={t.id} className="rounded border border-sand-200 bg-sand-50 p-2">
              <div className="font-mono text-[11px]">
                <span className="text-accent-700 font-semibold">{t.name}</span>(
                <span className="text-stone-600">{JSON.stringify(t.args)}</span>)
              </div>
              {t.output && (
                <pre className="mt-1 whitespace-pre-wrap text-[11px] text-stone-700 bg-white border border-sand-200 rounded p-1.5">
                  {t.output.slice(0, 800)}
                </pre>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

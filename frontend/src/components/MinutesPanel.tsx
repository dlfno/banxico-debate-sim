import ReactMarkdown from "react-markdown";

export default function MinutesPanel({ markdown }: { markdown: string | null }) {
  if (!markdown) return null;
  return (
    <div className="rounded-lg border border-stone-200 bg-white p-4">
      <h3 className="font-semibold mb-2">Minuta</h3>
      <div className="markdown text-sm">
        <ReactMarkdown>{markdown}</ReactMarkdown>
      </div>
    </div>
  );
}

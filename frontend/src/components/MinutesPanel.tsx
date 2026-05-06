import ReactMarkdown from "react-markdown";

export default function MinutesPanel({ markdown }: { markdown: string | null }) {
  if (!markdown) return null;
  return (
    <div className="institutional-card overflow-hidden">
      <div className="px-4 py-2.5 bg-banxico-700 text-white flex items-center gap-2 border-b-2 border-accent-600">
        <span className="text-base">📝</span>
        <h3 className="font-serif text-sm">Minuta</h3>
      </div>
      <div className="p-4 markdown text-sm bg-white">
        <ReactMarkdown>{markdown}</ReactMarkdown>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api, openChatSocket } from "../api";
import type { Agent, MemoryItem, Message, WsEvent } from "../types";
import AgentCard from "../components/AgentCard";
import MessageBubble from "../components/MessageBubble";
import type { ToolTrace } from "../components/ToolCallTrace";

type Bubble = {
  id: string;
  role: "user" | "assistant";
  content: string;
  trace: ToolTrace[];
  pending?: boolean;
  agentId?: number;
};

export default function ChatPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const agents = useQuery({ queryKey: ["agents"], queryFn: api.listAgents });

  const selectedAgent = useMemo<Agent | undefined>(() => {
    if (!agents.data) return undefined;
    if (agentId) return agents.data.find((a) => String(a.id) === agentId);
    return agents.data[0];
  }, [agents.data, agentId]);

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  const memory = useQuery<MemoryItem[]>({
    queryKey: ["memory", selectedAgent?.id],
    queryFn: () => api.getAgentMemory(selectedAgent!.id),
    enabled: !!selectedAgent,
  });

  // (Re)create session when agent changes
  useEffect(() => {
    if (!selectedAgent) return;
    let cancelled = false;
    (async () => {
      const session = await api.createChatSession(selectedAgent.id);
      if (cancelled) return;
      setSessionId(session.id);
      setBubbles([]);
      try {
        const prior: Message[] = await api.listChatMessages(session.id);
        setBubbles(
          prior.map((m) => ({
            id: `db-${m.id}`,
            role: m.role === "user" ? "user" : "assistant",
            content: m.content,
            trace: [],
            agentId: m.agent_id ?? undefined,
          })),
        );
      } catch {
        /* empty session */
      }
    })();
    return () => {
      cancelled = true;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [selectedAgent?.id]);

  useEffect(() => {
    if (!sessionId) return;
    const ws = openChatSocket(sessionId, handleEvent);
    wsRef.current = ws;
    return () => ws.close();
  }, [sessionId]);

  useEffect(() => {
    scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: "smooth" });
  }, [bubbles]);

  function handleEvent(ev: WsEvent) {
    setBubbles((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (ev.type === "turn_start") {
        next.push({
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: "",
          trace: [],
          pending: true,
          agentId: ev.agent_id,
        });
      } else if (ev.type === "token") {
        if (last && last.role === "assistant" && last.pending) {
          last.content += ev.delta;
        }
      } else if (ev.type === "tool_start") {
        if (last && last.role === "assistant" && last.pending) {
          last.trace.push({ id: ev.id, name: ev.name, args: ev.args });
        }
      } else if (ev.type === "tool_end") {
        if (last && last.role === "assistant" && last.pending) {
          const t = last.trace.find((x) => x.id === ev.id);
          if (t) t.output = ev.output;
        }
      } else if (ev.type === "final") {
        if (last && last.role === "assistant" && last.pending) {
          last.pending = false;
          if (!last.content && ev.text) last.content = ev.text;
        }
        setSending(false);
      } else if (ev.type === "error") {
        next.push({
          id: `error-${Date.now()}`,
          role: "assistant",
          content: `⚠️ ${ev.message}`,
          trace: [],
        });
        setSending(false);
      }
      return next;
    });
  }

  function send() {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    const user: Bubble = { id: `user-${Date.now()}`, role: "user", content: input, trace: [] };
    setBubbles((b) => [...b, user]);
    wsRef.current.send(JSON.stringify({ type: "user", content: input }));
    setInput("");
    setSending(true);
  }

  return (
    <div className="max-w-6xl mx-auto p-4 grid grid-cols-12 gap-4 h-[calc(100vh-60px)]">
      <aside className="col-span-3 space-y-2 overflow-auto">
        <h2 className="font-semibold text-sm text-stone-700 mb-1">Miembros de la Junta</h2>
        {agents.data?.map((a) => (
          <AgentCard
            key={a.id}
            agent={a}
            selected={selectedAgent?.id === a.id}
            onClick={() => navigate(`/chat/${a.id}`)}
          />
        ))}
        {memory.data && memory.data.length > 0 && (
          <div className="mt-4 p-3 rounded border border-stone-200 bg-white text-xs text-stone-700">
            <div className="font-semibold mb-1">Memoria persistente</div>
            <ul className="space-y-1 list-disc pl-4">
              {memory.data.slice(0, 6).map((m) => (
                <li key={m.id}>
                  <span className="text-stone-400 mr-1">[{m.kind}]</span>
                  {m.content.length > 140 ? m.content.slice(0, 140) + "…" : m.content}
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>

      <section className="col-span-9 flex flex-col rounded-xl border border-stone-200 bg-stone-50">
        <div className="px-4 py-3 border-b border-stone-200 bg-white flex items-center gap-3">
          <span className="text-xl">{selectedAgent?.avatar}</span>
          <div>
            <div className="font-medium">{selectedAgent?.display_name}</div>
            <div className="text-xs text-stone-500">{selectedAgent?.role} — {selectedAgent?.stance}</div>
          </div>
        </div>
        <div ref={scrollerRef} className="flex-1 overflow-auto px-4 py-3">
          {bubbles.length === 0 && (
            <p className="text-sm text-stone-500">
              Inicia la conversación. El agente puede usar herramientas (web_search, datos macro, calculadora).
            </p>
          )}
          {bubbles.map((b) => (
            <MessageBubble
              key={b.id}
              who={b.role === "user" ? "Tú" : selectedAgent?.display_name || "Agente"}
              avatar={b.role === "user" ? "🧑" : selectedAgent?.avatar}
              role={b.role}
              content={b.content}
              trace={b.trace}
              pending={b.pending}
            />
          ))}
        </div>
        <div className="border-t border-stone-200 p-3 bg-white flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Escribe tu mensaje…"
            className="flex-1 border border-stone-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-banxico-500"
          />
          <button
            onClick={send}
            disabled={sending || !input.trim()}
            className="bg-banxico-600 hover:bg-banxico-700 disabled:opacity-50 text-white rounded-lg px-4"
          >
            Enviar
          </button>
        </div>
      </section>
    </div>
  );
}

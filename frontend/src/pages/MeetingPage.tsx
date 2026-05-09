import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api, openMeetingSocket } from "../api";
import type { Agent, Message, WsEvent } from "../types";
import MessageBubble from "../components/MessageBubble";
import VoteTally, { type VoteEntry } from "../components/VoteTally";
import MinutesPanel from "../components/MinutesPanel";
import type { ToolTrace } from "../components/ToolCallTrace";
import { durationMs, formatDuration } from "../format";

type Bubble = {
  id: string;
  agentId?: number;
  role: "assistant" | "moderator" | "secretario";
  content: string;
  phase?: string;
  trace: ToolTrace[];
  pending?: boolean;
};

const PHASE_LABEL: Record<string, string> = {
  setup: "Agenda",
  opening: "Apertura",
  debate: "Debate",
  vote: "Voto",
  minutes: "Minuta",
};

export default function MeetingPage() {
  const { meetingId } = useParams();
  const navigate = useNavigate();
  const agents = useQuery({ queryKey: ["agents"], queryFn: api.listAgents });

  const [topic, setTopic] = useState("Decisión de tasa de referencia, próxima reunión");
  const [rounds, setRounds] = useState(2);
  const [selected, setSelected] = useState<number[]>([]);

  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [votes, setVotes] = useState<VoteEntry[]>([]);
  const [decision, setDecision] = useState<number | null>(null);
  const [minutes, setMinutes] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [endedAt, setEndedAt] = useState<string | null>(null);
  const [tick, setTick] = useState(0);  // fuerza re-render cada segundo mientras running
  const wsRef = useRef<WebSocket | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  // Ticker en vivo: actualiza el cronómetro cada segundo mientras la junta corre.
  useEffect(() => {
    if (!running || !startedAt) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, [running, startedAt]);

  // Cronómetro: si está corriendo, mide hasta ahora; si terminó, mide hasta endedAt.
  // tick se referencia para invalidar memoization cada segundo.
  void tick;
  const elapsedMs = startedAt
    ? (endedAt ? durationMs(startedAt, endedAt) : Date.now() - new Date(startedAt).getTime())
    : null;

  const agentById = useMemo(() => Object.fromEntries((agents.data || []).map((a) => [a.id, a])), [agents.data]);

  // Load existing meeting if route includes id
  useEffect(() => {
    if (!meetingId) return;
    let cancelled = false;
    (async () => {
      const m = await api.getMeeting(Number(meetingId));
      if (cancelled) return;
      setBubbles(
        m.messages.map((msg: Message) => ({
          id: `db-${msg.id}`,
          agentId: msg.agent_id ?? undefined,
          role: msg.role === "moderator" || msg.role === "secretario" ? (msg.role as any) : "assistant",
          content: msg.content,
          phase: msg.phase ?? undefined,
          trace: [],
        })),
      );
      setVotes(
        m.votes.map((v) => ({
          agent_id: v.agent_id,
          agent: agentById[v.agent_id]?.display_name || `agent ${v.agent_id}`,
          decision_bps: v.decision_bps,
          rationale: v.rationale,
        })),
      );
      setDecision(m.decision_bps);
      setMinutes(m.minutes_md);
      setStartedAt(m.started_at);
      setEndedAt(m.ended_at);
    })();
    return () => {
      cancelled = true;
    };
  }, [meetingId, agentById]);

  useEffect(() => {
    scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: "smooth" });
  }, [bubbles, minutes]);

  function toggleAgent(id: number) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  async function startMeeting() {
    if (!topic.trim()) return;
    const ids = selected.length > 0 ? selected : agents.data?.map((a) => a.id);
    setRunning(true);
    setBubbles([]);
    setVotes([]);
    setDecision(null);
    setMinutes(null);
    setEndedAt(null);
    const meeting = await api.createMeeting(topic, rounds, ids);
    setStartedAt(meeting.started_at);
    navigate(`/meeting/${meeting.id}`, { replace: true });
    const ws = openMeetingSocket(meeting.id, handleEvent);
    wsRef.current = ws;
  }

  function handleEvent(ev: WsEvent) {
    if (ev.type === "vote") {
      setVotes((vs) => {
        const filtered = vs.filter((v) => v.agent_id !== ev.agent_id);
        return [...filtered, { agent_id: ev.agent_id, agent: ev.agent, decision_bps: ev.decision_bps, rationale: ev.rationale }];
      });
      return;
    }
    if (ev.type === "decision") {
      setDecision(ev.decision_bps);
      return;
    }
    if (ev.type === "done") {
      setRunning(false);
      setEndedAt(new Date().toISOString());
      return;
    }
    if (ev.type === "minutes") {
      setMinutes(ev.content);
    }
    setBubbles((prev) => {
      const lastIdx = prev.length - 1;
      const last = prev[lastIdx];
      const replaceLast = (patch: Partial<Bubble>) => {
        const updated = [...prev];
        updated[lastIdx] = { ...last, ...patch };
        return updated;
      };
      if (ev.type === "phase") {
        return [
          ...prev,
          {
            id: `mod-${Date.now()}`,
            role: "moderator",
            content: ev.content,
            phase: ev.phase,
            trace: [],
          },
        ];
      }
      if (ev.type === "turn_start") {
        return [
          ...prev,
          {
            id: `a-${Date.now()}`,
            agentId: ev.agent_id,
            role: "assistant",
            content: "",
            phase: ev.phase,
            trace: [],
            pending: true,
          },
        ];
      }
      if (ev.type === "token") {
        if (last && last.pending) {
          return replaceLast({ content: last.content + ev.delta });
        }
        return prev;
      }
      if (ev.type === "tool_start") {
        if (last && last.pending) {
          return replaceLast({
            trace: [...last.trace, { id: ev.id, name: ev.name, args: ev.args }],
          });
        }
        return prev;
      }
      if (ev.type === "tool_end") {
        if (last && last.pending) {
          return replaceLast({
            trace: last.trace.map((t) => (t.id === ev.id ? { ...t, output: ev.output } : t)),
          });
        }
        return prev;
      }
      if (ev.type === "final") {
        if (last && last.pending) {
          return replaceLast({
            pending: false,
            content: last.content || ev.text || "",
          });
        }
        return prev;
      }
      if (ev.type === "minutes") {
        return [
          ...prev,
          {
            id: `sec-${Date.now()}`,
            role: "secretario",
            content: ev.content,
            phase: "minutes",
            trace: [],
          },
        ];
      }
      if (ev.type === "error") {
        setRunning(false);
        return [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: "moderator",
            content: `⚠️ ${ev.message}`,
            trace: [],
          },
        ];
      }
      return prev;
    });
  }

  if (!meetingId && !running) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="institutional-card overflow-hidden">
          {/* Encabezado de la sección */}
          <div className="bg-banxico-700 text-white px-6 py-4 border-b-4 border-accent-600">
            <div className="text-[10px] uppercase tracking-[0.22em] text-white/70 font-medium">
              Política Monetaria · Simulación
            </div>
            <h2 className="font-serif text-2xl">Configurar nueva junta</h2>
          </div>

          <div className="p-6 space-y-6 bg-white">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-banxico-700 mb-1.5">
                Tema de la deliberación
              </label>
              <input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="input-institutional"
                placeholder="Ej. Decisión de tasa de referencia, próxima reunión"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-banxico-700 mb-1.5">
                Rondas de debate
              </label>
              <input
                type="number"
                min={1}
                max={4}
                value={rounds}
                onChange={(e) => setRounds(Number(e.target.value))}
                className="input-institutional w-28"
              />
              <p className="text-xs text-stone-500 mt-1">
                Cada ronda permite a los miembros responder y refinar su postura.
              </p>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-banxico-700">
                  Participantes
                </h3>
                <span className="text-xs text-stone-500">
                  Vacío = todos los miembros
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {agents.data?.map((a: Agent) => {
                  const isSel = selected.includes(a.id);
                  return (
                    <label
                      key={a.id}
                      className={`flex items-center gap-3 border rounded-md p-2.5 cursor-pointer transition ${
                        isSel
                          ? "border-accent-500 bg-accent-50/40 ring-1 ring-accent-100"
                          : "border-sand-200 bg-white hover:border-accent-500/60"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSel}
                        onChange={() => toggleAgent(a.id)}
                        className="accent-accent-600"
                      />
                      <span className="text-xl">{a.avatar}</span>
                      <span className="flex-1 text-sm font-medium text-stone-800">
                        {a.display_name}
                      </span>
                      <span className="text-[10px] uppercase tracking-wide text-stone-500 bg-sand-50 border border-sand-200 px-1.5 py-0.5 rounded">
                        {a.stance}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-sand-200">
              <button onClick={() => navigate("/")} className="btn-secondary">
                Cancelar
              </button>
              <button onClick={startMeeting} className="btn-primary">
                Iniciar junta
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-6 py-5 grid grid-cols-12 gap-4">
      <section className="col-span-12 lg:col-span-8 flex flex-col institutional-card overflow-hidden h-[calc(100vh-220px)] min-h-[500px]">
        <div className="px-5 py-3 border-b border-sand-200 bg-banxico-700 text-white flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-white/10 flex items-center justify-center text-sm">
            🏛️
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] uppercase tracking-[0.18em] text-white/60 font-medium">
              Tema de la deliberación
            </div>
            <div className="font-serif text-base truncate">{topic}</div>
          </div>
          {elapsedMs !== null && (
            <span
              className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded font-mono ${
                running
                  ? "bg-accent-600 text-white"
                  : "bg-white/10 text-white/80 border border-white/20"
              }`}
              title={
                running
                  ? "Tiempo transcurrido (junta en curso)"
                  : "Duración total de la junta"
              }
            >
              {running ? (
                <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
              ) : (
                <span>⏱</span>
              )}
              {formatDuration(elapsedMs)}
            </span>
          )}
        </div>
        <div ref={scrollerRef} className="flex-1 overflow-auto px-4 py-3 bg-sand-50/50">
          {bubbles.map((b) => {
            const ag = b.agentId ? agentById[b.agentId] : undefined;
            const who =
              b.role === "moderator"
                ? "Moderador"
                : b.role === "secretario"
                ? "Secretario"
                : ag?.display_name || "Agente";
            const avatar = b.role === "moderator" ? "🪧" : b.role === "secretario" ? "📝" : ag?.avatar;
            return (
              <MessageBubble
                key={b.id}
                who={who}
                avatar={avatar}
                role={b.role as any}
                content={b.content}
                phaseLabel={b.phase ? PHASE_LABEL[b.phase] : undefined}
                trace={b.trace}
                pending={b.pending}
              />
            );
          })}
          {running && (
            <p className="text-xs text-accent-600 mt-2 italic flex items-center gap-2">
              <span className="w-2 h-2 bg-accent-500 rounded-full animate-pulse" />
              Junta en curso…
            </p>
          )}
        </div>
      </section>
      <aside className="col-span-12 lg:col-span-4 space-y-4">
        <VoteTally votes={votes} agents={agents.data || []} decision={decision} />
        <MinutesPanel markdown={minutes} />
      </aside>
    </div>
  );
}

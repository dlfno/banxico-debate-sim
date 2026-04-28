import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api, openMeetingSocket } from "../api";
import type { Agent, Message, WsEvent } from "../types";
import MessageBubble from "../components/MessageBubble";
import VoteTally, { type VoteEntry } from "../components/VoteTally";
import MinutesPanel from "../components/MinutesPanel";
import type { ToolTrace } from "../components/ToolCallTrace";

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
  const wsRef = useRef<WebSocket | null>(null);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

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
    const meeting = await api.createMeeting(topic, rounds, ids);
    navigate(`/meeting/${meeting.id}`, { replace: true });
    const ws = openMeetingSocket(meeting.id, handleEvent);
    wsRef.current = ws;
  }

  function handleEvent(ev: WsEvent) {
    setBubbles((prev) => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (ev.type === "phase") {
        next.push({
          id: `mod-${Date.now()}`,
          role: "moderator",
          content: ev.content,
          phase: ev.phase,
          trace: [],
        });
      } else if (ev.type === "turn_start") {
        next.push({
          id: `a-${Date.now()}`,
          agentId: ev.agent_id,
          role: "assistant",
          content: "",
          phase: ev.phase,
          trace: [],
          pending: true,
        });
      } else if (ev.type === "token") {
        if (last && last.pending) last.content += ev.delta;
      } else if (ev.type === "tool_start") {
        if (last && last.pending) last.trace.push({ id: ev.id, name: ev.name, args: ev.args });
      } else if (ev.type === "tool_end") {
        if (last && last.pending) {
          const t = last.trace.find((x) => x.id === ev.id);
          if (t) t.output = ev.output;
        }
      } else if (ev.type === "final") {
        if (last && last.pending) {
          last.pending = false;
          if (!last.content && ev.text) last.content = ev.text;
        }
      } else if (ev.type === "vote") {
        setVotes((vs) => {
          const filtered = vs.filter((v) => v.agent_id !== ev.agent_id);
          return [...filtered, { agent_id: ev.agent_id, agent: ev.agent, decision_bps: ev.decision_bps, rationale: ev.rationale }];
        });
      } else if (ev.type === "decision") {
        setDecision(ev.decision_bps);
      } else if (ev.type === "minutes") {
        setMinutes(ev.content);
        next.push({
          id: `sec-${Date.now()}`,
          role: "secretario",
          content: ev.content,
          phase: "minutes",
          trace: [],
        });
      } else if (ev.type === "done") {
        setRunning(false);
      } else if (ev.type === "error") {
        next.push({
          id: `err-${Date.now()}`,
          role: "moderator",
          content: `⚠️ ${ev.message}`,
          trace: [],
        });
        setRunning(false);
      }
      return next;
    });
  }

  if (!meetingId && !running) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <h2 className="text-xl font-semibold mb-3">Configura una junta</h2>
        <label className="block text-sm font-medium mb-1">Tema</label>
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          className="w-full border border-stone-300 rounded-lg px-3 py-2 mb-3"
        />
        <label className="block text-sm font-medium mb-1">Rondas de debate</label>
        <input
          type="number"
          min={1}
          max={4}
          value={rounds}
          onChange={(e) => setRounds(Number(e.target.value))}
          className="w-24 border border-stone-300 rounded-lg px-3 py-2 mb-4"
        />
        <h3 className="font-semibold text-sm mb-2">Participantes (vacío = todos)</h3>
        <div className="grid grid-cols-2 gap-2 mb-4">
          {agents.data?.map((a: Agent) => (
            <label
              key={a.id}
              className="flex items-center gap-2 border border-stone-200 rounded-lg p-2 bg-white cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selected.includes(a.id)}
                onChange={() => toggleAgent(a.id)}
              />
              <span>{a.avatar}</span>
              <span className="flex-1">{a.display_name}</span>
              <span className="text-xs text-stone-500">{a.stance}</span>
            </label>
          ))}
        </div>
        <button
          onClick={startMeeting}
          className="bg-banxico-600 hover:bg-banxico-700 text-white rounded-lg px-4 py-2"
        >
          Iniciar junta
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-4 grid grid-cols-12 gap-4">
      <section className="col-span-8 flex flex-col rounded-xl border border-stone-200 bg-stone-50 h-[calc(100vh-100px)]">
        <div className="px-4 py-3 border-b border-stone-200 bg-white">
          <div className="text-xs text-stone-500 uppercase tracking-wide">Tema</div>
          <div className="font-medium">{topic}</div>
        </div>
        <div ref={scrollerRef} className="flex-1 overflow-auto px-4 py-3">
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
          {running && <p className="text-xs text-stone-500 mt-2">Junta en curso…</p>}
        </div>
      </section>
      <aside className="col-span-4 space-y-4">
        <VoteTally votes={votes} agents={agents.data || []} decision={decision} />
        <MinutesPanel markdown={minutes} />
      </aside>
    </div>
  );
}

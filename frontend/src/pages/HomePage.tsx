import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString();
}

export default function HomePage() {
  const meetings = useQuery({ queryKey: ["meetings"], queryFn: api.listMeetings });
  const chats = useQuery({ queryKey: ["chat-sessions"], queryFn: api.listChatSessions });
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [confirmChatId, setConfirmChatId] = useState<number | null>(null);
  const deleteMutation = useMutation({
    mutationFn: api.deleteMeeting,
    onSuccess: () => {
      meetings.refetch();
      setConfirmId(null);
    },
  });
  const deleteChatMutation = useMutation({
    mutationFn: api.deleteChatSession,
    onSuccess: () => {
      chats.refetch();
      setConfirmChatId(null);
    },
  });

  return (
    <div>
      {/* Banner institucional con la frase rectora */}
      <div className="bg-white border-b border-sand-200">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="rounded-md border border-accent-100 bg-accent-50/40 px-6 py-5">
            <p className="text-center text-banxico-700 font-serif text-lg md:text-xl leading-snug">
              El objetivo prioritario del Banco de México es{" "}
              <span className="font-semibold">mantener una inflación baja y estable</span>.
              Este simulador permite explorar la deliberación de la Junta de Gobierno
              mediante agentes con posturas diferenciadas.
            </p>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Tarjetas de modo */}
        <h2 className="section-title mb-3">Modos de simulación</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-10">
          <Link
            to="/chat"
            className="institutional-card p-6 hover:border-accent-500 hover:shadow-md transition group"
          >
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-md bg-accent-50 text-accent-600 flex items-center justify-center text-2xl border border-accent-100 group-hover:bg-accent-100 transition">
                💬
              </div>
              <div className="flex-1">
                <h3 className="font-serif text-xl font-semibold text-banxico-700 mb-1">
                  Chat 1-a-1
                </h3>
                <p className="text-sm text-stone-600 leading-relaxed">
                  Conversa con un miembro específico. Cada agente conserva memoria
                  persistente entre sesiones y entre modos.
                </p>
              </div>
            </div>
          </Link>
          <Link
            to="/meeting"
            className="institutional-card p-6 hover:border-accent-500 hover:shadow-md transition group"
          >
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-md bg-accent-50 text-accent-600 flex items-center justify-center text-2xl border border-accent-100 group-hover:bg-accent-100 transition">
                🏛️
              </div>
              <div className="flex-1">
                <h3 className="font-serif text-xl font-semibold text-banxico-700 mb-1">
                  Simulación de Junta
                </h3>
                <p className="text-sm text-stone-600 leading-relaxed">
                  Define un tema y ejecuta una junta completa: aperturas, debate,
                  votación y minuta automática.
                </p>
              </div>
            </div>
          </Link>
        </div>

        {/* Historial */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="section-title">Juntas previas</h2>
              <span className="text-xs text-stone-400">
                {meetings.data?.length ?? 0} registros
              </span>
            </div>
            {meetings.isLoading && <p className="text-stone-500 text-sm">Cargando…</p>}
            {meetings.data?.length === 0 && (
              <div className="institutional-card p-4 text-stone-500 text-sm text-center">
                Aún no hay juntas. Inicia una desde la tarjeta de arriba.
              </div>
            )}
            <ul className="space-y-2">
              {meetings.data?.map((m) => (
                <li key={m.id} className="relative">
                  <Link
                    to={`/meeting/${m.id}`}
                    className="block institutional-card p-3 hover:border-accent-500 hover:shadow-md transition"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium truncate text-banxico-700">
                        {m.topic}
                      </span>
                      <span
                        className={`font-mono text-sm px-2 py-0.5 rounded ${
                          m.decision_bps === null
                            ? "bg-amber-50 text-amber-700 border border-amber-200"
                            : "bg-accent-50 text-accent-700 border border-accent-100"
                        }`}
                      >
                        {m.decision_bps !== null
                          ? (m.decision_bps > 0 ? `+${m.decision_bps}` : `${m.decision_bps}`) + " bps"
                          : "en curso"}
                      </span>
                    </div>
                    <div className="text-xs text-stone-500 flex items-center gap-2 mt-1">
                      <span>{fmtDate(m.started_at)}</span>
                      <span className="text-stone-300">·</span>
                      <span>
                        creado por{" "}
                        <span className="font-medium text-stone-700">
                          {m.created_by.display_name}
                        </span>
                      </span>
                    </div>
                  </Link>
                  {m.decision_bps === null && (
                    confirmId === m.id ? (
                      <div className="absolute inset-0 rounded-lg border border-red-300 bg-red-50 flex items-center justify-center gap-3 text-sm">
                        <span className="text-red-700 font-medium">¿Eliminar esta junta?</span>
                        <button
                          onClick={() => deleteMutation.mutate(m.id)}
                          disabled={deleteMutation.isPending}
                          className="px-3 py-1 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                        >
                          {deleteMutation.isPending ? "…" : "Sí, eliminar"}
                        </button>
                        <button
                          onClick={() => setConfirmId(null)}
                          className="px-3 py-1 rounded border border-stone-300 bg-white hover:bg-stone-50"
                        >
                          Cancelar
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          setConfirmId(m.id);
                        }}
                        title="Descartar junta en curso"
                        className="absolute top-2 right-2 w-6 h-6 flex items-center justify-center rounded-full text-stone-400 hover:bg-red-100 hover:text-red-600 transition text-xs leading-none"
                      >
                        ✕
                      </button>
                    )
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="section-title">Chats previos</h2>
              <span className="text-xs text-stone-400">
                {chats.data?.length ?? 0} sesiones
              </span>
            </div>
            {chats.isLoading && <p className="text-stone-500 text-sm">Cargando…</p>}
            {chats.data?.length === 0 && (
              <div className="institutional-card p-4 text-stone-500 text-sm text-center">
                Aún no hay chats. Inicia uno desde la tarjeta de arriba.
              </div>
            )}
            <ul className="space-y-2">
              {chats.data?.map((c) => (
                <li key={c.id} className="relative">
                  <Link
                    to={`/chat/session/${c.id}`}
                    className="block institutional-card p-3 hover:border-accent-500 hover:shadow-md transition"
                  >
                    <div className="flex items-center justify-between gap-2 pr-7">
                      <span className="font-medium truncate text-banxico-700">
                        <span className="mr-1">{c.agent_avatar}</span>
                        {c.agent_name}
                      </span>
                      <span className="text-xs text-stone-500 bg-sand-50 border border-sand-200 px-2 py-0.5 rounded">
                        {c.message_count} mensajes
                      </span>
                    </div>
                    <div className="text-xs text-stone-500 flex items-center gap-2 mt-1">
                      <span>
                        {c.last_message_at
                          ? `último: ${fmtDate(c.last_message_at)}`
                          : `iniciado: ${fmtDate(c.started_at)}`}
                      </span>
                      <span className="text-stone-300">·</span>
                      <span>
                        chateó{" "}
                        <span className="font-medium text-stone-700">
                          {c.created_by.display_name}
                        </span>
                      </span>
                    </div>
                  </Link>
                  {confirmChatId === c.id ? (
                    <div className="absolute inset-0 rounded-lg border border-red-300 bg-red-50 flex items-center justify-center gap-3 text-sm">
                      <span className="text-red-700 font-medium">¿Eliminar este chat?</span>
                      <button
                        onClick={() => deleteChatMutation.mutate(c.id)}
                        disabled={deleteChatMutation.isPending}
                        className="px-3 py-1 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                      >
                        {deleteChatMutation.isPending ? "…" : "Sí, eliminar"}
                      </button>
                      <button
                        onClick={() => setConfirmChatId(null)}
                        className="px-3 py-1 rounded border border-stone-300 bg-white hover:bg-stone-50"
                      >
                        Cancelar
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        setConfirmChatId(c.id);
                      }}
                      title="Eliminar chat"
                      className="absolute top-2 right-2 w-6 h-6 flex items-center justify-center rounded-full text-stone-400 hover:bg-red-100 hover:text-red-600 transition text-xs leading-none"
                    >
                      ✕
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}

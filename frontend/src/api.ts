import { getStoredToken } from "./auth";
import type {
  Agent,
  ChatSession,
  ChatSessionSummary,
  MemoryItem,
  Meeting,
  MeetingSummary,
  Message,
  VersionInfo,
  WsEvent,
} from "./types";

const API_BASE = "/api";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    window.dispatchEvent(new Event("auth:unauthorized"));
    throw new Error("No autorizado");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  listAgents: () => jsonFetch<Agent[]>("/agents"),
  getAgentMemory: (id: number) => jsonFetch<MemoryItem[]>(`/agents/${id}/memory`),

  createChatSession: (agent_id: number) =>
    jsonFetch<ChatSession>("/chat/sessions", { method: "POST", body: JSON.stringify({ agent_id }) }),
  listChatSessions: () => jsonFetch<ChatSessionSummary[]>("/chat/sessions"),
  listChatMessages: (sid: number) => jsonFetch<Message[]>(`/chat/sessions/${sid}/messages`),
  deleteChatSession: (sid: number) =>
    jsonFetch<{ deleted: boolean }>(`/chat/sessions/${sid}`, { method: "DELETE" }),

  createMeeting: (topic: string, rounds: number, agent_ids?: number[]) =>
    jsonFetch<Meeting>("/meetings", {
      method: "POST",
      body: JSON.stringify({ topic, rounds, agent_ids }),
    }),
  listMeetings: () => jsonFetch<MeetingSummary[]>("/meetings"),
  getMeeting: (id: number) => jsonFetch<Meeting>(`/meetings/${id}`),
  deleteMeeting: (id: number) =>
    jsonFetch<{ deleted: boolean }>(`/meetings/${id}`, { method: "DELETE" }),

  getVersion: () => jsonFetch<VersionInfo>("/version"),
};

function wsUrl(path: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const token = getStoredToken();
  const sep = path.includes("?") ? "&" : "?";
  const auth = token ? `${sep}token=${encodeURIComponent(token)}` : "";
  return `${proto}://${location.host}/api${path}${auth}`;
}

export function openChatSocket(sessionId: number, onEvent: (e: WsEvent) => void): WebSocket {
  const ws = new WebSocket(wsUrl(`/chat/ws/${sessionId}`));
  ws.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as WsEvent);
    } catch {
      // ignore
    }
  };
  return ws;
}

export function openMeetingSocket(meetingId: number, onEvent: (e: WsEvent) => void): WebSocket {
  const ws = new WebSocket(wsUrl(`/meetings/ws/${meetingId}`));
  ws.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as WsEvent);
    } catch {
      // ignore
    }
  };
  return ws;
}

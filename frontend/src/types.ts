export type Agent = {
  id: number;
  slug: string;
  display_name: string;
  role: string;
  stance: string;
  avatar: string;
};

export type MemoryItem = {
  id: number;
  kind: "fact" | "stance" | "meeting_summary";
  content: string;
  source_meeting_id: number | null;
  created_at: string;
};

export type ChatSession = {
  id: number;
  agent_id: number;
  started_at: string;
};

export type Message = {
  id: number;
  agent_id: number | null;
  role: string;
  phase: string | null;
  content: string;
  tool_calls_json: string | null;
  created_at: string;
};

export type Vote = {
  agent_id: number;
  decision_bps: number;
  rationale: string;
};

export type Meeting = {
  id: number;
  topic: string;
  started_at: string;
  ended_at: string | null;
  decision_bps: number | null;
  minutes_md: string | null;
  votes: Vote[];
  messages: Message[];
};

export type MeetingSummary = {
  id: number;
  topic: string;
  started_at: string;
  ended_at: string | null;
  decision_bps: number | null;
};

export type WsEvent =
  | { type: "turn_start"; agent_id?: number; agent?: string; phase?: string }
  | { type: "token"; delta: string; agent_id?: number; agent?: string; phase?: string }
  | { type: "tool_start"; name: string; args: any; id: string; agent_id?: number; agent?: string; phase?: string }
  | { type: "tool_end"; name: string; output: string; id: string; agent_id?: number; agent?: string; phase?: string }
  | { type: "final"; text: string; agent_id?: number; agent?: string; phase?: string }
  | { type: "phase"; phase: string; content: string }
  | { type: "vote"; agent_id: number; agent: string; decision_bps: number; rationale: string }
  | { type: "decision"; decision_bps: number }
  | { type: "minutes"; content: string }
  | { type: "done"; meeting_id: number }
  | { type: "error"; message: string };

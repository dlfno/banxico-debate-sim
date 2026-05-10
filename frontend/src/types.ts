export type AgentDescription = {
  tagline: string;
  summary: string;
  focus: string[];
  skills: string[];
  data_sources: string[];
};

export type VersionInfo = {
  git_commit: string;
  git_commit_date: string;
  build_time: string;
  process_started_at: string;
};

export type WorldCountry = {
  name: string;
  inflation: number | null;
  inflation_year: string | null;
  gdp_usd: number | null;
  gdp_usd_year: string | null;
  external_debt_usd: number | null;
  external_debt_usd_year: string | null;
  public_debt_pct_gdp: number | null;
  public_debt_pct_gdp_year: string | null;
};

export type WorldIndicatorMeta = {
  label: string;
  unit: string;
  source: string;
};

export type OilChokepoint = {
  name: string;
  coord: [number, number]; // [lon, lat]
  flow_mbd: number;
  note: string;
};

export type ConflictCountry = {
  iso3: string;
  name: string;
  status: string;
  note: string;
  source: string;
};

export type WorldMapData = {
  countries: Record<string, WorldCountry>; // keyed by ISO3
  indicators: Record<string, WorldIndicatorMeta>;
  oil_chokepoints: OilChokepoint[];
  conflicts: ConflictCountry[];
  generated_at: string;
};

export type Agent = {
  id: number;
  slug: string;
  display_name: string;
  role: string;
  stance: string;
  avatar: string;
  description?: AgentDescription | null;
};

export type User = {
  id: number;
  username: string;
  display_name: string;
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
  created_by: User;
};

export type ChatSessionSummary = {
  id: number;
  agent_id: number;
  agent_name: string;
  agent_avatar: string;
  started_at: string;
  last_message_at: string | null;
  message_count: number;
  created_by: User;
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
  created_by: User;
  votes: Vote[];
  messages: Message[];
};

export type MeetingSummary = {
  id: number;
  topic: string;
  started_at: string;
  ended_at: string | null;
  decision_bps: number | null;
  created_by: User;
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

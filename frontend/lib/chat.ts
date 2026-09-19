export type NodeName =
  | "entry"
  | "data_retrieval"
  | "tools"
  | "analytics"
  | "presentation";


export type ActivityKind =
  | "stage_summary"
  | "plan_update"
  | "node_update"
  | "thought_stream"
  | "thought_token"
  | "tool_call"
  | "tool_result"
  | "evidence_update"
  | "verification_update";

export interface ActivityRecord {
  eventId: string;
  sequence?: number;
  correlationId?: string;
  transition?: string;
  phase?: string;
  durationMs?: number;
  kind: ActivityKind;
  node?: NodeName;
  title: string;
  summary?: string;
  status?: string;
  emittedAt?: string;
  data: Record<string, unknown>;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  label?: string;
  summary?: string;
  status?: "running" | "ok" | "fail";
  ms?: number;
  rows?: number;
  error?: string;
  agent?: string;
  sql?: string;
}

export interface EvidenceMeta {
  source?: string;
  fetched_at?: string;
  rows?: number;
  cached?: boolean;
  season?: string;
  as_of?: string;
  qualification?: string;
  coverage?: string;
  warnings?: string[];
}

export interface ToolResult {
  tool: string;
  ok?: boolean;
  rows?: unknown;
  meta?: EvidenceMeta;
  error?: string;
}

export interface NodeState {
  status: "running" | "complete" | "error";
  thoughts: string[];
  liveThought?: string;
  liveThoughtAgent?: string;
  toolCalls: ToolCall[];
  toolResults: ToolResult[];
  tables: ToolResult[];
}

export interface AiMessage {
  text: string;
  nodes: Partial<Record<NodeName, NodeState>>;
  done: boolean;
  streaming?: boolean;
  thoughtStarted?: number;
  thoughtMs?: number;
  error?: string;
  suggestions?: string[];
  caution?: string[];
  activity?: ActivityRecord[];
  carry?: {
    players?: string[];
    teams?: string[];
    run_id?: string;
    verification?: string;
    verified_claims?: number;
    gaps?: { kind?: string; blocks?: string[] }[];
  };
}

export interface ChatMessage {
  role: "human" | "ai";
  text: string;
  ai?: AiMessage;
}

export interface ModelOption {
  id: string;
  engine: string;
  default?: boolean;
}

export interface ModelsResponse {
  models: ModelOption[];
  available: Record<string, boolean>;
}

export const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function emptyNode(): NodeState {
  return { status: "running", thoughts: [], toolCalls: [], toolResults: [], tables: [] };
}

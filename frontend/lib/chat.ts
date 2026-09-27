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
  available?: boolean;
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

// True when a final_answer event is a failure/fallback message, not a
// recovered answer. The error banner must stay up for these; clearing it
// would hide a genuine failure behind a "successful" final event.
// Signals (from backend):
// - v2 exception path: carry.verification="partial", carry.verified_claims=0,
//   carry.gaps=[{kind:"execution_failure"}],
//   text="I could not verify a publishable answer from the available data."
// - v1 scrub-everything path: text="I pulled the relevant data but could not
//   verify the figures in the summary. ..."
// A genuine answer has verified_claims > 0 (or no carry at all from older
// backends, in which case non-empty text counts as recovered).
export function isFailureFinal(text: string, carry: unknown): boolean {
  const t = text.trim();
  if (!t) return true; // empty final = nothing recovered
  // Known failure copy from both runtimes.
  if (
    t.startsWith("I could not verify a publishable answer") ||
    t.startsWith("I pulled the relevant data but could not verify")
  ) {
    return true;
  }
  // Structured signal: zero verified claims means the run produced no
  // verifiable answer, even if it emitted a non-empty final event.
  if (carry && typeof carry === "object") {
    const c = carry as Record<string, unknown>;
    if (c.verified_claims === 0) return true;
  }
  return false;
}

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
//
// Detection priority (structured signals first, prose only as last resort):
// 1. PRIMARY: carry.verification — "failed" is a failure; "pass"/"verified"
//    is recovered. "partial" is ambiguous and falls through.
// 2. SECONDARY: carry.verified_claims — 0 means the run produced no
//    verifiable answer (failure); >0 means recovered.
//    Known failure shape from backends:
//    - v2 exception path: verification="partial", verified_claims=0,
//      gaps=[{kind:"execution_failure"}],
//      text="I could not verify a publishable answer from the available data."
//    - v1 scrub-everything path: verification="partial", verified_claims=0,
//      text="I pulled the relevant data but could not verify the figures..."
// 3. TERTIARY (fallback only, for backends without structured carry):
//    known failure copy prefixes from both runtimes.
// Empty text is always a failure. Non-empty text with no carry counts as
// recovered (older backends).
export function isFailureFinal(text: string, carry?: unknown): boolean {
  const t = text.trim();
  if (!t) return true; // empty final = nothing recovered
  if (carry && typeof carry === "object") {
    const c = carry as Record<string, unknown>;
    // Primary: explicit verification status from the backend.
    if (c.verification === "failed") return true;
    if (c.verification === "pass" || c.verification === "verified") return false;
    // Secondary: zero verified claims = no verifiable answer.
    if (typeof c.verified_claims === "number") {
      return c.verified_claims === 0;
    }
    // "partial" without a claims count, or unrecognized carry shapes:
    // fall through to the prose fallback below.
  }
  // Tertiary: prose prefixes for backends that don't send structured carry.
  if (
    t.startsWith("I could not verify a publishable answer") ||
    t.startsWith("I pulled the relevant data but could not verify")
  ) {
    return true;
  }
  return false;
}

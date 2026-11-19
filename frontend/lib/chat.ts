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
  id?: string;
  name: string;
  args: Record<string, unknown>;
  label?: string;
  summary?: string;
  status?: "running" | "ok" | "fail";
  ms?: number;
  rows?: number;
  error?: string;
  reason?: string;
  agent?: string;
  sql?: string;
  startedAt?: number;
  endedAt?: number;
}

interface EvidenceMeta {
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

interface NodeState {
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
    output_statuses?: {
      requirement_kind?: string;
      requirement_id?: string | null;
      output_id?: string;
      status?: string;
      value?: string;
      unit?: string;
      subject_type?: string;
      subject_id?: string | number | null;
    }[];
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

export interface BatchedStreamEvent {
  type: string;
  data: unknown;
}

export interface StreamBatcher {
  push: (type: string, data: unknown) => void;
  flush: () => void;
  size: () => number;
}

export const TERMINAL_STREAM_EVENTS = ["final_answer", "graph_end", "error"];

export function isImmediateEvent(type: string): boolean {
  return type === "token";
}

export function createStreamBatcher(
  onFlush: (events: BatchedStreamEvent[]) => void,
  schedule: (flush: () => void) => void = (flush) => {
    if (typeof requestAnimationFrame !== "undefined") requestAnimationFrame(flush);
    else setTimeout(flush, 0);
  },
  terminalTypes: string[] = TERMINAL_STREAM_EVENTS,
): StreamBatcher {
  let queue: BatchedStreamEvent[] = [];
  let scheduled = false;
  const drain = () => {
    scheduled = false;
    if (!queue.length) return;
    const events = queue;
    queue = [];
    onFlush(events);
  };
  return {
    push: (type, data) => {
      queue.push({ type, data });
      if (terminalTypes.includes(type)) {
        drain();
        return;
      }
      if (!scheduled) {
        scheduled = true;
        schedule(drain);
      }
    },
    flush: drain,
    size: () => queue.length,
  };
}

export const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function emptyNode(): NodeState {
  return { status: "running", thoughts: [], toolCalls: [], toolResults: [], tables: [] };
}







































export function isFailureFinal(text: string, carry?: unknown): boolean {
  const t = text.trim();
  if (!t) return true;
  if (carry && typeof carry === "object") {
    const c = carry as Record<string, unknown>;

    if (c.verification === "failed") return true;
    if (c.verification === "pass" || c.verification === "verified") return false;

    if (typeof c.verified_claims === "number") {
      return c.verified_claims === 0;
    }


  }

  if (
    t.startsWith("I could not verify a publishable answer") ||
    t.startsWith("I pulled the relevant data but could not verify")
  ) {
    return true;
  }
  return false;
}

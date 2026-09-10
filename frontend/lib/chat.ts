export type NodeName =
  | "entry"
  | "data_retrieval"
  | "tools"
  | "analytics"
  | "presentation";

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

export interface ToolResult {
  tool: string;
  ok?: boolean;
  rows?: unknown;
  meta?: { source?: string; fetched_at?: string; rows?: number; cached?: boolean };
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

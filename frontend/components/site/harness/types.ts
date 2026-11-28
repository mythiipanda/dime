import type { DimeArtifact, StreamSnapshot, ThinkingRow, ToolState, VerificationCarry } from "@/lib/dime-stream";

export type Tab = { id: string; label: string };

export const REFERENCE_TAB = "t1";

export const FADE_UP = "fade-up 280ms cubic-bezier(0.23,1,0.32,1) both";

export type ViewKey =
  | "matchups"
  | "trades"
  | "awards"
  | "warehouse";

export type AssistantFailure = { kind: string; message: string };

export type ChatMsg =
  | { role: "user"; text: string }
  | {
      role: "assistant";
      text: string;
      artifacts: DimeArtifact[];
      suggestions: string[];
      carry: VerificationCarry | null;
      failure: AssistantFailure | null;
      stopped?: boolean;
      thinking?: ThinkingRow[];
      tools?: ToolState[];
    };

export type LiveRun = StreamSnapshot & { id: number; startedAt: number };

export function assistantMessageFromSnapshot(
  snap: StreamSnapshot,
  message: string,
  stopped = snap.halted === true,
): Extract<ChatMsg, { role: "assistant" }> {
  return {
    role: "assistant",
    text: snap.text,
    artifacts: snap.artifacts,
    suggestions: snap.suggestions,
    carry: snap.carry,
    failure: snap.failed ?? (message ? { kind: "connection", message } : null),
    thinking: snap.thinking ?? [],
    tools: snap.tools ?? [],
    ...(stopped ? { stopped } : {}),
  };
}

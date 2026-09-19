import type { ActivityKind, ActivityRecord, NodeName } from "./chat";

export const ACTIVITY_TYPES = new Set<string>([
  "stage_summary", "plan_update", "node_update", "thought_stream",
  "thought_token", "tool_call", "tool_result", "evidence_update",
  "verification_update",
]);

const text = (value: unknown) => String(value || "").replace(/_/g, " ");

export function activityRecordFromEvent(
  type: string,
  raw: Record<string, unknown>,
  fallbackIndex: number,
): ActivityRecord | null {
  if (!ACTIVITY_TYPES.has(type)) return null;
  const payload = raw.data && typeof raw.data === "object" && !Array.isArray(raw.data)
    ? raw.data as Record<string, unknown>
    : {};
  const titles: Record<string, string> = {
    stage_summary: text(raw.title) || `Stage: ${text(raw.phase || raw.node)}`,
    plan_update: text(raw.title) || `Plan: ${text(payload.capability || payload.plan_node_id)}`,
    node_update: text(raw.title) || text(raw.node) || "Runtime stage",
    thought_stream: text(raw.agent) ? `${text(raw.agent)} thought` : "Reasoning",
    thought_token: text(raw.agent) ? `${text(raw.agent)} thought` : "Reasoning",
    tool_call: text(raw.label || raw.title || raw.name || payload.name) || "Tool call",
    tool_result: `${text(raw.title || raw.name || payload.name) || "Tool"} result`,
    evidence_update: text(raw.title) || `Evidence: ${text(payload.capability || payload.evidence_id)}`,
    verification_update: text(raw.title) || "Verification",
  };
  const summary = raw.summary ?? raw.text ?? raw.reason ?? raw.message;
  return {
    eventId: typeof raw.event_id === "string" ? raw.event_id : `legacy:${fallbackIndex}:${type}`,
    sequence: typeof raw.sequence === "number" ? raw.sequence : undefined,
    correlationId: typeof raw.correlation_id === "string" ? raw.correlation_id : undefined,
    transition: typeof raw.transition === "string" ? raw.transition : undefined,
    phase: typeof raw.phase === "string" ? raw.phase : undefined,
    durationMs: typeof raw.duration_ms === "number" ? raw.duration_ms : undefined,
    kind: type as ActivityKind,
    node: raw.node as NodeName | undefined,
    title: titles[type] || text(type),
    summary: typeof summary === "string" ? summary : undefined,
    status: typeof raw.status === "string" ? raw.status : undefined,
    emittedAt: typeof raw.emitted_at === "string" ? raw.emitted_at : undefined,
    // Preserve the exact wire payload. Nested normalized-event data is not
    // flattened, so replay and live records remain byte-shape equivalent.
    data: { ...raw },
  };
}

// Mirrors the narrowed public contract under backend QA. Deliberately excludes
// raw goals, requirement prose, entity IDs, free-form plan descriptions, source
// strings, warnings, claim results, repair instructions, and contradiction prose.
export const ACTIVITY_CONTRACT_FIXTURE: Record<string, unknown>[] = [
  { type: "tool_call", event_id: "run-a:1", sequence: 1, emitted_at: "2026-09-18T20:00:00Z", phase: "execute", status: "running", title: "Team ratings", transition: "started", correlation_id: "call-1", data: { name: "team_ratings", args: { season: "2025-26" } } },
  { type: "tool_result", event_id: "run-a:2", sequence: 2, emitted_at: "2026-09-18T20:00:01Z", phase: "execute", status: "complete", title: "Team ratings", transition: "succeeded", correlation_id: "call-1", duration_ms: 14, data: { name: "team_ratings", rows: 30 } },
  { type: "stage_summary", event_id: "run-a:3", sequence: 3, emitted_at: "2026-09-18T20:00:01Z", phase: "understand", status: "complete", title: "Request understood", transition: "completed", correlation_id: "stage:understand", data: { mode: "quick", season: "2025-26", entity_count: 1, requirement_count: 1 } },
  { type: "plan_update", event_id: "run-a:4", sequence: 4, emitted_at: "2026-09-18T20:00:01Z", phase: "plan", status: "complete", title: "Plan accepted", transition: "completed", correlation_id: "stage:plan", data: { node_count: 1, nodes: [{ id: "rank", status: "pending", capabilities: ["team_ratings"] }] } },
  { type: "evidence_update", event_id: "run-a:5", sequence: 5, emitted_at: "2026-09-18T20:00:01Z", phase: "execute", status: "complete", title: "Evidence admitted", transition: "admitted", correlation_id: "evidence-1", data: { capability: "team_ratings", row_count: 30, season: "2025-26", source_as_of: "2026-09-18" } },
  { type: "verification_update", event_id: "run-a:6", sequence: 6, emitted_at: "2026-09-18T20:00:02Z", phase: "verify", status: "pass", title: "Verification updated", transition: "snapshot", correlation_id: "verification:initial", data: { round: "initial", total_claims: 1, supported_claims: 1, missing_branch_count: 0, blocked_requirement_count: 0 } },
];

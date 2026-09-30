import type { ActivityKind, ActivityRecord, NodeName } from "./chat";

const ACTIVITY_TYPES = new Set<string>([
  "stage_summary", "plan_update", "node_update", "thought_stream",
  "thought_token", "tool_call", "tool_result", "evidence_update",
  "verification_update",
]);

const text = (value: unknown) => String(value || "").replace(/_/g, " ");

export function mergeActivityRecord(
  items: ActivityRecord[],
  incoming: ActivityRecord,
): ActivityRecord[] {
  if (items.some((item) => item.eventId === incoming.eventId)) return items;
  return [...items, incoming].sort((a, b) => {
    if (a.sequence !== undefined && b.sequence !== undefined) return a.sequence - b.sequence;
    if (a.sequence !== undefined) return -1;
    if (b.sequence !== undefined) return 1;
    return 0;
  });
}

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
    title: titles[type],
    summary: typeof summary === "string" ? summary : undefined,
    status: typeof raw.status === "string" ? raw.status : undefined,
    emittedAt: typeof raw.emitted_at === "string" ? raw.emitted_at : undefined,
    
    


    data: { ...raw },
  };
}







export interface ToolPair {
  call?: ActivityRecord;
  result?: ActivityRecord;
}

export type PlanStepState = "pending" | "running" | "done";

export interface PlanStep {
  capability: string;
  state: PlanStepState;
}

export function recordField(item: ActivityRecord, key: string): unknown {
  const raw = item.data as Record<string, unknown>;
  if (raw[key] !== undefined) return raw[key];
  const nested = raw.data;
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return (nested as Record<string, unknown>)[key];
  }
  return undefined;
}

const recordString = (item: ActivityRecord, key: string): string | undefined => {
  const value = recordField(item, key);
  return typeof value === "string" && value ? value : undefined;
};

export const recordKey = (item: ActivityRecord): string | undefined =>
  recordString(item, "name") ?? recordString(item, "capability");

export const recordLabel = (item: ActivityRecord): string | undefined =>
  recordString(item, "label") ?? recordKey(item);

const recordName = (item: ActivityRecord): string | undefined => recordKey(item);

export function pairToolItems(items: ActivityRecord[]): ToolPair[] {
  const pairs: ToolPair[] = [];
  const openByCorrelation = new Map<string, ToolPair>();
  const openByName: ToolPair[] = [];
  for (const item of items) {
    if (item.kind !== "tool_call" && item.kind !== "tool_result") continue;
    if (item.kind === "tool_call") {
      const pair: ToolPair = { call: item };
      pairs.push(pair);
      if (item.correlationId) openByCorrelation.set(item.correlationId, pair);
      else openByName.push(pair);
      continue;
    }
    let pair: ToolPair | undefined;
    if (item.correlationId) pair = openByCorrelation.get(item.correlationId);
    if (!pair) {
      const name = recordName(item);
      for (const open of openByName) {
        if (!open.result && recordName(open.call!) === name) {
          pair = open;
          break;
        }
      }
    }
    if (pair && !pair.result) {
      pair.result = item;
      if (pair.call?.correlationId) openByCorrelation.delete(pair.call.correlationId);
      const at = openByName.indexOf(pair);
      if (at >= 0) openByName.splice(at, 1);
    } else {
      pairs.push({ result: item });
    }
  }
  return pairs;
}

export function planSteps(items: ActivityRecord[]): PlanStep[] {
  const plans = items.filter((i) => i.kind === "plan_update");
  if (!plans.length) return [];
  const latest = plans[plans.length - 1];
  const d = latest.data.data && typeof latest.data.data === "object" && !Array.isArray(latest.data.data)
    ? latest.data.data as Record<string, unknown>
    : {};
  const capabilities = Array.isArray(d.capabilities)
    ? d.capabilities.filter((c): c is string => typeof c === "string" && !!c)
    : [];
  const running = new Set<string>();
  const done = new Set<string>();
  for (const item of items) {
    const name = recordName(item);
    if (!name) continue;
    if (item.kind === "tool_call") running.add(name);
    if (item.kind === "tool_result") {
      running.delete(name);
      if (item.transition !== "failed" && item.status !== "fail" && item.status !== "failed") done.add(name);
    }
    if (item.kind === "evidence_update" && item.transition === "admitted") {
      running.delete(name);
      done.add(name);
    }
  }
  return capabilities.map((capability) => ({
    capability,
    state: done.has(capability) ? "done" : running.has(capability) ? "running" : "pending",
  }));
}

export function isNoiseRecord(item: ActivityRecord): boolean {
  if (item.kind === "thought_stream" || item.kind === "thought_token") return true;
  if (item.kind === "node_update" && item.node === "entry") return true;
  return false;
}

export const ACTIVITY_CONTRACT_FIXTURE: Record<string, unknown>[] = [
  { type: "tool_call", event_id: "run-a:1", sequence: 1, emitted_at: "2026-09-18T20:00:00Z", phase: "execute", status: "running", title: "Tool running", transition: "started", correlation_id: "call-1", data: { name: "team_ratings", argument_count: 1, unknown_argument_count: 0 } },
  { type: "tool_result", event_id: "run-a:2", sequence: 2, emitted_at: "2026-09-18T20:00:01Z", phase: "execute", status: "complete", title: "Tool complete", transition: "succeeded", correlation_id: "call-1", duration_ms: 14, data: { name: "team_ratings", rows: 30 } },
  { type: "stage_summary", event_id: "run-a:3", sequence: 3, emitted_at: "2026-09-18T20:00:01Z", phase: "understand", status: "complete", title: "Request understood", transition: "completed", correlation_id: "stage:understand", data: { mode: "quick", season: "2025-26", entity_count: 1, requirement_count: 1, calculation_count: 0 } },
  { type: "plan_update", event_id: "run-a:4", sequence: 4, emitted_at: "2026-09-18T20:00:01Z", phase: "plan", status: "complete", title: "Plan accepted", transition: "completed", correlation_id: "stage:plan", data: { node_count: 1, capabilities: ["team_ratings"], unknown_capability_count: 0 } },
  { type: "evidence_update", event_id: "run-a:5", sequence: 5, emitted_at: "2026-09-18T20:00:01Z", phase: "execute", status: "complete", title: "Evidence admitted", transition: "admitted", correlation_id: "evidence-1", data: { capability: "team_ratings", rows: 30, season: "2025-26", as_of: "2026-09-18", observed_at: "2026-09-18T20:00:01Z", qualification: "present", coverage: "present", warning_count: 0 } },
  { type: "verification_update", event_id: "run-a:6", sequence: 6, emitted_at: "2026-09-18T20:00:02Z", phase: "verify", status: "pass", title: "Verification updated", transition: "snapshot", correlation_id: "verification:initial", data: { round: "initial", supported_count: 1, claim_count: 1, missing_count: 0, contradiction_count: 0, repair_count: 0 } },
];

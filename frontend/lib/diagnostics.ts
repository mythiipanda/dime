export interface SseEvent {
  type: string;
  data: unknown;
}

export interface BindingDiagnostic {
  run_id: string;
  claim_index: number;
  requirement_kind: string;
  requirement_id: string | null;
  output_id: string;
  node_id: string | null;
  evidence_id: string | null;
  selector: string | null;
  row_selector: string | null;
  subject_selector: string | null;
  subject_entity_type: string | null;
  subject_entity_id: string | null;
  declared_value: Record<string, unknown>;
  declared_unit: Record<string, unknown> | null;
  domain: string | null;
  evidence_capability: string | null;
  reanchor_changed: boolean;
  rejection: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseSseText(text: string): SseEvent[] {
  const events: SseEvent[] = [];
  for (const part of String(text || "").split("\n\n")) {
    const lines = part.split("\n");
    const typeLine = lines.find((l) => l.startsWith("event:"));
    const dataLines = lines
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trim());
    if (!typeLine || !dataLines.length) continue;
    const type = typeLine.slice(6).trim();
    const raw = dataLines.join("\n");
    let data: unknown = raw;
    try {
      data = JSON.parse(raw);
    } catch {}
    events.push({ type, data });
  }
  return events;
}

export function isBindingDiagnostic(data: unknown): data is BindingDiagnostic {
  if (!isRecord(data)) return false;
  return (
    typeof data.output_id === "string" &&
    typeof data.rejection === "string" &&
    typeof data.claim_index === "number"
  );
}

export function bindingDiagnostics(events: SseEvent[]): BindingDiagnostic[] {
  return events.map((e) => e.data).filter(isBindingDiagnostic);
}

export interface DiffRow {
  key: string;
  output_id: string;
  claim_index: number;
  left: BindingDiagnostic | null;
  right: BindingDiagnostic | null;
  changed: boolean;
}

export function diffDiagnostics(
  left: BindingDiagnostic[],
  right: BindingDiagnostic[],
): DiffRow[] {
  const rightByOutput = new Map(right.map((d) => [d.output_id, d]));
  const seen = new Set<string>();
  const rows: DiffRow[] = [];
  for (const l of left) {
    if (seen.has(l.output_id)) continue;
    seen.add(l.output_id);
    const r = rightByOutput.get(l.output_id) || null;
    rows.push({
      key: l.output_id,
      output_id: l.output_id,
      claim_index: l.claim_index,
      left: l,
      right: r,
      changed: !r || r.rejection !== l.rejection,
    });
  }
  for (const r of right) {
    if (seen.has(r.output_id)) continue;
    seen.add(r.output_id);
    rows.push({
      key: r.output_id,
      output_id: r.output_id,
      claim_index: r.claim_index,
      left: null,
      right: r,
      changed: true,
    });
  }
  return rows;
}

export function diffMarker(row: DiffRow): string {
  if (!row.left) return "only in run B";
  if (!row.right) return "only in run A";
  return row.changed ? "changed" : "same";
}

export interface RevisionInfo {
  revision: string;
  runtime: string;
}

export function revisionInfo(data: unknown, runtime: string): RevisionInfo | null {
  if (!isRecord(data)) return null;
  if (typeof data.revision !== "string" || !data.revision) return null;
  return { revision: data.revision, runtime };
}

export function shortRevision(revision: string): string {
  return String(revision || "").slice(0, 8);
}

export function runIdOf(events: SseEvent[]): string | null {
  for (const e of events) {
    if (e.type !== "final_answer") continue;
    if (!isRecord(e.data)) continue;
    const carry = (e.data as Record<string, unknown>).carry;
    if (isRecord(carry) && typeof carry.run_id === "string" && carry.run_id) {
      return carry.run_id;
    }
  }
  for (const e of events) {
    if (isRecord(e.data) && typeof e.data.run_id === "string" && e.data.run_id) {
      return e.data.run_id;
    }
  }
  return null;
}

export interface FastFailVerdict {
  fastFail: boolean;
  understandMs: number | null;
  gapKinds: string[];
}

function carryOf(events: SseEvent[]): Record<string, unknown> | null {
  for (const e of events) {
    if (e.type !== "final_answer") continue;
    if (!isRecord(e.data)) continue;
    const carry = (e.data as Record<string, unknown>).carry;
    if (isRecord(carry)) return carry;
  }
  return null;
}

export function fastFailVerdict(events: SseEvent[]): FastFailVerdict {
  const carry = carryOf(events);
  const latencies = carry && isRecord(carry.stage_latencies_ms) ? carry.stage_latencies_ms : null;
  const rawMs = latencies ? latencies.understand : undefined;
  const understandMs = typeof rawMs === "number" && Number.isFinite(rawMs) ? rawMs : null;
  const gaps = carry && Array.isArray(carry.gaps) ? carry.gaps : [];
  const gapKinds = gaps
    .map((g) => (isRecord(g) && typeof g.kind === "string" ? g.kind : ""))
    .filter(Boolean);
  return {
    fastFail:
      understandMs !== null && understandMs < 1000 && gapKinds.includes("execution_failure"),
    understandMs,
    gapKinds,
  };
}

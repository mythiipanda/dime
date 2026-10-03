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

import type { AiMessage } from "./chat";

export type BadgeState = "verified" | "partial" | "unverified" | "unknown";

export interface EvidenceGap {
  kind?: string;
  blocks?: string[];
}

export interface OutputStatus {
  requirement_kind?: string;
  requirement_id?: string | null;
  output_id?: string;
  status?: string;
  value?: string;
  unit?: string;
  subject_type?: string;
  subject_id?: string | number | null;
}

export interface EvidenceCarry {
  run_id?: string;
  verification?: string;
  verified_claims?: number;
  output_statuses?: OutputStatus[];
  gaps?: EvidenceGap[];
}

export interface EvidenceProvenance {
  capability?: string;
  season?: string;
  as_of?: string;
  source_as_of?: string;
  fetched_at?: string;
  observed_at?: string;
}

export interface EvidenceRow {
  key: string;
  finding: string;
  detail: string;
  value: string;
  source: string;
  ok: boolean;
}

export interface EvidenceSummary {
  state: BadgeState;
  backed: number;
  total: number;
  gaps: string[];
  rows: EvidenceRow[];
}

export function humanize(token: string): string {
  const words = String(token || "")
    .split(/[_-]+/)
    .map((w) => w.trim())
    .filter(Boolean);
  if (words.length > 1 && (words[0] === "get" || words[0] === "fetch")) {
    words.shift();
  }
  if (!words.length) return "";
  const joined = words.join(" ");
  return joined.charAt(0).toUpperCase() + joined.slice(1);
}

export function gapMessage(kind: string): string {
  const key = String(kind || "");
  switch (key) {
    case "missing_evidence":
      return "No data covered this.";
    case "source_conflict":
      return "Sources disagreed on this.";
    case "unsupported_claim":
      return "The data did not back this.";
    case "execution_failure":
      return "The lookup failed.";
    case "synthesis_incomplete":
      return "This did not reach the answer.";
    case "judge_unavailable":
      return "Dime could not double-check this.";
    case "run_timeout":
      return "The run ran out of time.";
    case "":
      return "No reason given.";
    default:
      return humanize(key) + ".";
  }
}

function asDatePart(raw: unknown): string {
  if (typeof raw !== "string" || !raw) return "";
  return raw.length >= 10 ? raw.slice(0, 10) : raw;
}

function provenanceSource(meta: EvidenceProvenance | undefined): string {
  if (!meta) return "";
  const parts: string[] = [];
  if (meta.capability) parts.push(humanize(meta.capability));
  if (meta.season) parts.push(meta.season);
  const stamp = asDatePart(meta.as_of || meta.source_as_of || meta.fetched_at || meta.observed_at);
  if (stamp) parts.push(stamp);
  return parts.join(" · ");
}

function subjectLabel(id: unknown): string {
  if (id === null || id === undefined || id === "") return "";
  return String(id);
}

function subjectDetail(type: unknown, outputId: string): string {
  const output = humanize(outputId);
  if (typeof type === "string" && type) return humanize(type) + " · " + output;
  return output;
}

function valueWithUnit(value: unknown, unit: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  if (!text) return "";
  if (typeof unit === "string" && unit && unit !== "unitless") return text + " " + unit;
  return text;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function allTables(ai: AiMessage): unknown[] {
  const out: unknown[] = [];
  const nodes = ai.nodes || {};
  for (const node of Object.values(nodes)) {
    if (!node || !Array.isArray(node.tables)) continue;
    out.push(...node.tables);
  }
  return out;
}

function tableRow(table: unknown, index: number): EvidenceRow | null {
  if (!isRecord(table)) return null;
  if (isRecord(table.provenance) || typeof table.output_id === "string") {
    const t = table as Record<string, unknown>;
    const provenance = isRecord(t.provenance) ? (t.provenance as EvidenceProvenance) : undefined;
    const subject = subjectLabel(t.subject_id);
    const outputId = typeof t.output_id === "string" ? t.output_id : "";
    const value = valueWithUnit(
      t.value !== undefined ? t.value : t.input_value,
      t.unit,
    );
    return {
      key: "claim-" + index + "-" + outputId,
      finding: subject || humanize(outputId),
      detail: subject ? subjectDetail(t.subject_type, outputId) : "",
      value,
      source: provenanceSource(provenance),
      ok: true,
    };
  }
  if (typeof table.tool === "string") {
    const t = table as { tool: string; meta?: EvidenceProvenance };
    return {
      key: "tool-" + index + "-" + t.tool,
      finding: humanize(t.tool),
      detail: "",
      value: "",
      source: provenanceSource(t.meta),
      ok: true,
    };
  }
  return null;
}

function incompleteRows(statuses: OutputStatus[], gaps: EvidenceGap[]): EvidenceRow[] {
  const reason = gaps.length ? gapMessage(gaps[0].kind || "") : "No reason given.";
  const rows: EvidenceRow[] = [];
  statuses.forEach((status, index) => {
    if (!status || status.status === "complete") return;
    const outputId = typeof status.output_id === "string" ? status.output_id : "";
    const subject = subjectLabel(status.subject_id);
    rows.push({
      key: "gap-" + index + "-" + outputId,
      finding: subject || humanize(outputId) || "A finding",
      detail: reason,
      value: "",
      source: "",
      ok: false,
    });
  });
  return rows;
}

function gapOnlyRows(gaps: EvidenceGap[]): EvidenceRow[] {
  return gaps.map((gap, index) => ({
    key: "gap-" + index,
    finding: "This answer",
    detail: gapMessage(gap && typeof gap.kind === "string" ? gap.kind : ""),
    value: "",
    source: "",
    ok: false,
  }));
}

export function evidenceRows(ai: AiMessage): EvidenceRow[] {
  const tables = allTables(ai);
  const rows: EvidenceRow[] = [];
  tables.forEach((table, index) => {
    const row = tableRow(table, index);
    if (row) rows.push(row);
  });
  const carry = (ai.carry || {}) as EvidenceCarry;
  const statuses = Array.isArray(carry.output_statuses) ? carry.output_statuses : [];
  const gaps = Array.isArray(carry.gaps) ? carry.gaps : [];
  if (statuses.length > 0) {
    rows.push(...incompleteRows(statuses, gaps));
  } else if (rows.length === 0 && gaps.length > 0) {
    rows.push(...gapOnlyRows(gaps));
  }
  return rows;
}

export function badgeState(carry: unknown): BadgeState {
  if (!isRecord(carry)) return "unknown";
  const c = carry as EvidenceCarry;
  const verdict = typeof c.verification === "string" ? c.verification : "";
  const gaps = Array.isArray(c.gaps) ? c.gaps : [];
  const statuses = Array.isArray(c.output_statuses) ? c.output_statuses : [];
  const backed =
    typeof c.verified_claims === "number"
      ? c.verified_claims
      : statuses.filter((s) => s && s.status === "complete").length;
  const hasSignal =
    verdict !== "" ||
    typeof c.verified_claims === "number" ||
    gaps.length > 0 ||
    statuses.length > 0;
  if (backed > 0) {
    if ((verdict === "pass" || verdict === "verified") && gaps.length === 0) return "verified";
    return "partial";
  }
  if (hasSignal) return "unverified";
  return "unknown";
}

export function summarizeEvidence(ai: AiMessage): EvidenceSummary {
  const rows = evidenceRows(ai);
  const carry = (ai.carry || {}) as EvidenceCarry;
  const gaps = Array.isArray(carry.gaps) ? carry.gaps : [];
  const statuses = Array.isArray(carry.output_statuses) ? carry.output_statuses : [];
  const backed =
    typeof carry.verified_claims === "number"
      ? carry.verified_claims
      : rows.filter((r) => r.ok).length;
  const total = Math.max(statuses.length, rows.length, backed);
  return {
    state: badgeState(ai.carry),
    backed,
    total,
    gaps: gaps.map((g) => (g && typeof g.kind === "string" ? g.kind : "")),
    rows,
  };
}

export function badgeText(summary: EvidenceSummary): string {
  const one = summary.total === 1 ? "finding" : "findings";
  if (summary.state === "verified") return "Verified · " + summary.backed + " of " + summary.total + " " + one;
  if (summary.state === "partial") return "Some verified · " + summary.backed + " of " + summary.total + " " + one;
  if (summary.state === "unverified") return "Could not verify";
  return "";
}

import type { AnswerSubmission, PiSource } from "../evidence";

export interface TextDeltaEvent {
  type: "text_delta";
  text: string;
}

export interface ThinkingEvent {
  type: "thinking";
  label: string;
  detail?: string;
}

export type ToolActivityStatus = "running" | "ok" | "fail";

export interface ToolActivityEvent {
  type: "tool_activity";
  id: string | null;
  name: string;
  label: string;
  status: ToolActivityStatus;
  rows?: number;
  ms?: number;
  args?: string[];
  error?: string;
}

export type ProvenanceOrigin =
  | "live"
  | "warehouse"
  | "mixed"
  | "partly-undeclared"
  | "undeclared";

export interface ProvenanceEvidence {
  label: string;
  provenance: DimeProvenance;
}

export interface DimeProvenance {
  origin: ProvenanceOrigin;
  capability?: string;
  warehouseId?: string;
  dataset?: string;
  season?: string;
  asOf?: string;
  as_of?: string;
  sql?: string;
  liveSources: string[];
  liveSourceIds?: string[];
  evidence?: ProvenanceEvidence[];
}

export type VerificationStatus = "pass" | "partial" | "unknown";

export interface EvidenceGapNote {
  kind: string;
  blocks: string[];
}

export interface VerificationCarry {
  sourceRefs?: string[];
  sources?: PiSource[];
  verification: VerificationStatus;
  verifiedClaims: number | null;
  runId?: string;
  gaps: EvidenceGapNote[];
  gapsReadable: boolean;
  submission?: AnswerSubmission;
}

export type VerificationState = "verified" | "partial" | "unverified" | "unknown";

export interface VerificationDisclosure {
  state: VerificationState;
  headline: string;
  detail: string;
  gaps: EvidenceGapNote[];
}

export interface TableArtifactPayload {
  kind: "table";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  columns: { key: string; label: string; numeric?: boolean }[];
  rows: (string | number | null)[][];
  footnote?: string;
}

export interface CompareArtifactPayload {
  kind: "compare";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  aName: string;
  bName: string;
  rows: { label: string; a: number; b: number }[];
}

export type ChartTone = "ink" | "muted" | "accent" | "good" | "warn";

export interface ChartSeriesPayload {
  name: string;
  values: (number | null)[];
  tone?: ChartTone;
  unit?: string;
}

export interface ChartMark {
  value: number;
  label: string;
}

export interface ChartAnnotation {
  index: number;
  text: string;
}

export interface ChartArtifactPayload {
  kind: "chart";
  title: string;
  subtitle?: string;
  variant?: "line" | "bar";
  source?: string;
  provenance?: DimeProvenance;
  series: ChartSeriesPayload[];
  footnote?: string;
  unit?: string;
  xLabels?: string[];
  xLabel?: string;
  yLabel?: string;
  marks?: ChartMark[];
  annotations?: ChartAnnotation[];
  labelValues?: boolean;
}

export interface ShotChartArtifactPayload {
  kind: "shot_chart";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  zones: { x: number; y: number; att: number; pct: number; label?: string; makes?: number; delta?: number }[];
  footnote?: string;
}

export interface ScatterArtifactPayload {
  kind: "scatter";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  xLabel: string;
  yLabel: string;
  points: { label: string; x: number; y: number; highlight?: boolean }[];
  xMid?: number;
  yMid?: number;
  footnote?: string;
}

export interface PlayerCardSectionPayload {
  label: string;
  sourceRef: string;
  sourceRow: number;
  metrics?: { column: string; label: string; value: number | null; unit?: string }[];
  fields?: { column: string; label: string; value: string | null }[];
  provenance?: DimeProvenance;
}

export interface MemoAnchor {
  ref: string;
  row: number;
  columns: string[];
}

export interface MemoSectionPayload {
  heading: string;
  body: string;
  anchors?: MemoAnchor[];
}

export interface MemoArtifactPayload {
  kind: "memo";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  subtitle?: string;
  text: string;
  sections?: MemoSectionPayload[];
  footnote?: string;
}
export interface PlayerCardArtifactPayload {
  kind: "player_card";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  playerName: string;
  team?: string;
  sourceRef: string;
  sourceRow: number;
  nameColumn: string;
  teamColumn?: string;
  metrics: { column: string; label: string; value: number | null; unit?: string }[];
  sections?: PlayerCardSectionPayload[];
}

export interface TeamCardArtifactPayload {
  kind: "team_card";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  teamName: string;
  sourceRef: string;
  sourceRow: number;
  nameColumn: string;
  metrics: { column: string; label: string; value: number | null; unit?: string }[];
  sections?: PlayerCardSectionPayload[];
}


export interface TradeVerdictTeamPayload {
  team: string;
  playersOut: string[];
  playersIn: string[];
  outgoing?: number;
  incoming?: number;
  payrollBefore?: number;
  payrollAfter?: number;
  allowedIncoming?: number;
  matchRule?: string;
  hardCap?: string;
  overApron1?: boolean;
  overApron2?: boolean;
  matchingFailed?: boolean;
  aggregates?: boolean;
  tpeCreation?: { amount: number; condition?: string };
  picksOut?: { year: number; round: number; swap?: boolean; protection?: string }[];
  picksIn?: { year: number; round: number; swap?: boolean; protection?: string }[];
}

export interface TradeVerdictArtifactPayload {
  kind: "trade_verdict";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  legal: boolean;
  issues?: string[];
  teams: TradeVerdictTeamPayload[];
  checks?: { rule: string; note?: string }[];
  evaluationTool?: string;
  sourceRef: string;
}

export interface CapSummaryArtifactPayload {
  kind: "cap_summary";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  team: string;
  season?: string;
  payrollBefore: number;
  payrollAfter: number;
  delta?: number;
  capRoom?: number;
  capRoomBefore?: number;
  taxRoom?: number;
  roomApron1?: number;
  roomApron2?: number;
  teamSalaryBefore?: number;
  teamSalaryAfter?: number;
  capHoldsAfter?: number;
  rosterChargesAfter?: number;
  rosterBefore?: number;
  rosterAfter?: number;
  overTax?: boolean;
  overApron1?: boolean;
  overApron2?: boolean;
  hardCap?: string;
  issues?: string[];
  steps?: { kind: string; detail: string; delta?: number; payroll?: number }[];
  restrictions?: { threshold: string; rule: string }[];
  evaluationTool?: string;
  sourceRef: string;
}

export type DimeArtifact =
  | TableArtifactPayload
  | CompareArtifactPayload
  | ChartArtifactPayload
  | ShotChartArtifactPayload
  | ScatterArtifactPayload
  | PlayerCardArtifactPayload
  | TeamCardArtifactPayload
  | MemoArtifactPayload
  | TradeVerdictArtifactPayload
  | CapSummaryArtifactPayload;

export interface ArtifactEvent {
  type: "artifact";
  artifact: DimeArtifact;
}

export interface FinalEvent {
  type: "final";
  text: string;
  carry: VerificationCarry | null;
  artifacts?: DimeArtifact[];
}

export interface FailureEvent {
  type: "failure";
  kind: string;
  message: string;
}

export type DimeStreamEvent =
  | TextDeltaEvent
  | ThinkingEvent
  | ToolActivityEvent
  | ArtifactEvent
  | FinalEvent
  | FailureEvent;

export interface ThinkingRow {
  label: string;
  detail?: string;
}

export interface ToolState {
  key: string;
  name: string;
  label: string;
  status: ToolActivityStatus;
  rows?: number;
  ms?: number;
  args?: string[];
  error?: string;
}

export interface StreamFailure {
  kind: string;
  message: string;
}

export interface StreamSnapshot {
  text: string;
  thinking: ThinkingRow[];
  tools: ToolState[];
  artifacts: DimeArtifact[];
  suggestions: string[];
  carry: VerificationCarry | null;
  failed: StreamFailure | null;
  done: boolean;
  halted?: boolean;
}

export interface DimeStreamCallbacks {
  onUpdate: (snap: StreamSnapshot) => void;
  onDone: (snap: StreamSnapshot) => void;
  onError: (snap: StreamSnapshot, message: string) => void;
}

export function asRecord(data: unknown): Record<string, unknown> {
  return typeof data === "object" && data !== null && !Array.isArray(data)
    ? (data as Record<string, unknown>)
    : {};
}

export function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function trimmedString(raw: unknown): string | undefined {
  if (typeof raw !== "string") return undefined;
  const trimmed = raw.trim();
  return trimmed ? trimmed : undefined;
}

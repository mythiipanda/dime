import { postChatStream } from "./api";

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
  season?: string;
  asOf?: string;
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
  verification: VerificationStatus;
  verifiedClaims: number | null;
  runId?: string;
  gaps: EvidenceGapNote[];
  gapsReadable: boolean;
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
  rows: (string | number)[][];
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

export interface ChartArtifactPayload {
  kind: "chart";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  series: { name: string; values: number[] }[];
  footnote?: string;
}

export interface ShotChartArtifactPayload {
  kind: "shot_chart";
  title: string;
  source?: string;
  provenance?: DimeProvenance;
  zones: { x: number; y: number; att: number; pct: number }[];
}

export type DimeArtifact =
  | TableArtifactPayload
  | CompareArtifactPayload
  | ChartArtifactPayload
  | ShotChartArtifactPayload;

export interface ArtifactEvent {
  type: "artifact";
  artifact: DimeArtifact;
}

export interface FinalEvent {
  type: "final";
  text: string;
  carry: VerificationCarry | null;
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

type ToolNarration = { running: string; done: string };

const TOOL_LABELS: Record<string, ToolNarration> = {
  entity_resolution: { running: "Resolving players and teams", done: "Resolved players and teams" },
  warehouse_freshness: { running: "Checking data freshness", done: "Checked data freshness" },
  standings: { running: "Pulling standings", done: "Pulled standings" },
  team_trajectory: { running: "Charting team trajectory", done: "Charted team trajectory" },
  team_totals: { running: "Pulling team totals", done: "Pulled team totals" },
  qualified_leaders: { running: "Pulling league leaders", done: "Pulled league leaders" },
  team_splits: { running: "Pulling team splits", done: "Pulled team splits" },
  injury_impact: { running: "Checking injury impact", done: "Checked injury impact" },
  lineup_matchups: { running: "Building lineup matchups", done: "Built lineup matchups" },
  competitive_ratings: { running: "Computing competitive ratings", done: "Computed competitive ratings" },
  injuries: { running: "Checking injuries", done: "Checked injuries" },
  team_shot_zones: { running: "Mapping team shot zones", done: "Mapped team shot zones" },
  player_shot_zones: { running: "Mapping shot zones", done: "Mapped shot zones" },
  rest_splits: { running: "Pulling rest splits", done: "Pulled rest splits" },
  rookie_leaders: { running: "Pulling rookie leaders", done: "Pulled rookie leaders" },
  team_ratings: { running: "Pulling team ratings", done: "Pulled team ratings" },
  shots: { running: "Pulling shot data", done: "Pulled shot data" },
  shooting_efficiency: { running: "Computing shooting efficiency", done: "Computed shooting efficiency" },
  on_off: { running: "Computing on/off numbers", done: "Computed on/off numbers" },
  lineups: { running: "Pulling lineup data", done: "Pulled lineup data" },
  clutch: { running: "Pulling clutch numbers", done: "Pulled clutch numbers" },
  player_ratings: { running: "Pulling player ratings", done: "Pulled player ratings" },
  playoff_team_ratings: { running: "Pulling playoff ratings", done: "Pulled playoff ratings" },
  game_prediction: { running: "Running game prediction", done: "Ran game prediction" },
  four_factors: { running: "Computing four factors", done: "Computed four factors" },
  team_four_factors: { running: "Computing team four factors", done: "Computed team four factors" },
  matchup_brief: { running: "Building matchup brief", done: "Built matchup brief" },
  season_series: { running: "Pulling season series", done: "Pulled season series" },
  head_to_head: { running: "Pulling head-to-head", done: "Pulled head-to-head" },
  matchup_splits: { running: "Pulling matchup splits", done: "Pulled matchup splits" },
  today: { running: "Checking today's games", done: "Checked today's games" },
  morning_briefing: { running: "Building the morning briefing", done: "Built the morning briefing" },
  award_results: { running: "Pulling award results", done: "Pulled award results" },
  player_comparison: { running: "Comparing players", done: "Compared players" },
  sql_exec: { running: "Querying warehouse", done: "Queried warehouse" },
  web_search: { running: "Searching the web", done: "Searched the web" },
  web_fetch: { running: "Reading a web page", done: "Read a web page" },
  tool: { running: "Running a tool", done: "Ran a tool" },
};

export function toolLabelFor(
  name: unknown,
  status: ToolActivityStatus = "running",
): string {
  const key = typeof name === "string" ? name : "";
  const narration = TOOL_LABELS[key] ?? TOOL_LABELS.tool;
  return status === "running" ? narration.running : narration.done;
}

function argumentLine(name: string, value: unknown): string {
  if (typeof value === "string") return `${name}=${value}`;
  return `${name}=${JSON.stringify(value)}`;
}

function publishableArgumentLines(data: unknown): string[] | undefined {
  const call = asRecord(data);
  const declared = Array.isArray(call.arguments) ? call.arguments : [];
  const lines: string[] = [];
  for (const item of declared) {
    const argument = asRecord(item);
    const name = asString(argument.name);
    if (!name) continue;
    lines.push(argumentLine(name, argument.value));
  }
  const unknown = asNumber(call.unknown_argument_count) ?? 0;
  if (unknown > 0) {
    lines.push(`+${unknown} more not shown`);
  }
  return lines.length ? lines : undefined;
}

const NODE_LABELS: Record<string, string> = {
  entry: "Understanding your question",
  data_retrieval: "Planning the analysis",
  tools: "Gathering the numbers",
  analytics: "Checking the numbers",
  presentation: "Writing the answer",
};

export function thinkingLabelFor(node: unknown): string {
  const key = typeof node === "string" ? node : "";
  return NODE_LABELS[key] ?? "Working";
}

const FAILURE_COPY: Record<string, { title: string; body: string }> = {
  timeout: {
    title: "This took too long",
    body: "The analysis ran past the time limit. Try a narrower question or try again.",
  },
  quota: {
    title: "The model is out of quota",
    body: "Dime's model hit its usage limit. Your question is fine — try again in a little while.",
  },
  rate_limited: {
    title: "Too many requests",
    body: "Slow down a touch and try again in a minute.",
  },
  execution_failure: {
    title: "Some data was unavailable",
    body: "Dime couldn't pull everything this question needed. Try again or narrow the question.",
  },
  provider_error: {
    title: "The analyst is down",
    body: "Dime's model provider didn't respond. Nothing is wrong with your question — try again shortly.",
  },
  connection: {
    title: "Couldn't reach Dime",
    body: "The connection to the backend dropped. Check your connection and try again.",
  },
  startup: {
    title: "Couldn't start this run",
    body: "Dime couldn't start the analysis. Try again in a moment.",
  },
};

export function failureCopy(kind: string): { title: string; body: string } {
  return (
    FAILURE_COPY[kind] ?? {
      title: "Something went wrong",
      body: "Dime hit an unexpected problem. Try again in a moment.",
    }
  );
}

interface EvidenceRow {
  metric: string;
  subject: string;
  value: number | null;
  unit: string;
  provenance: DimeProvenance;
}

function safeSourceUrl(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return /^https?:\/\/\S+$/i.test(trimmed) ? trimmed : null;
}

const LIVE_SOURCE_IDS = new Set(["nba_api", "basketball_reference", "espn"]);

function validSourceId(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return LIVE_SOURCE_IDS.has(trimmed) ? trimmed : null;
}

function trimmedString(raw: unknown): string | undefined {
  if (typeof raw !== "string") return undefined;
  const trimmed = raw.trim();
  return trimmed ? trimmed : undefined;
}

function compactProvenance(fields: DimeProvenance): DimeProvenance {
  const provenance: DimeProvenance = {
    origin: fields.origin,
    liveSources: fields.liveSources,
  };
  if (fields.capability) provenance.capability = fields.capability;
  if (fields.warehouseId) provenance.warehouseId = fields.warehouseId;
  if (fields.season) provenance.season = fields.season;
  if (fields.asOf) provenance.asOf = fields.asOf;
  if (fields.liveSourceIds && fields.liveSourceIds.length > 0) {
    provenance.liveSourceIds = fields.liveSourceIds;
  }
  return provenance;
}

export function undeclaredProvenance(): DimeProvenance {
  return { origin: "undeclared", liveSources: [] };
}

function originFromParts(
  live: boolean,
  warehouse: boolean,
  unknown: boolean,
): ProvenanceOrigin {
  if (live && warehouse) return "mixed";
  if ((live || warehouse) && unknown) return "partly-undeclared";
  if (live) return "live";
  if (warehouse) return "warehouse";
  return "undeclared";
}

function originParts(
  origin: ProvenanceOrigin | undefined,
): { live: boolean; warehouse: boolean } {
  if (origin === "live") return { live: true, warehouse: false };
  if (origin === "warehouse") return { live: false, warehouse: true };
  if (origin === "mixed") return { live: true, warehouse: true };
  return { live: false, warehouse: false };
}

export function parseProvenance(raw: unknown): DimeProvenance {
  const record = asRecord(raw);
  const warehouseId = trimmedString(record.warehouse_id);
  const rawSources = Array.isArray(record.live_sources) ? record.live_sources : [];
  const liveSources = [...new Set(
    rawSources
      .map(safeSourceUrl)
      .filter((url): url is string => url !== null),
  )];
  const liveSourceIds = [...new Set(
    rawSources
      .map(validSourceId)
      .filter((id): id is string => id !== null),
  )];
  const producer = record.origin;
  const declaresMixed = producer === "mixed";
  const hasLive = liveSources.length > 0 || liveSourceIds.length > 0;
  const live = producer === "live" || (declaresMixed && hasLive);
  const warehouse =
    (producer === "warehouse" || declaresMixed) && warehouseId !== undefined;
  return compactProvenance({
    origin: originFromParts(live, warehouse, declaresMixed && !(live && warehouse)),
    capability: trimmedString(record.capability),
    warehouseId,
    season: trimmedString(record.season),
    asOf: trimmedString(record.as_of),
    liveSources,
    liveSourceIds,
  });
}

function agreedValue(values: (string | undefined)[]): string | undefined {
  const [first, ...rest] = values;
  if (first === undefined) return undefined;
  return rest.every((value) => value === first) ? first : undefined;
}

function readableProvenance(raw: unknown): DimeProvenance | null {
  const record = asRecord(raw);
  const origin = trimmedString(record.origin);
  if (origin === undefined || !Array.isArray(record.liveSources)) return null;
  return raw as DimeProvenance;
}

function coalescedEvidence(
  entries: (DimeProvenance | undefined)[],
): ProvenanceEvidence[] | undefined {
  let nested = false;
  const collected: ProvenanceEvidence[] = [];
  for (const entry of entries) {
    const evidence = entry?.evidence;
    if (!Array.isArray(evidence) || evidence.length === 0) continue;
    nested = true;
    for (const item of evidence) {
      const provenance = readableProvenance(item?.provenance);
      const label = trimmedString(item?.label);
      if (label === undefined || provenance === null) return undefined;
      collected.push({ label, provenance });
    }
  }
  if (!nested) return undefined;
  const unique: ProvenanceEvidence[] = [];
  const seen = new Set<string>();
  for (const item of collected) {
    const key = `${item.label}\u0000${JSON.stringify(item.provenance)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(item);
  }
  return unique.length ? unique : undefined;
}

export function mergeProvenance(
  entries: (DimeProvenance | undefined)[],
): DimeProvenance {
  let live = false;
  let warehouse = false;
  let unknown = false;
  for (const entry of entries) {
    const parts = originParts(entry?.origin);
    live ||= parts.live;
    warehouse ||= parts.warehouse;
    unknown ||= !parts.live && !parts.warehouse;
  }
  const merged = compactProvenance({
    origin: originFromParts(live, warehouse, unknown),
    capability: agreedValue(entries.map((entry) => entry?.capability)),
    warehouseId: agreedValue(entries.map((entry) => entry?.warehouseId)),
    season: agreedValue(entries.map((entry) => entry?.season)),
    asOf: agreedValue(entries.map((entry) => entry?.asOf)),
    liveSources: [
      ...new Set(entries.flatMap((entry) => entry?.liveSources ?? [])),
    ],
    liveSourceIds: [
      ...new Set(entries.flatMap((entry) => entry?.liveSourceIds ?? [])),
    ],
  });
  const evidence = coalescedEvidence(entries);
  if (evidence) merged.evidence = evidence;
  return merged;
}

export function mergeArtifactProvenance(
  artifacts: DimeArtifact[],
): DimeProvenance | undefined {
  if (artifacts.length === 0) return undefined;
  return mergeProvenance(
    artifacts.map((artifact) => artifact.provenance ?? undeclaredProvenance()),
  );
}

export function originPhrase(
  provenance: DimeProvenance | undefined,
): string {
  if (!provenance) return "not declared";
  if (provenance.origin === "warehouse") {
    return provenance.warehouseId
      ? `declared warehouse ${provenance.warehouseId}`
      : "declared warehouse";
  }
  if (provenance.origin === "live") return "live source";
  if (provenance.origin === "mixed") return "mixed live and warehouse sources";
  if (provenance.origin === "partly-undeclared") return "mixed sources, partly undeclared";
  return "not declared";
}

export function provenanceSource(
  provenance: DimeProvenance | undefined,
): string | undefined {
  if (!provenance) return undefined;
  if (provenance.origin === "warehouse") {
    return provenance.warehouseId
      ? `dime warehouse · ${provenance.warehouseId}`
      : "dime warehouse";
  }
  if (provenance.origin === "live") return "live sources";
  if (provenance.origin === "mixed") return "mixed sources";
  if (provenance.origin === "partly-undeclared") return "mixed sources, partly undeclared";
  return "source not declared";
}

function parseGap(raw: unknown): EvidenceGapNote | null {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return null;
  const record = raw as Record<string, unknown>;
  const kind = trimmedString(record.kind);
  if (kind === undefined) return null;
  const rawBlocks = record.blocks;
  if (rawBlocks === undefined) return { kind, blocks: [] };
  if (!Array.isArray(rawBlocks)) return null;
  const blocks: string[] = [];
  for (const item of rawBlocks) {
    const block = trimmedString(item);
    if (block === undefined) return null;
    blocks.push(block);
  }
  return { kind, blocks };
}

function checkedClaimCount(raw: unknown): number | null {
  const claims = asNumber(raw);
  return claims !== undefined && Number.isInteger(claims) && claims >= 0 ? claims : null;
}

export function parseCarry(raw: unknown): VerificationCarry | null {
  if (raw === null || raw === undefined) return null;
  const record = asRecord(raw);
  const verification: VerificationStatus =
    record.verification === "pass" || record.verification === "partial"
      ? record.verification
      : "unknown";
  const verifiedClaims = checkedClaimCount(record.verified_claims);
  const rawGaps = record.gaps;
  const parsedGaps = Array.isArray(rawGaps) ? rawGaps.map(parseGap) : [];
  const gaps = parsedGaps.filter((gap): gap is EvidenceGapNote => gap !== null);
  const gapsReadable = Array.isArray(rawGaps) && gaps.length === rawGaps.length;
  const runId = trimmedString(record.run_id);
  if (verification === "unknown" && verifiedClaims === null && !runId && gaps.length === 0) {
    return null;
  }
  const carry: VerificationCarry = { verification, verifiedClaims, gaps, gapsReadable };
  if (runId) carry.runId = runId;
  return carry;
}

function originSentence(provenance: DimeProvenance | undefined): string {
  return `Origin: ${originPhrase(provenance)}.`;
}

function unverifiedReason(carry: VerificationCarry): string {
  if (carry.verification === "unknown") {
    return "This run did not report a verification status.";
  }
  if (!carry.gapsReadable) {
    return "The run reported a pass, but its gap report could not be read.";
  }
  if (carry.verifiedClaims === null) {
    return "The run reported a pass, but not how many claims it checked.";
  }
  return "The run reported a pass, but these numbers are not all from a declared warehouse source.";
}

export function verificationDisclosure(
  carry: VerificationCarry | null,
  provenance: DimeProvenance | undefined,
): VerificationDisclosure {
  const origin = originSentence(provenance);
  if (!carry) {
    return {
      state: "unknown",
      headline: "Verification unknown",
      detail: `This run did not report whether its numbers were checked. ${origin}`,
      gaps: [],
    };
  }
  const claims = carry.verifiedClaims;
  const claimText =
    claims === null
      ? "verified claim count not reported"
      : `${claims} verified claim${claims === 1 ? "" : "s"}`;
  const gapCount = carry.gaps.length;
  const unreadableText = carry.gapsReadable ? "" : " The run's gap report could not be read.";
  const gapText = gapCount
    ? ` ${gapCount} gap${gapCount === 1 ? "" : "s"} reported.${unreadableText}`
    : unreadableText;
  const passReported =
    carry.verification === "pass" &&
    claims !== null &&
    claims > 0 &&
    carry.gapsReadable &&
    gapCount === 0;
  if (passReported && provenance?.origin === "warehouse") {
    const where = provenance.warehouseId
      ? `declared warehouse ${provenance.warehouseId}`
      : "declared warehouse";
    return {
      state: "verified",
      headline: "Verified",
      detail: `${claimText} from the ${where}.`,
      gaps: carry.gaps,
    };
  }
  if (carry.verification === "partial" || claims === 0 || gapCount > 0) {
    return {
      state: "partial",
      headline: claims === 0 ? "No verified claims" : "Verification partial",
      detail: `${claimText}.${gapText} ${origin}`,
      gaps: carry.gaps,
    };
  }
  return {
    state: "unverified",
    headline: "Not verified",
    detail: `${unverifiedReason(carry)} This answer is not shown as verified. ${origin}`,
    gaps: carry.gaps,
  };
}

function asEvidenceRows(tables: unknown): EvidenceRow[] {
  if (!Array.isArray(tables)) return [];
  const rows: EvidenceRow[] = [];
  for (const item of tables) {
    if (typeof item !== "object" || item === null) continue;
    const row = item as Record<string, unknown>;
    const metric =
      typeof row.display_name === "string" && row.display_name
        ? row.display_name
        : typeof row.output_id === "string"
          ? row.output_id
          : "";
    if (!metric) continue;
    const subject =
      typeof row.subject_display_name === "string" && row.subject_display_name
        ? row.subject_display_name
        : "League";
    const raw = row.value;
    const value =
      typeof raw === "number" && Number.isFinite(raw)
        ? raw
        : typeof raw === "string" && raw.trim() !== "" && Number.isFinite(Number(raw))
          ? Number(raw)
          : null;
    const unit = typeof row.unit === "string" && row.unit !== "unitless" ? row.unit : "";
    rows.push({ metric, subject, value, unit, provenance: parseProvenance(row.provenance) });
  }
  return rows;
}

function formatMetricValue(value: number): string | number {
  return Number.isInteger(value) ? value : Math.round(value * 10) / 10;
}

const RESOLVED_CHART_KINDS = new Set(["chart"]);

function asResolvedArtifacts(raw: unknown): DimeArtifact[] {
  if (!Array.isArray(raw)) return [];
  const artifacts: DimeArtifact[] = [];
  for (const item of raw) {
    if (typeof item !== "object" || item === null) continue;
    const entry = item as Record<string, unknown>;
    const kind = typeof entry.kind === "string" ? entry.kind : "";
    if (!RESOLVED_CHART_KINDS.has(kind)) continue;
    const title = typeof entry.title === "string" ? entry.title : "";
    if (!title) continue;
    const series: { name: string; values: number[] }[] = [];
    for (const line of Array.isArray(entry.series) ? entry.series : []) {
      if (typeof line !== "object" || line === null) continue;
      const record = line as Record<string, unknown>;
      const name = typeof record.name === "string" ? record.name : "";
      const values = (Array.isArray(record.values) ? record.values : [])
        .filter((value): value is number =>
          typeof value === "number" && Number.isFinite(value));
      if (name && values.length > 0) series.push({ name, values });
    }
    if (series.length === 0) continue;
    const provenance =
      entry.provenance === undefined || entry.provenance === null
        ? undefined
        : parseProvenance(entry.provenance);
    artifacts.push({
      kind: "chart",
      title,
      series,
      source: provenanceSource(provenance),
      provenance,
      footnote:
        typeof entry.footnote === "string" && entry.footnote
          ? entry.footnote
          : undefined,
    });
  }
  return artifacts;
}

function evidenceProvenance(rows: EvidenceRow[]): DimeProvenance {
  const summary = mergeProvenance(rows.map((row) => row.provenance));
  if (rows.length < 2) return summary;
  return {
    ...summary,
    evidence: rows.map((row) => ({
      label: `${row.subject} · ${row.metric}`,
      provenance: row.provenance,
    })),
  };
}

export function deriveArtifacts(tables: unknown): DimeArtifact[] {
  const rows = asEvidenceRows(tables);
  if (!rows.length) return [];
  const artifacts: DimeArtifact[] = [];
  const byMetric = new Map<string, EvidenceRow[]>();
  for (const row of rows) {
    const group = byMetric.get(row.metric) ?? [];
    group.push(row);
    byMetric.set(row.metric, group);
  }
  const subjects = [...new Set(rows.map((r) => r.subject))];
  const sharedMetrics = [...byMetric.entries()].filter(
    ([, group]) =>
      subjects.length === 2 &&
      group.length === 2 &&
      group[0].subject !== group[1].subject &&
      group.every((r) => r.value !== null),
  );
  if (subjects.length === 2 && sharedMetrics.length > 0) {
    const [aName, bName] = subjects;
    const compared = sharedMetrics.flatMap(([, group]) => group);
    const provenance = evidenceProvenance(compared);
    artifacts.push({
      kind: "compare",
      title: "Head-to-head",
      source: provenanceSource(provenance),
      provenance,
      aName,
      bName,
      rows: sharedMetrics.map(([metric, group]) => {
        const aRow = group.find((r) => r.subject === aName) ?? group[0];
        const bRow = group.find((r) => r.subject === bName) ?? group[1];
        return {
          label: metric,
          a: aRow.value as number,
          b: bRow.value as number,
        };
      }),
    });
  }
  const compared = new Set(sharedMetrics.map(([metric]) => metric));
  const tableRows = rows.filter((r) => !compared.has(r.metric));
  if (tableRows.length > 0) {
    const provenance = evidenceProvenance(tableRows);
    artifacts.push({
      kind: "table",
      title: "Evidence",
      source: provenanceSource(provenance),
      provenance,
      columns: [
        { key: "metric", label: "Metric" },
        { key: "subject", label: "Subject" },
        { key: "value", label: "Value", numeric: true },
        { key: "unit", label: "Unit" },
      ],
      rows: tableRows.map((r) => [
        r.metric,
        r.subject,
        r.value === null ? "—" : formatMetricValue(r.value),
        r.unit,
      ]),
    });
  }
  return artifacts;
}

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
}

function emptySnapshot(): StreamSnapshot {
  return {
    text: "",
    thinking: [],
    tools: [],
    artifacts: [],
    suggestions: [],
    carry: null,
    failed: null,
    done: false,
  };
}

const MAX_THINKING_ROWS = 12;
const MAX_TOOLS = 24;

function asRecord(data: unknown): Record<string, unknown> {
  return typeof data === "object" && data !== null
    ? (data as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function reduceBackendEvent(type: string, data: unknown): DimeStreamEvent[] {
  const d = asRecord(data);
  switch (type) {
    case "token": {
      const text = asString(d.text);
      return text ? [{ type: "text_delta", text }] : [];
    }
    case "status": {
      const label = asString(d.text);
      return label ? [{ type: "thinking", label }] : [];
    }
    case "thought_stream": {
      return [{ type: "thinking", label: thinkingLabelFor(d.node) }];
    }
    case "node_update": {
      if (d.status !== "running") return [];
      return [{ type: "thinking", label: thinkingLabelFor(d.node) }];
    }
    case "tool_call": {
      const name = asString(d.name) || "tool";
      return [
        {
          type: "tool_activity",
          id: asString(d.event_id) || null,
          name,
          label: toolLabelFor(name, "running"),
          status: "running",
          args: publishableArgumentLines(d.data),
        },
      ];
    }
    case "tool_result": {
      const name = asString(d.name) || "tool";
      const status: ToolActivityStatus = d.status === "fail" ? "fail" : "ok";
      return [
        {
          type: "tool_activity",
          id: asString(d.event_id) || null,
          name,
          label: toolLabelFor(name, status),
          status,
          rows: asNumber(d.rows),
          ms: asNumber(d.ms),
          error: status === "fail" ? asString(d.error) || "Tool failed" : undefined,
        },
      ];
    }
    case "custom_data": {
      const derived = deriveArtifacts(d.tables);
      const resolved = asResolvedArtifacts(d.artifacts);
      return [...derived, ...resolved].map((artifact) => ({
        type: "artifact",
        artifact,
      }));
    }
    case "final_answer": {
      return [{ type: "final", text: asString(d.text), carry: parseCarry(d.carry) }];
    }
    case "failure": {
      const kind = asString(d.kind) || "execution_failure";
      return [
        {
          type: "failure",
          kind,
          message: asString(d.message) || failureCopy(kind).body,
        },
      ];
    }
    case "error": {
      const message = asString(d.message);
      const kind = /rate limit/i.test(message) ? "rate_limited" : "execution_failure";
      return [{ type: "failure", kind, message: message || failureCopy(kind).body }];
    }
    default:
      return [];
  }
}

type FailureAuthority = "typed" | "fallback";

function failureAuthorityFor(type: string): FailureAuthority | null {
  if (type === "failure") return "typed";
  if (type === "error") return "fallback";
  return null;
}

export class DimeStream {
  private snap = emptySnapshot();
  private seq = 0;
  private hasTypedFailure = false;

  snapshot(): StreamSnapshot {
    return {
      ...this.snap,
      thinking: [...this.snap.thinking],
      tools: this.snap.tools.map((t) => ({ ...t })),
      artifacts: [...this.snap.artifacts],
      suggestions: [...this.snap.suggestions],
      carry: this.snap.carry ? { ...this.snap.carry } : null,
      failed: this.snap.failed ? { ...this.snap.failed } : null,
    };
  }

  handle(type: string, data: unknown): void {
    const authority = failureAuthorityFor(type);
    for (const event of reduceBackendEvent(type, data)) {
      this.apply(event, authority);
    }
    if (type === "suggestions") {
      const items = asRecord(data).items;
      if (Array.isArray(items)) {
        this.snap.suggestions = items
          .filter((item): item is string => typeof item === "string" && item.trim() !== "")
          .slice(0, 8);
      }
    }
  }

  finish(): void {
    this.snap.done = true;
  }

  fail(kind: string, message: string): void {
    this.recordFailure({ type: "failure", kind, message }, "fallback");
  }

  private recordFailure(
    event: FailureEvent,
    authority: FailureAuthority | null,
  ): void {
    if (authority === "typed") {
      this.hasTypedFailure = true;
    } else if (this.hasTypedFailure) {
      return;
    }
    this.snap.failed = { kind: event.kind, message: event.message };
  }

  private apply(
    event: DimeStreamEvent,
    authority: FailureAuthority | null,
  ): void {
    switch (event.type) {
      case "text_delta":
        this.snap.text += event.text;
        break;
      case "thinking": {
        const last = this.snap.thinking[this.snap.thinking.length - 1];
        if (!last || last.label !== event.label) {
          this.snap.thinking = [
            ...this.snap.thinking,
            { label: event.label, detail: event.detail },
          ].slice(-MAX_THINKING_ROWS);
        }
        break;
      }
      case "tool_activity": {
        const tools = this.snap.tools;
        let idx =
          event.id !== null ? tools.findIndex((t) => t.key === event.id) : -1;
        if (idx < 0 && event.id === null && event.status !== "running") {
          for (let i = tools.length - 1; i >= 0; i -= 1) {
            if (tools[i].status === "running" && tools[i].name === event.name) {
              idx = i;
              break;
            }
          }
        }
        if (idx >= 0) {
          const next = [...tools];
          next[idx] = {
            ...next[idx],
            label: event.label,
            status: event.status,
            rows: event.rows ?? next[idx].rows,
            ms: event.ms ?? next[idx].ms,
            args: event.args ?? next[idx].args,
            error: event.error ?? next[idx].error,
          };
          this.snap.tools = next;
        } else if (event.status === "running") {
          this.seq += 1;
          this.snap.tools = [
            ...tools,
            {
              key: event.id ?? `local:${this.seq}`,
              name: event.name,
              label: event.label,
              status: event.status,
              rows: event.rows,
              ms: event.ms,
              args: event.args,
              error: event.error,
            },
          ].slice(-MAX_TOOLS);
        } else {
          this.seq += 1;
          this.snap.tools = [
            ...tools,
            {
              key: event.id ?? `local:${this.seq}`,
              name: event.name,
              label: event.label,
              status: event.status,
              rows: event.rows,
              ms: event.ms,
              args: event.args,
              error: event.error,
            },
          ].slice(-MAX_TOOLS);
        }
        break;
      }
      case "artifact":
        this.snap.artifacts = [...this.snap.artifacts, event.artifact];
        break;
      case "final":
        this.snap.text = event.text;
        this.snap.carry = event.carry;
        break;
      case "failure":
        this.recordFailure(event, authority);
        break;
    }
  }
}

export interface DimeStreamCallbacks {
  onUpdate: (snap: StreamSnapshot) => void;
  onDone: (snap: StreamSnapshot) => void;
  onError: (snap: StreamSnapshot, message: string) => void;
}

export function streamDimeChat(
  q: string,
  callbacks: DimeStreamCallbacks,
  opts?: { signal?: AbortSignal; model?: string | null },
): void {
  const stream = new DimeStream();
  let settled = false;
  const emit = () => callbacks.onUpdate(stream.snapshot());
  void postChatStream(
    q,
    opts?.model ?? null,
    {
      onEvent: (type, data) => {
        if (settled) return;
        stream.handle(type, data);
        emit();
      },
      onDone: () => {
        if (settled) return;
        settled = true;
        stream.finish();
        callbacks.onDone(stream.snapshot());
      },
      onError: (message) => {
        if (settled) return;
        settled = true;
        stream.fail("connection", message);
        stream.finish();
        const snap = stream.snapshot();
        callbacks.onError(snap, message);
      },
    },
    opts?.signal,
    null,
  );
}

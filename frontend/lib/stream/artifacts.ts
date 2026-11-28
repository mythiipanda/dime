import { mergeProvenance, parseProvenance, provenanceSource } from "./provenance";
import type {
  ChartArtifactPayload,
  ChartSeriesPayload,
  ChartTone,
  CompareArtifactPayload,
  DimeArtifact,
  DimeProvenance,
  MemoAnchor,
  MemoArtifactPayload,
  TradeVerdictArtifactPayload,
  CapSummaryArtifactPayload,
  TradeVerdictTeamPayload,
  MemoSectionPayload,
  PlayerCardArtifactPayload,
  PlayerCardSectionPayload,
  TeamCardArtifactPayload,
  ScatterArtifactPayload,
  ShotChartArtifactPayload,
  TableArtifactPayload,
} from "./types";

interface EvidenceRow {
  metric: string;
  subject: string;
  value: number | null;
  unit: string;
  provenance: DimeProvenance;
}

const VALID_CHART_TONES: ReadonlySet<ChartTone> = new Set([
  "ink",
  "muted",
  "accent",
  "good",
  "warn",
]);

function finiteNumber(raw: unknown): number | undefined {
  return typeof raw === "number" && Number.isFinite(raw) ? raw : undefined;
}

function parseChartTone(raw: unknown): ChartTone | undefined {
  return typeof raw === "string" && VALID_CHART_TONES.has(raw as ChartTone)
    ? (raw as ChartTone)
    : undefined;
}

function parseChartSeries(raw: unknown): ChartSeriesPayload[] {
  const series: ChartSeriesPayload[] = [];
  for (const line of Array.isArray(raw) ? raw : []) {
    if (typeof line !== "object" || line === null) continue;
    const record = line as Record<string, unknown>;
    const name = typeof record.name === "string" ? record.name : "";
    const tone = parseChartTone(record.tone);
    const values = (Array.isArray(record.values) ? record.values : [])
      .map(value => finiteNumber(value) ?? null);
    if (name && values.some(value => value !== null)) {
      series.push({ name, values, ...(tone ? { tone } : {}) });
    }
  }
  return series;
}

function resolveChart(
  entry: Record<string, unknown>,
  title: string,
  provenance: DimeProvenance | undefined,
): ChartArtifactPayload | null {
  const series = parseChartSeries(entry.series);
  if (series.length === 0) return null;
  const unit = typeof entry.unit === "string" ? entry.unit : undefined;
  const xLabels = Array.isArray(entry.xLabels)
    ? entry.xLabels.map((lbl) => typeof lbl === "string" || finiteNumber(lbl) !== undefined ? String(lbl) : "")
    : undefined;
  const footnote =
    typeof entry.footnote === "string" && entry.footnote ? entry.footnote : undefined;
  const textField = (key: string) =>
    typeof entry[key] === "string" && entry[key] ? (entry[key] as string) : undefined;
  const marks = (Array.isArray(entry.marks) ? entry.marks : [])
    .map((raw) => {
      const m = raw as Record<string, unknown>;
      const value = finiteNumber(m?.value);
      const label = typeof m?.label === "string" ? m.label : "";
      return value !== undefined && label ? { value, label } : null;
    })
    .filter((m): m is { value: number; label: string } => m !== null);
  const annotations = (Array.isArray(entry.annotations) ? entry.annotations : [])
    .map((raw) => {
      const a = raw as Record<string, unknown>;
      const index = finiteNumber(a?.index);
      const text = typeof a?.text === "string" ? a.text : "";
      return index !== undefined && Number.isInteger(index) && index >= 0 && text
        ? { index, text }
        : null;
    })
    .filter((a): a is { index: number; text: string } => a !== null);
  const variant = entry.variant === "bar" ? "bar" : entry.variant === "line" ? "line" : undefined;
  return {
    kind: "chart",
    title,
    series,
    source: provenanceSource(provenance),
    provenance,
    footnote,
    ...(unit !== undefined ? { unit } : {}),
    ...(xLabels && xLabels.length > 0 ? { xLabels } : {}),
    ...(textField("subtitle") ? { subtitle: textField("subtitle") } : {}),
    ...(textField("xLabel") ? { xLabel: textField("xLabel") } : {}),
    ...(textField("yLabel") ? { yLabel: textField("yLabel") } : {}),
    ...(variant ? { variant } : {}),
    ...(marks.length ? { marks } : {}),
    ...(annotations.length ? { annotations } : {}),
    ...(entry.labelValues === true ? { labelValues: true } : {}),
  };
}

function parseShotZone(
  line: unknown,
): { x: number; y: number; att: number; pct: number; label?: string; makes?: number; delta?: number } | null {
  if (typeof line !== "object" || line === null) return null;
  const z = line as Record<string, unknown>;
  const x = finiteNumber(z.x);
  const y = finiteNumber(z.y);
  const att = finiteNumber(z.att);
  const pct = finiteNumber(z.pct);
  if (x === undefined || y === undefined || att === undefined || pct === undefined) {
    return null;
  }
  const parsed: { x: number; y: number; att: number; pct: number; label?: string; makes?: number; delta?: number } = { x, y, att, pct };
  if (typeof z.label === "string" && z.label) parsed.label = z.label;
  const makes = finiteNumber(z.makes);
  if (makes !== undefined) parsed.makes = makes;
  const delta = finiteNumber(z.delta);
  if (delta !== undefined) parsed.delta = delta;
  return parsed;
}

function resolveShotChart(
  entry: Record<string, unknown>,
  title: string,
  provenance: DimeProvenance | undefined,
): ShotChartArtifactPayload {
  const zones: { x: number; y: number; att: number; pct: number; label?: string; makes?: number; delta?: number }[] = [];
  for (const line of Array.isArray(entry.zones) ? entry.zones : []) {
    const parsed = parseShotZone(line);
    if (parsed) zones.push(parsed);
  }
  return {
    kind: "shot_chart",
    title,
    zones,
    source: provenanceSource(provenance),
    provenance,
    footnote:
      typeof entry.footnote === "string" && entry.footnote ? entry.footnote : undefined,
  };
}

function parseTableColumns(
  raw: unknown,
): { key: string; label: string; numeric?: boolean }[] {
  const columns: { key: string; label: string; numeric?: boolean }[] = [];
  for (const col of Array.isArray(raw) ? raw : []) {
    if (typeof col !== "object" || col === null) continue;
    const c = col as Record<string, unknown>;
    const key = typeof c.key === "string" ? c.key : "";
    if (!key) continue;
    const label = typeof c.label === "string" ? c.label : key;
    const numeric = typeof c.numeric === "boolean" ? c.numeric : undefined;
    columns.push({ key, label, ...(numeric !== undefined ? { numeric } : {}) });
  }
  return columns;
}

function tableCell(val: unknown): string | number {
  return finiteNumber(val) !== undefined ? (val as number) : String(val ?? "");
}

function parseTableRows(
  raw: unknown,
  columns: { key: string; label: string; numeric?: boolean }[],
): (string | number)[][] {
  const rows: (string | number)[][] = [];
  for (const row of Array.isArray(raw) ? raw : []) {
    if (Array.isArray(row)) {
      rows.push(row.map(tableCell));
    } else if (typeof row === "object" && row !== null) {
      const r = row as Record<string, unknown>;
      rows.push(columns.map((col) => tableCell(r[col.key])));
    }
  }
  return rows;
}

function resolveTable(
  entry: Record<string, unknown>,
  title: string,
  provenance: DimeProvenance | undefined,
): TableArtifactPayload | null {
  const columns = parseTableColumns(entry.columns);
  const rows = parseTableRows(entry.rows, columns);
  if (columns.length === 0 || rows.length === 0) return null;
  const footnote =
    typeof entry.footnote === "string" && entry.footnote ? entry.footnote : undefined;
  return {
    kind: "table",
    title,
    columns,
    rows,
    source: provenanceSource(provenance),
    provenance,
    ...(footnote ? { footnote } : {}),
  };
}

function resolveCompare(
  entry: Record<string, unknown>,
  title: string,
  provenance: DimeProvenance | undefined,
): CompareArtifactPayload | null {
  const aName = typeof entry.aName === "string" ? entry.aName : "Player A";
  const bName = typeof entry.bName === "string" ? entry.bName : "Player B";
  const rows: { label: string; a: number; b: number }[] = [];
  for (const line of Array.isArray(entry.rows) ? entry.rows : []) {
    if (typeof line !== "object" || line === null) continue;
    const r = line as Record<string, unknown>;
    const label = typeof r.label === "string" ? r.label : "";
    if (!label) continue;
    rows.push({
      label,
      a: finiteNumber(r.a) ?? 0,
      b: finiteNumber(r.b) ?? 0,
    });
  }
  if (rows.length === 0) return null;
  return {
    kind: "compare",
    title,
    aName,
    bName,
    rows,
    source: provenanceSource(provenance),
    provenance,
  };
}

function parseScatterPoint(
  line: unknown,
): { label: string; x: number; y: number; highlight?: boolean } | null {
  if (typeof line !== "object" || line === null) return null;
  const p = line as Record<string, unknown>;
  const label = typeof p.label === "string" ? p.label : "";
  const x = finiteNumber(p.x);
  const y = finiteNumber(p.y);
  if (!label || x === undefined || y === undefined) return null;
  const highlight = typeof p.highlight === "boolean" ? p.highlight : undefined;
  return { label, x, y, ...(highlight !== undefined ? { highlight } : {}) };
}

function resolveScatter(
  entry: Record<string, unknown>,
  title: string,
  provenance: DimeProvenance | undefined,
): ScatterArtifactPayload | null {
  const xLabel = typeof entry.xLabel === "string" ? entry.xLabel : "";
  const yLabel = typeof entry.yLabel === "string" ? entry.yLabel : "";
  const xMid = finiteNumber(entry.xMid);
  const yMid = finiteNumber(entry.yMid);
  const footnote =
    typeof entry.footnote === "string" && entry.footnote ? entry.footnote : undefined;
  const points: { label: string; x: number; y: number; highlight?: boolean }[] = [];
  for (const line of Array.isArray(entry.points) ? entry.points : []) {
    const parsed = parseScatterPoint(line);
    if (parsed) points.push(parsed);
  }
  if (points.length === 0) return null;
  return {
    kind: "scatter",
    title,
    xLabel,
    yLabel,
    points,
    ...(xMid !== undefined ? { xMid } : {}),
    ...(yMid !== undefined ? { yMid } : {}),
    ...(footnote ? { footnote } : {}),
    source: provenanceSource(provenance),
    provenance,
  };
}

type ArtifactResolver = (
  entry: Record<string, unknown>,
  title: string,
  provenance: DimeProvenance | undefined,
) => DimeArtifact | null;

type CardMetric = { column: string; label: string; value: number | null; unit?: string };

function parseCardMetric(raw: unknown): CardMetric | null {
  if (!raw || typeof raw !== "object") return null;
  const metric = raw as Record<string, unknown>;
  if (typeof metric.column !== "string" || !metric.column || typeof metric.label !== "string" || !metric.label ||
      (metric.value !== null && finiteNumber(metric.value) === undefined)) return null;
  return { column: metric.column, label: metric.label, value: metric.value as number | null,
    ...(typeof metric.unit === "string" ? { unit: metric.unit } : {}) };
}

function parseCardSections(raw: unknown): PlayerCardSectionPayload[] | undefined | null {
  if (raw === undefined) return undefined;
  if (!Array.isArray(raw) || raw.length === 0 || raw.length > 6) return null;
  const sections: PlayerCardSectionPayload[] = [];
  for (const rawSection of raw) {
    if (!rawSection || typeof rawSection !== "object") return null;
    const section = rawSection as Record<string, unknown>;
    if (typeof section.label !== "string" || !section.label ||
        typeof section.sourceRef !== "string" || !section.sourceRef ||
        typeof section.sourceRow !== "number" || !Number.isInteger(section.sourceRow) || section.sourceRow < 0 ||
        (section.metrics === undefined && section.fields === undefined)) return null;
    const resolved: PlayerCardSectionPayload = { label: section.label, sourceRef: section.sourceRef, sourceRow: section.sourceRow };
    if (section.metrics !== undefined) {
      if (!Array.isArray(section.metrics) || section.metrics.length === 0 || section.metrics.length > 6) return null;
      resolved.metrics = [];
      for (const rawMetric of section.metrics) {
        const metric = parseCardMetric(rawMetric);
        if (!metric) return null;
        resolved.metrics.push(metric);
      }
    }
    if (section.fields !== undefined) {
      if (!Array.isArray(section.fields) || section.fields.length === 0 || section.fields.length > 6) return null;
      resolved.fields = [];
      for (const rawField of section.fields) {
        if (!rawField || typeof rawField !== "object") return null;
        const item = rawField as Record<string, unknown>;
        if (typeof item.column !== "string" || !item.column || typeof item.label !== "string" || !item.label ||
            (item.value !== null && typeof item.value !== "string")) return null;
        resolved.fields.push({ column: item.column, label: item.label, value: item.value as string | null });
      }
    }
    if (typeof section.provenance === "object" && section.provenance !== null)
      resolved.provenance = section.provenance as DimeProvenance;
    sections.push(resolved);
  }
  return sections;
}

function resolvePlayerCard(entry: Record<string, unknown>, title: string, provenance: DimeProvenance | undefined): PlayerCardArtifactPayload | null {
  if (typeof entry.playerName !== "string" || !entry.playerName.trim() ||
      typeof entry.sourceRef !== "string" || !entry.sourceRef ||
      typeof entry.sourceRow !== "number" || !Number.isInteger(entry.sourceRow) || entry.sourceRow < 0 ||
      typeof entry.nameColumn !== "string" || !entry.nameColumn ||
      !Array.isArray(entry.metrics) || entry.metrics.length === 0 || entry.metrics.length > 6) return null;
  const metrics: CardMetric[] = [];
  for (const raw of entry.metrics) {
    const metric = parseCardMetric(raw);
    if (!metric) return null;
    metrics.push(metric);
  }
  const sections = parseCardSections(entry.sections);
  if (sections === null) return null;
  return { kind: "player_card", title, playerName: entry.playerName,
    ...(typeof entry.team === "string" ? { team: entry.team } : {}),
    sourceRef: entry.sourceRef, sourceRow: entry.sourceRow, nameColumn: entry.nameColumn,
    ...(typeof entry.teamColumn === "string" ? { teamColumn: entry.teamColumn } : {}),
    metrics, ...(sections ? { sections } : {}),
    source: provenanceSource(provenance), provenance };
}

function resolveTeamCard(entry: Record<string, unknown>, title: string, provenance: DimeProvenance | undefined): TeamCardArtifactPayload | null {
  if (typeof entry.teamName !== "string" || !entry.teamName.trim() ||
      typeof entry.sourceRef !== "string" || !entry.sourceRef ||
      typeof entry.sourceRow !== "number" || !Number.isInteger(entry.sourceRow) || entry.sourceRow < 0 ||
      typeof entry.nameColumn !== "string" || !entry.nameColumn ||
      !Array.isArray(entry.metrics) || entry.metrics.length === 0 || entry.metrics.length > 6) return null;
  const metrics: CardMetric[] = [];
  for (const raw of entry.metrics) {
    const metric = parseCardMetric(raw);
    if (!metric) return null;
    metrics.push(metric);
  }
  const sections = parseCardSections(entry.sections);
  if (sections === null) return null;
  return { kind: "team_card", title, teamName: entry.teamName,
    sourceRef: entry.sourceRef, sourceRow: entry.sourceRow, nameColumn: entry.nameColumn,
    metrics, ...(sections ? { sections } : {}),
    source: provenanceSource(provenance), provenance };
}

function resolveMemo(
  entry: Record<string, unknown>,
  title: string,
  provenance: DimeProvenance | undefined,
): MemoArtifactPayload | null {
  const sections: MemoSectionPayload[] = [];
  for (const line of Array.isArray(entry.sections) ? entry.sections : []) {
    if (typeof line !== "object" || line === null) continue;
    const s = line as Record<string, unknown>;
    const heading = typeof s.heading === "string" ? s.heading : "";
    const body = typeof s.body === "string" ? s.body : "";
    if (!heading || !body) continue;
    const anchors: MemoAnchor[] = [];
    for (const raw of Array.isArray(s.anchors) ? s.anchors : []) {
      const a = typeof raw === "object" && raw !== null ? (raw as Record<string, unknown>) : null;
      const ref = a && typeof a.ref === "string" ? a.ref : "";
      const row = a ? finiteNumber(a.row) : undefined;
      const columns = a && Array.isArray(a.columns)
        ? a.columns.filter((c): c is string => typeof c === "string" && c !== "")
        : [];
      if (ref && row !== undefined && row >= 0 && columns.length > 0) {
        anchors.push({ ref, row, columns });
      }
    }
    sections.push({ heading, body, ...(anchors.length > 0 ? { anchors } : {}) });
  }
  if (sections.length === 0) return null;
  const subtitle = typeof entry.subtitle === "string" && entry.subtitle ? entry.subtitle : undefined;
  const footnote = typeof entry.footnote === "string" && entry.footnote ? entry.footnote : undefined;
  return {
    kind: "memo",
    title,
    text: sections.map(s => `${s.heading}\n${s.body}`).join("\n\n"),
    sections,
    source: provenanceSource(provenance),
    provenance,
    ...(subtitle ? { subtitle } : {}),
    ...(footnote ? { footnote } : {}),
  };
}


function parseVerdictTeam(raw: unknown): TradeVerdictTeamPayload | null {
  if (!raw || typeof raw !== "object") return null;
  const entry = raw as Record<string, unknown>;
  if (typeof entry.team !== "string" || !entry.team) return null;
  if (!Array.isArray(entry.playersOut) || !Array.isArray(entry.playersIn)) return null;
  const playersOut = entry.playersOut.filter((p): p is string => typeof p === "string");
  const playersIn = entry.playersIn.filter((p): p is string => typeof p === "string");
  if (playersOut.length !== entry.playersOut.length || playersIn.length !== entry.playersIn.length) return null;
  const team: TradeVerdictTeamPayload = { team: entry.team, playersOut, playersIn };
  const numericKeys = ["outgoing", "incoming", "payrollBefore", "payrollAfter", "allowedIncoming"] as const;
  for (const key of numericKeys) {
    if (entry[key] === undefined) continue;
    const value = finiteNumber(entry[key]);
    if (value === undefined) return null;
    team[key] = value;
  }
  if (typeof entry.matchRule === "string" && entry.matchRule) team.matchRule = entry.matchRule;
  if (typeof entry.hardCap === "string" && entry.hardCap) team.hardCap = entry.hardCap;
  for (const flag of ["overApron1", "overApron2", "matchingFailed", "aggregates"] as const) {
    if (entry[flag] === true) team[flag] = true;
  }
  if (entry.tpeCreation && typeof entry.tpeCreation === "object") {
    const tpe = entry.tpeCreation as Record<string, unknown>;
    const amount = finiteNumber(tpe.amount);
    if (amount !== undefined) {
      team.tpeCreation = { amount, ...(typeof tpe.condition === "string" && tpe.condition ? { condition: tpe.condition } : {}) };
    }
  }
  for (const key of ["picksOut", "picksIn"] as const) {
    if (entry[key] === undefined) continue;
    if (!Array.isArray(entry[key])) return null;
    const picks: { year: number; round: number; swap?: boolean; protection?: string }[] = [];
    for (const rawPick of entry[key] as unknown[]) {
      if (!rawPick || typeof rawPick !== "object") return null;
      const pick = rawPick as Record<string, unknown>;
      const year = finiteNumber(pick.year);
      const round = finiteNumber(pick.round);
      if (year === undefined || round === undefined) return null;
      picks.push({ year, round, ...(pick.swap === true ? { swap: true } : {}), ...(typeof pick.protection === "string" && pick.protection ? { protection: pick.protection } : {}) });
    }
    if (picks.length) team[key] = picks;
  }
  return team;
}

function resolveTradeVerdict(entry: Record<string, unknown>, title: string, provenance: DimeProvenance | undefined): TradeVerdictArtifactPayload | null {
  if (typeof entry.legal !== "boolean") return null;
  if (typeof entry.sourceRef !== "string" || !entry.sourceRef) return null;
  if (!Array.isArray(entry.teams) || entry.teams.length === 0) return null;
  const teams: TradeVerdictTeamPayload[] = [];
  for (const rawTeam of entry.teams) {
    const team = parseVerdictTeam(rawTeam);
    if (!team) return null;
    teams.push(team);
  }
  const issues = Array.isArray(entry.issues)
    ? entry.issues.filter((issue): issue is string => typeof issue === "string" && issue !== "")
    : [];
  const checks: { rule: string; note?: string }[] = [];
  if (Array.isArray(entry.checks)) {
    for (const rawCheck of entry.checks) {
      if (!rawCheck || typeof rawCheck !== "object") continue;
      const check = rawCheck as Record<string, unknown>;
      if (typeof check.rule !== "string" || !check.rule) continue;
      checks.push({ rule: check.rule, ...(typeof check.note === "string" && check.note ? { note: check.note } : {}) });
    }
  }
  return {
    kind: "trade_verdict", title, legal: entry.legal, teams,
    ...(issues.length ? { issues } : {}),
    ...(checks.length ? { checks } : {}),
    ...(typeof entry.evaluationTool === "string" && entry.evaluationTool ? { evaluationTool: entry.evaluationTool } : {}),
    sourceRef: entry.sourceRef,
    source: provenanceSource(provenance), provenance,
  };
}

function resolveCapSummary(entry: Record<string, unknown>, title: string, provenance: DimeProvenance | undefined): CapSummaryArtifactPayload | null {
  if (typeof entry.team !== "string" || !entry.team) return null;
  if (typeof entry.sourceRef !== "string" || !entry.sourceRef) return null;
  const payrollBefore = finiteNumber(entry.payrollBefore);
  const payrollAfter = finiteNumber(entry.payrollAfter);
  if (payrollBefore === undefined || payrollAfter === undefined) return null;
  const out: CapSummaryArtifactPayload = {
    kind: "cap_summary", title, team: entry.team, payrollBefore, payrollAfter,
    sourceRef: entry.sourceRef,
    source: provenanceSource(provenance), provenance,
  };
  for (const key of ["delta", "capRoom", "capRoomBefore", "taxRoom", "roomApron1", "roomApron2", "teamSalaryBefore", "teamSalaryAfter", "capHoldsAfter", "rosterChargesAfter", "rosterBefore", "rosterAfter"] as const) {
    if (entry[key] === undefined) continue;
    const value = finiteNumber(entry[key]);
    if (value === undefined) return null;
    out[key] = value;
  }
  if (typeof entry.season === "string" && entry.season) out.season = entry.season;
  if (typeof entry.hardCap === "string" && entry.hardCap) out.hardCap = entry.hardCap;
  if (typeof entry.evaluationTool === "string" && entry.evaluationTool) out.evaluationTool = entry.evaluationTool;
  for (const flag of ["overTax", "overApron1", "overApron2"] as const) {
    if (entry[flag] === true) out[flag] = true;
  }
  if (Array.isArray(entry.issues)) {
    const issues = entry.issues.filter((issue): issue is string => typeof issue === "string" && issue !== "");
    if (issues.length) out.issues = issues;
  }
  if (Array.isArray(entry.steps)) {
    const steps: { kind: string; detail: string; delta?: number; payroll?: number }[] = [];
    for (const rawStep of entry.steps) {
      if (!rawStep || typeof rawStep !== "object") return null;
      const step = rawStep as Record<string, unknown>;
      if (typeof step.detail !== "string" || !step.detail) return null;
      const kind = typeof step.kind === "string" && step.kind ? step.kind : "step";
      const parsed: { kind: string; detail: string; delta?: number; payroll?: number } = { kind, detail: step.detail };
      for (const key of ["delta", "payroll"] as const) {
        if (step[key] === undefined) continue;
        const value = finiteNumber(step[key]);
        if (value === undefined) return null;
        parsed[key] = value;
      }
      steps.push(parsed);
    }
    if (steps.length) out.steps = steps;
  }
  if (Array.isArray(entry.restrictions)) {
    const restrictions: { threshold: string; rule: string }[] = [];
    for (const rawRestriction of entry.restrictions) {
      if (!rawRestriction || typeof rawRestriction !== "object") return null;
      const restriction = rawRestriction as Record<string, unknown>;
      if (typeof restriction.threshold !== "string" || !restriction.threshold) return null;
      if (typeof restriction.rule !== "string" || !restriction.rule) return null;
      restrictions.push({ threshold: restriction.threshold, rule: restriction.rule });
    }
    if (restrictions.length) out.restrictions = restrictions;
  }
  return out;
}

const ARTIFACT_RESOLVERS: Record<string, ArtifactResolver> = {
  chart: resolveChart,
  shot_chart: resolveShotChart,
  table: resolveTable,
  compare: resolveCompare,
  scatter: resolveScatter,
  player_card: resolvePlayerCard,
  team_card: resolveTeamCard,
  memo: resolveMemo,
  trade_verdict: resolveTradeVerdict,
  cap_summary: resolveCapSummary,};

export function memoToMarkdown(artifact: MemoArtifactPayload): string {
  const lines: string[] = [`# ${artifact.title}`];
  if (artifact.subtitle) lines.push(`\n_${artifact.subtitle}_`);
  if (!artifact.sections?.length) lines.push("", artifact.text);
  for (const section of artifact.sections ?? []) {
    lines.push("", `## ${section.heading}`, "", section.body);
    if (section.anchors?.length) {
      const refs = [...new Set(section.anchors.map(a => `${a.ref} row ${a.row}`))];
      lines.push("", `_Cited rows: ${refs.join(" · ")}_`);
    }
  }
  if (artifact.footnote) lines.push("", `---`, "", artifact.footnote);
  if (artifact.source) lines.push("", `Source: ${artifact.source}`);
  return lines.join("\n") + "\n";
}

export function asResolvedArtifacts(raw: unknown): DimeArtifact[] {
  if (!Array.isArray(raw)) return [];
  const artifacts: DimeArtifact[] = [];
  for (const item of raw) {
    if (typeof item !== "object" || item === null) continue;
    const entry = item as Record<string, unknown>;
    const kind = typeof entry.kind === "string" ? entry.kind : "";
    const resolver = Object.hasOwn(ARTIFACT_RESOLVERS, kind) ? ARTIFACT_RESOLVERS[kind] : undefined;
    const title = typeof entry.title === "string" ? entry.title : "";
    if (!resolver || !title) continue;
    const provenance =
      entry.provenance === undefined || entry.provenance === null
        ? undefined
        : parseProvenance(entry.provenance);
    const resolved = resolver(entry, title, provenance);
    if (resolved) artifacts.push(resolved);
  }
  return artifacts;
}

function parseEvidenceValue(raw: unknown): number | null {
  const num = finiteNumber(raw);
  if (num !== undefined) return num;
  if (typeof raw === "string" && raw.trim() !== "") {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
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
    const unit = typeof row.unit === "string" && row.unit !== "unitless" ? row.unit : "";
    rows.push({
      metric,
      subject,
      value: parseEvidenceValue(row.value),
      unit,
      provenance: parseProvenance(row.provenance),
    });
  }
  return rows;
}

function formatMetricValue(value: number): string | number {
  return Number.isInteger(value) ? value : Math.round(value * 10) / 10;
}

function evidenceProvenance(rows: EvidenceRow[]): DimeProvenance {
  const summary = mergeProvenance(rows.map((row) => row.provenance));
  if (rows.length < 2) return summary;
  return {
    ...summary,
    evidence: rows.map((row) => ({
      label: `${row.subject} \u00b7 ${row.metric}`,
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
        r.value === null ? "\u2014" : formatMetricValue(r.value),
        r.unit,
      ]),
    });
  }
  return artifacts;
}

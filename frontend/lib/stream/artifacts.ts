import { mergeProvenance, parseProvenance, provenanceSource } from "./provenance";
import type {
  ChartArtifactPayload,
  ChartSeriesPayload,
  ChartTone,
  CompareArtifactPayload,
  DimeArtifact,
  DimeProvenance,
  PlayerCardArtifactPayload,
  PlayerCardSectionPayload,
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
  return {
    kind: "chart",
    title,
    series,
    source: provenanceSource(provenance),
    provenance,
    footnote,
    ...(unit !== undefined ? { unit } : {}),
    ...(xLabels && xLabels.length > 0 ? { xLabels } : {}),
  };
}

function parseShotZone(
  line: unknown,
): { x: number; y: number; att: number; pct: number } | null {
  if (typeof line !== "object" || line === null) return null;
  const z = line as Record<string, unknown>;
  const x = finiteNumber(z.x);
  const y = finiteNumber(z.y);
  const att = finiteNumber(z.att);
  const pct = finiteNumber(z.pct);
  if (x === undefined || y === undefined || att === undefined || pct === undefined) {
    return null;
  }
  return { x, y, att, pct };
}

function resolveShotChart(
  entry: Record<string, unknown>,
  title: string,
  provenance: DimeProvenance | undefined,
): ShotChartArtifactPayload {
  const zones: { x: number; y: number; att: number; pct: number }[] = [];
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
  return {
    kind: "table",
    title,
    columns,
    rows,
    source: provenanceSource(provenance),
    provenance,
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

function resolvePlayerCard(entry: Record<string, unknown>, title: string, provenance: DimeProvenance | undefined): PlayerCardArtifactPayload | null {
  if (typeof entry.playerName !== "string" || !entry.playerName.trim() ||
      typeof entry.sourceRef !== "string" || !entry.sourceRef ||
      typeof entry.sourceRow !== "number" || !Number.isInteger(entry.sourceRow) || entry.sourceRow < 0 ||
      typeof entry.nameColumn !== "string" || !entry.nameColumn ||
      !Array.isArray(entry.metrics) || entry.metrics.length === 0 || entry.metrics.length > 6) return null;
  const metrics: PlayerCardArtifactPayload["metrics"] = [];
  for (const raw of entry.metrics) {
    if (!raw || typeof raw !== "object") return null;
    const metric = raw as Record<string, unknown>;
    if (typeof metric.column !== "string" || !metric.column || typeof metric.label !== "string" || !metric.label ||
        (metric.value !== null && finiteNumber(metric.value) === undefined)) return null;
    metrics.push({ column: metric.column, label: metric.label, value: metric.value as number | null,
      ...(typeof metric.unit === "string" ? { unit: metric.unit } : {}) });
  }
  let sections: PlayerCardArtifactPayload["sections"];
  if (entry.sections !== undefined) {
    if (!Array.isArray(entry.sections) || entry.sections.length === 0 || entry.sections.length > 6) return null;
    sections = [];
    for (const rawSection of entry.sections) {
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
          if (!rawMetric || typeof rawMetric !== "object") return null;
          const metric = rawMetric as Record<string, unknown>;
          if (typeof metric.column !== "string" || !metric.column || typeof metric.label !== "string" || !metric.label ||
              (metric.value !== null && finiteNumber(metric.value) === undefined)) return null;
          resolved.metrics.push({ column: metric.column, label: metric.label, value: metric.value as number | null,
            ...(typeof metric.unit === "string" ? { unit: metric.unit } : {}) });
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
  }
  return { kind: "player_card", title, playerName: entry.playerName,
    ...(typeof entry.team === "string" ? { team: entry.team } : {}),
    sourceRef: entry.sourceRef, sourceRow: entry.sourceRow, nameColumn: entry.nameColumn,
    ...(typeof entry.teamColumn === "string" ? { teamColumn: entry.teamColumn } : {}),
    metrics, ...(sections ? { sections } : {}),
    source: provenanceSource(provenance), provenance };
}

const ARTIFACT_RESOLVERS: Record<string, ArtifactResolver> = {
  chart: resolveChart,
  shot_chart: resolveShotChart,
  table: resolveTable,
  compare: resolveCompare,
  scatter: resolveScatter,
  player_card: resolvePlayerCard,
};

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

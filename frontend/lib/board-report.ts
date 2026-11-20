import type { DimeArtifact, DimeProvenance } from "./dime-stream";
import { applyPinRerun, cardRequeries, updatePin, type Board, type BoardCell, type BoardMetric, type BoardPin, type PinRequery } from "./boards";

export interface ReportBlock {
  heading: string;
  meta?: string[];
  lines?: string[];
  table?: { columns: string[]; rows: string[][] };
}

export interface BoardReport {
  title: string;
  subtitle: string;
  generated: string;
  blocks: ReportBlock[];
}

const day = (iso: string) => new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
const num = (value: unknown) => typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-US", { maximumFractionDigits: 2 }) : "—";

function provenanceLines(provenance: DimeProvenance | undefined): string[] {
  if (!provenance) return [];
  const parts = [provenance.capability, (provenance as { dataset?: string }).dataset, provenance.season, provenance.as_of].filter((part): part is string => typeof part === "string" && part.length > 0);
  const lines: string[] = [];
  if (parts.length) lines.push(`Source: ${parts.join(" · ")}`);
  if (typeof provenance.sql === "string") lines.push(`SQL: ${provenance.sql}`);
  return lines;
}

interface CardSection { label: string; metrics?: { column: string; label: string; value: number | null; unit?: string }[]; fields?: { column: string; label: string; value: string | null }[]; provenance?: DimeProvenance }

function cardBlocks(artifact: DimeArtifact & { playerName?: string; teamName?: string; metrics?: { label: string; value: number | null; unit?: string }[]; sections?: CardSection[] }): ReportBlock[] {
  const blocks: ReportBlock[] = [];
  const metrics = artifact.metrics ?? [];
  if (metrics.length) blocks.push({ heading: artifact.playerName ?? artifact.teamName ?? artifact.title, lines: metrics.map(metric => `${metric.label}: ${num(metric.value)}${metric.unit ? ` ${metric.unit}` : ""}`) });
  for (const section of artifact.sections ?? []) {
    const lines = [
      ...(section.fields ?? []).map(field => `${field.label}: ${field.value ?? "—"}`),
      ...(section.metrics ?? []).map(metric => `${metric.label}: ${num(metric.value)}${metric.unit ? ` ${metric.unit}` : ""}`),
      ...provenanceLines(section.provenance),
    ];
    blocks.push({ heading: section.label, lines });
  }
  return blocks;
}

function artifactBlocks(artifact: DimeArtifact): ReportBlock[] {
  if (artifact.kind === "memo") return [{ heading: artifact.title, lines: [artifact.text] }];
  if (artifact.kind === "table") return [{ heading: artifact.title, table: { columns: artifact.columns.map(column => column.label), rows: artifact.rows.map(row => row.map(cell => String(cell))) } }];
  if (artifact.kind === "compare") return [{ heading: artifact.title, table: { columns: ["", artifact.aName, artifact.bName], rows: artifact.rows.map(row => [row.label, num(row.a), num(row.b)]) } }];
  if (artifact.kind === "chart") {
    const lines = artifact.series.map(series => `${series.name}: ${series.values.map(num).join(", ")}${artifact.unit ? ` ${artifact.unit}` : ""}`);
    if (artifact.footnote) lines.push(artifact.footnote);
    return [{ heading: artifact.title, lines }];
  }
  if (artifact.kind === "scatter") {
    const lines = artifact.points.map(point => `${point.label}: ${num(point.x)} ${artifact.xLabel}, ${num(point.y)} ${artifact.yLabel}`);
    if (artifact.footnote) lines.push(artifact.footnote);
    return [{ heading: artifact.title, lines }];
  }
  if (artifact.kind === "shot_chart") {
    const lines = artifact.zones.map(zone => `(${zone.x}, ${zone.y}): ${zone.att} attempts, ${Math.round(zone.pct * 100)}%`);
    if (artifact.footnote) lines.push(artifact.footnote);
    return [{ heading: artifact.title, lines }];
  }
  return cardBlocks(artifact as DimeArtifact & { playerName?: string; teamName?: string; metrics?: { label: string; value: number | null; unit?: string }[]; sections?: CardSection[] });
}

function cellText(cell: BoardCell | undefined): string {
  if (!cell) return "—";
  return cell.value == null ? "—" : String(cell.value);
}

function citationLines(board: Board, metrics: BoardMetric[]): string[] {
  const lines: string[] = [];
  board.columns.forEach((column, index) => {
    const label = metrics.find(metric => metric.id === column.metric_id)?.label ?? column.metric_id;
    const cell = board.rows.map(row => board.cells[row.player_id]?.[column.metric_id]).find((item): item is BoardCell => !!item?.citation);
    if (!cell) return;
    const citation = cell.citation;
    lines.push(`[${index + 1}] ${label}: ${citation.table}.${citation.column} · ${citation.season} · ${citation.sql}${citation.params?.length ? ` (${citation.params.join(", ")})` : ""}`);
  });
  return lines;
}

export function buildBoardReport(board: Board, metrics: BoardMetric[]): BoardReport {
  const blocks: ReportBlock[] = [];
  if (board.rows.length && board.columns.length) {
    blocks.push({
      heading: "Players",
      table: {
        columns: ["Player", "Team", ...board.columns.map(column => metrics.find(metric => metric.id === column.metric_id)?.label ?? column.metric_id)],
        rows: board.rows.map(row => [row.name, row.team || "—", ...board.columns.map(column => cellText(board.cells[row.player_id]?.[column.metric_id]))]),
      },
      lines: citationLines(board, metrics),
    });
  }
  for (const pin of board.pins ?? []) {
    const meta = [`${(pin.artifact as { kind: string }).kind.replace(/_/g, " ")}`, `pinned ${day(pin.pinned_at)}`, ...(pin.refreshed_at ? [`data refreshed ${day(pin.refreshed_at)}`] : ["data as pinned"])];
    const sections = artifactBlocks(pin.artifact);
    const [first, ...rest] = sections;
    blocks.push({ heading: pin.artifact.title, meta, table: first?.table, lines: [...(first?.heading === pin.artifact.title ? (first.lines ?? []) : first?.heading ? [first.heading, ...(first.lines ?? [])] : (first?.lines ?? [])), ...provenanceLines(pin.artifact.provenance)] });
    for (const extra of rest) blocks.push({ heading: `${pin.artifact.title} — ${extra.heading}`, table: extra.table, lines: extra.lines });
  }
  return { title: board.title, subtitle: `Player board · ${board.season}`, generated: new Date().toISOString(), blocks };
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function boardReportMarkdown(report: BoardReport): string {
  const out = [`# ${report.title}`, "", `*${report.subtitle} — exported ${day(report.generated)}*`, ""];
  for (const block of report.blocks) {
    out.push(`## ${block.heading}`, "");
    if (block.meta?.length) out.push(`*${block.meta.join(" · ")}*`, "");
    if (block.table) {
      out.push(`| ${block.table.columns.join(" | ")} |`, `| ${block.table.columns.map(() => "---").join(" | ")} |`);
      for (const row of block.table.rows) out.push(`| ${row.join(" | ")} |`);
      out.push("");
    }
    for (const line of block.lines ?? []) out.push(`- ${line}`);
    if (block.lines?.length) out.push("");
  }
  return out.join("\n");
}

export function boardReportHtml(report: BoardReport): string {
  const parts = report.blocks.map(block => {
    const meta = block.meta?.length ? `<p class="meta">${block.meta.map(escapeHtml).join(" · ")}</p>` : "";
    const table = block.table ? `<table><thead><tr>${block.table.columns.map(column => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead><tbody>${block.table.rows.map(row => `<tr>${row.map(cell => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>` : "";
    const lines = block.lines?.length ? `<ul>${block.lines.map(line => `<li>${escapeHtml(line)}</li>`).join("")}</ul>` : "";
    return `<section><h2>${escapeHtml(block.heading)}</h2>${meta}${table}${lines}</section>`;
  }).join("\n");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(report.title)}</title><style>
body{font-family:ui-serif,Georgia,serif;max-width:820px;margin:40px auto;padding:0 24px;color:#1a1a1a;line-height:1.5}
h1{font-size:28px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 6px;border-bottom:1px solid #ddd;padding-bottom:4px}
.sub,.meta{color:#666;font-size:12px;font-style:italic}ul{margin:8px 0;padding-left:20px}li{font-size:13px;margin:2px 0}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:12.5px}th,td{border:1px solid #ddd;padding:5px 8px;text-align:left}th{background:#f5f5f5;font-weight:600}
@media print{body{margin:0}@page{margin:18mm}}
</style></head><body><h1>${escapeHtml(report.title)}</h1><p class="sub">${escapeHtml(report.subtitle)} — exported ${escapeHtml(day(report.generated))}</p>${parts}</body></html>`;
}

export async function refreshBoardPins(board: Board, rerun: (sql: string) => Promise<{ rows: Record<string, unknown>[] }>): Promise<{ board: Board; ran: number; failed: string[] }> {
  let next = board;
  let ran = 0;
  const failed: string[] = [];
  for (const pin of board.pins ?? []) {
    const queries: PinRequery[] = cardRequeries(pin.artifact);
    if (!queries.length) continue;
    try {
      const rows = new Map<PinRequery["key"], Record<string, unknown> | undefined>();
      for (const query of queries) rows.set(query.key, (await rerun(query.sql)).rows[query.row]);
      next = updatePin(next, pin.id, applyPinRerun(pin.artifact, rows));
      ran += 1;
    } catch {
      failed.push(pin.artifact.title);
    }
  }
  return { board: next, ran, failed };
}

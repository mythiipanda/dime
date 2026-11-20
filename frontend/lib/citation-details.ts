import type { AiMessage } from "./chat";
import { capabilityLabel, type EvidenceSource } from "./evidence";

const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const text = (...values: unknown[]) => values.find((value): value is string => typeof value === "string" && !!value.trim()) || "";

export function citationDetails(ai: AiMessage, source: EvidenceSource, prefix = "") {
  const tables = Object.values(ai.nodes).flatMap((node) => node.tables);
  const table = record(tables[Number(source.key.split("-").pop())]);
  const provenance = record(table.provenance);
  const capability = text(provenance.capability, table.tool);
  const tableId = text(table.table_id, table.evidence_id, provenance.table_id, provenance.evidence_id);
  const tableIndex = table.table_index ?? provenance.table_index;
  const candidates = tables.filter((candidate) => {
    const candidateRecord = record(candidate);
    if (!Array.isArray(candidate.rows)) return false;
    if (typeof tableIndex === "number") return tables.indexOf(candidate) === tableIndex;
    if (tableId) return [candidateRecord.table_id, candidateRecord.evidence_id, candidateRecord.id].includes(tableId);
    return candidate.tool === capability && (!provenance.season || record(candidate.meta).season === provenance.season);
  });
  const data = Array.isArray(table.rows) ? table : candidates.length === 1 ? record(candidates[0]) : table;
  const meta = record(data.meta);
  const rows = Array.isArray(data.rows) ? data.rows : [];
  const matching = rows.filter((row) => source.subject && Object.values(record(row)).some((value) => String(value).toLowerCase() === source.subject.toLowerCase()));
  const calls = Object.values(ai.nodes).flatMap((node) => node.toolCalls).filter((tool) => tool.name === capability && tool.sql);
  const call = calls.length === 1 ? calls[0] : undefined;
  const isGrid = Array.isArray(data.rows) && data.tool !== "get_comps" && data.rows.every((row) => row && typeof row === "object" && !Array.isArray(row));
  return {
    label: capabilityLabel(capability || source.stat),
    table: text(provenance.table, meta.table, capability) || "Not recorded",
    season: text(provenance.season, meta.season) || "Not recorded",
    origin: text(provenance.source, meta.source, source.origin) || "Dime evidence",
    query: text(table.sql, provenance.sql, provenance.query, data.sql, meta.sql, meta.query, call?.sql),
    count: typeof meta.rows === "number" ? meta.rows : rows.length,
    rows: (matching.length ? matching : rows).slice(0, 3).map(record),
    target: isGrid ? `${prefix}evidence-${tables.findIndex((candidate) => record(candidate) === data)}` : data.rows ? `${prefix}evidence-artifacts` : null,
  };
}
=======
import type { AnchorSelector, PiSource } from "./evidence";

const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const text = (...values: unknown[]) => values.find((value): value is string => typeof value === "string" && !!value.trim()) || "";

export function citationDetails(source: PiSource, anchor: AnchorSelector, prefix = "") {
  const data = record(source.data), meta = record(data.meta), provenance = record(data.provenance);
  const row = source.rows[anchor.row];
  const resolved = !!row && anchor.columns.length > 0 && anchor.columns.every(column => Object.hasOwn(row, column));
  return {
    label: source.label,
    table: text(meta.table, source.label, source.tool) || "Not recorded",
    season: text(meta.season, provenance.season, data.season) || "Not recorded",
    origin: text(meta.source, provenance.origin, source.tool) || "Dime evidence",
    query: text(data.sql, meta.sql, meta.query, provenance.sql),
    count: source.rows.length,
    rows: resolved ? [Object.fromEntries(anchor.columns.map(column => [source.units[column] ? `${column} (${source.units[column]})` : column, row[column]]))] : [],
    target: resolved ? `${prefix}source-${anchor.ref}-row-${anchor.row}` : null,
  };
}
>>>>>>> origin/dev

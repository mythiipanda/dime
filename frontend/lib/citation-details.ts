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
  return {
    label: capabilityLabel(capability || source.stat),
    table: text(provenance.table, meta.table, capability) || "Not recorded",
    season: text(provenance.season, meta.season) || "Not recorded",
    origin: text(provenance.source, meta.source, source.origin) || "Dime evidence",
    query: text(table.sql, provenance.sql, provenance.query, data.sql, meta.sql, meta.query, call?.sql),
    count: typeof meta.rows === "number" ? meta.rows : rows.length,
    rows: (matching.length ? matching : rows).slice(0, 3).map(record),
    target: `${prefix}evidence-${tables.indexOf(data as typeof tables[number])}`,
    fallback: `${prefix}evidence-artifacts`,
  };
}

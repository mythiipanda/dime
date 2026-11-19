import type { AiMessage } from "./chat";
import { capabilityLabel, type EvidenceSource } from "./evidence";

const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const text = (...values: unknown[]) => values.find((value): value is string => typeof value === "string" && !!value.trim()) || "";

export function citationDetails(ai: AiMessage, source: EvidenceSource, prefix = "") {
  const tables = Object.values(ai.nodes).flatMap((node) => node.tables);
  const table = record(tables[Number(source.key.split("-").pop())]);
  const provenance = record(table.provenance);
  const capability = text(provenance.capability, table.tool);
  const data = record(tables.find((candidate) => candidate.tool === capability && Array.isArray(candidate.rows)) || table);
  const meta = record(data.meta);
  const rows = Array.isArray(data.rows) ? data.rows : [];
  const matching = rows.filter((row) => source.subject && Object.values(record(row)).some((value) => String(value).toLowerCase() === source.subject.toLowerCase()));
  const call = Object.values(ai.nodes).flatMap((node) => node.toolCalls).find((tool) => tool.name === capability && tool.sql);
  return {
    label: capabilityLabel(capability || source.stat),
    table: text(provenance.table, meta.table, capability) || "Not recorded",
    season: text(provenance.season, meta.season) || "Not recorded",
    origin: text(provenance.source, meta.source, source.origin) || "Dime evidence",
    query: text(table.sql, provenance.sql, provenance.query, data.sql, meta.sql, meta.query, call?.sql),
    count: typeof meta.rows === "number" ? meta.rows : rows.length,
    rows: (matching.length ? matching : rows).slice(0, 3).map(record),
    target: `${prefix}evidence-${capability}`,
    fallback: `${prefix}evidence-artifacts`,
  };
}

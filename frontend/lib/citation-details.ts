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
    season: text(meta.season, provenance.season, data.season, row?._season) || "Not recorded",
    origin: text(meta.source, provenance.origin, source.tool) || "Dime evidence",
    query: text(data.sql, meta.sql, meta.query, provenance.sql),
    count: source.rows.length,
    rows: resolved ? [Object.fromEntries(anchor.columns.map(column => [source.units[column] ? `${column} (${source.units[column]})` : column, row[column]]))] : [],
    target: resolved ? `${prefix}source-${anchor.ref}-row-${anchor.row}` : null,
  };
}

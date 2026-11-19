import type { SQLResult } from "./notebooks";

function summary(value: unknown, depth = 0): string {
  if (value == null) return "—";
  if (typeof value !== "object") return String(value).slice(0, 200);
  if (depth >= 3) return "…";
  const entries = Array.isArray(value) ? value : Object.entries(value).map(([key, item]) => `${key}: ${summary(item, depth + 1)}`);
  return (entries.slice(0, 4).map((item) => typeof item === "string" ? item : summary(item, depth + 1)).join(" · ") + (entries.length > 4 ? " · …" : "")).slice(0, 200) || "—";
}

export function readableSnapshot(table: Pick<SQLResult, "columns" | "rows" | "truncated">) {
  return {
    ...table,
    columns: table.columns.map((column) => table.rows.some((row) => row[column.name] !== null && typeof row[column.name] === "object") ? { ...column, type: "VARCHAR" } : column),
    rows: table.rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, value !== null && typeof value === "object" ? summary(value) : value]))),
  };
}

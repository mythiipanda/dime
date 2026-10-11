import type { WarehouseTableRow } from "./api";

export function hasSeason2627(tables: WarehouseTableRow[]) {
  return tables.some(
    (t) =>
      t.season_range &&
      (t.season_range.min.includes("2026-27") || t.season_range.max.includes("2026-27")),
  );
}

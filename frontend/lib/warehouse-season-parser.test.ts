import { test } from "node:test";
import assert from "node:assert/strict";
import { parseSeasonValue, getSeason2627Coverage } from "./warehouse";
import type { WarehouseTableRow } from "./api";

test("three-digit span suffixes are rejected", () => {
  assert.equal(parseSeasonValue("2026-027"), null);
  assert.equal(parseSeasonValue("1999-000"), null);
  assert.equal(parseSeasonValue("2025-026"), null);
});

test("two-digit span suffixes are accepted", () => {
  assert.deepEqual(parseSeasonValue("2025-26"), { start_year: 2025, end_year: 2026 });
  assert.deepEqual(parseSeasonValue("2026-27"), { start_year: 2026, end_year: 2027 });
});

test("four-digit span suffixes are accepted", () => {
  assert.deepEqual(parseSeasonValue("2025-2026"), { start_year: 2025, end_year: 2026 });
  assert.deepEqual(parseSeasonValue("1999-2000"), { start_year: 1999, end_year: 2000 });
});

test("two-digit suffix rolls over the century", () => {
  assert.deepEqual(parseSeasonValue("1999-00"), { start_year: 1999, end_year: 2000 });
  assert.deepEqual(parseSeasonValue("2099-00"), { start_year: 2099, end_year: 2100 });
});

test("bare and prefixed values stay null", () => {
  assert.equal(parseSeasonValue("2026"), null);
  assert.equal(parseSeasonValue("22026"), null);
  assert.equal(parseSeasonValue("42026"), null);
  assert.equal(parseSeasonValue("NBA 2026-27"), null);
  assert.equal(parseSeasonValue("nba_official"), null);
  assert.equal(parseSeasonValue(""), null);
});

test("reversed and nonconsecutive spans stay null", () => {
  assert.equal(parseSeasonValue("2026-25"), null);
  assert.equal(parseSeasonValue("2026-2025"), null);
  assert.equal(parseSeasonValue("2026-28"), null);
  assert.equal(parseSeasonValue("2026-2028"), null);
});

test("malformed span widths are rejected", () => {
  assert.equal(parseSeasonValue("2026-2"), null);
  assert.equal(parseSeasonValue("2026-267"), null);
  assert.equal(parseSeasonValue("2026-0267"), null);
  assert.equal(parseSeasonValue("2026-"), null);
  assert.equal(parseSeasonValue("-26"), null);
  assert.equal(parseSeasonValue("20260-27"), null);
  assert.equal(parseSeasonValue("026-26"), null);
});

test("surrounding whitespace is trimmed", () => {
  assert.deepEqual(parseSeasonValue("  2026-27  "), { start_year: 2026, end_year: 2027 });
});

test("getSeason2627Coverage returns unknown for exact single-season span", () => {
  const tables: WarehouseTableRow[] = [
    { name: "a", row_count: 1, column_count: 1, season_range: { min: "2026-27", max: "2026-27" }, source_badge: "nba_official", description: "x" },
  ];
  assert.equal(getSeason2627Coverage(tables), "unknown");
});

test("getSeason2627Coverage returns unknown for sparse range", () => {
  const tables: WarehouseTableRow[] = [
    { name: "a", row_count: 1, column_count: 1, season_range: { min: "2024-25", max: "2028-29" }, source_badge: "nba_official", description: "x" },
  ];
  assert.equal(getSeason2627Coverage(tables), "unknown");
});

test("getSeason2627Coverage returns unknown for reversed range", () => {
  const tables: WarehouseTableRow[] = [
    { name: "a", row_count: 1, column_count: 1, season_range: { min: "2028-29", max: "2024-25" }, source_badge: "nba_official", description: "x" },
  ];
  assert.equal(getSeason2627Coverage(tables), "unknown");
});

test("getSeason2627Coverage returns unknown for bare-year range", () => {
  const tables: WarehouseTableRow[] = [
    { name: "a", row_count: 1, column_count: 1, season_range: { min: "2026", max: "2027" }, source_badge: "nba_official", description: "x" },
  ];
  assert.equal(getSeason2627Coverage(tables), "unknown");
});

test("getSeason2627Coverage returns unknown for null range", () => {
  const tables: WarehouseTableRow[] = [
    { name: "a", row_count: 1, column_count: 1, season_range: null, source_badge: "nba_official", description: "x" },
  ];
  assert.equal(getSeason2627Coverage(tables), "unknown");
});

test("getSeason2627Coverage returns unknown for zero-row table", () => {
  const tables: WarehouseTableRow[] = [
    { name: "a", row_count: 0, column_count: 1, season_range: { min: "2025-26", max: "2026-27" }, source_badge: "nba_official", description: "x" },
  ];
  assert.equal(getSeason2627Coverage(tables), "unknown");
});

test("getSeason2627Coverage returns unknown for malformed 2026-027", () => {
  const tables: WarehouseTableRow[] = [
    { name: "a", row_count: 1, column_count: 1, season_range: { min: "2026-027", max: "2026-027" }, source_badge: "nba_official", description: "x" },
  ];
  assert.equal(getSeason2627Coverage(tables), "unknown");
});

test("getSeason2627Coverage returns unknown for range excluding 2026-27 but cannot prove completeness", () => {
  const tables: WarehouseTableRow[] = [
    { name: "a", row_count: 1, column_count: 1, season_range: { min: "2020-21", max: "2025-26" }, source_badge: "nba_official", description: "x" },
  ];
  assert.equal(getSeason2627Coverage(tables), "unknown");
});

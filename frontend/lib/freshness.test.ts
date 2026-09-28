// Tests for the Explore nav freshness summary (redesign Phase C).
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDateLabel, summarizeFreshness } from "./freshness";
import type { FreshRow } from "./api";

test("freshDateLabel formats ISO timestamps as 'Mon D'", () => {
  assert.equal(freshDateLabel("2026-09-26T14:30:00"), "Sep 26");
  assert.equal(freshDateLabel("2026-01-05"), "Jan 5");
  assert.equal(freshDateLabel("2026-09-26"), "Sep 26");
});

test("freshDateLabel returns null on bad input", () => {
  assert.equal(freshDateLabel("never"), null);
  assert.equal(freshDateLabel("2026-13-01"), null);
  assert.equal(freshDateLabel(""), null);
});

const rows: FreshRow[] = [
  { table: "silver_team_games", rows: 1200, last_fetch: "2026-09-24T10:00:00", data_through: "2026-09-24" },
  { table: "silver_gamelogs", rows: 9800, last_fetch: "2026-09-26T14:30:00", data_through: "2026-09-26" },
  { table: "silver_shots", rows: 500, last_fetch: "2026-09-26T09:00:00", data_through: "2026-09-20" },
];

test("summarizeFreshness uses the MINIMUM coverage date so a fresh table can't mask stale ones", () => {
  assert.equal(
    summarizeFreshness(rows),
    "Data through Sep 20 · 3 datasets",
  );
});

test("summarizeFreshness is order-independent", () => {
  const shuffled = [rows[2], rows[0], rows[1]];
  assert.equal(
    summarizeFreshness(shuffled),
    "Data through Sep 20 · 3 datasets",
  );
});

test("summarizeFreshness skips tables without coverage and zero-row tables in the count", () => {
  const mixed: FreshRow[] = [
    ...rows,
    { table: "silver_standings", rows: 30, last_fetch: "2026-09-26T14:30:00", data_through: null },
    { table: "silver_playoffs", rows: 0, last_fetch: null, data_through: null },
  ];
  assert.equal(
    summarizeFreshness(mixed),
    "Data through Sep 20 · 4 datasets",
  );
});

test("summarizeFreshness falls back to an honest 'Last fetch' label on backends without coverage dates", () => {
  const legacy: FreshRow[] = [
    { table: "silver_team_games", rows: 1200, last_fetch: "2026-09-24T10:00:00" },
    { table: "silver_gamelogs", rows: 9800, last_fetch: "2026-09-26T14:30:00" },
  ];
  assert.equal(
    summarizeFreshness(legacy),
    "Last fetch Sep 26 · 2 datasets",
  );
});

test("summarizeFreshness returns null when nothing is known", () => {
  assert.equal(summarizeFreshness([]), null);
  assert.equal(
    summarizeFreshness([{ table: "silver_x", rows: 0, last_fetch: null }]),
    null,
  );
});

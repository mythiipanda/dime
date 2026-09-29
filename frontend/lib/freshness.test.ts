
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDateLabel, updatedLine } from "./freshness";
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

test("updatedLine uses the EARLIEST coverage date so a fresh table can't mask stale ones", () => {
  assert.equal(updatedLine(rows), "Updated Sep 20");
});

test("updatedLine is order-independent", () => {
  const shuffled = [rows[2], rows[0], rows[1]];
  assert.equal(updatedLine(shuffled), "Updated Sep 20");
});

test("updatedLine ignores feeds with no coverage date", () => {
  const mixed: FreshRow[] = [
    ...rows,
    { table: "silver_standings", rows: 30, last_fetch: "2026-09-26T14:30:00", data_through: null },
    { table: "silver_playoffs", rows: 0, last_fetch: null, data_through: null },
  ];
  assert.equal(updatedLine(mixed), "Updated Sep 20");
});

test("updatedLine falls back to the latest feed time on backends without coverage dates", () => {
  const legacy: FreshRow[] = [
    { table: "silver_team_games", rows: 1200, last_fetch: "2026-09-24T10:00:00" },
    { table: "silver_gamelogs", rows: 9800, last_fetch: "2026-09-26T14:30:00" },
    { table: "silver_shots", rows: 50, last_fetch: null },
  ];
  assert.equal(updatedLine(legacy), "Updated Sep 26");
});

test("updatedLine returns null when nothing is known", () => {
  assert.equal(updatedLine([]), null);
  assert.equal(
    updatedLine([{ table: "silver_x", rows: 0, last_fetch: null }]),
    null,
  );
});

test("updatedLine returns null on an unparseable coverage date", () => {
  assert.equal(
    updatedLine([{ table: "silver_x", rows: 1, last_fetch: null, data_through: "junk" }]),
    null,
  );
});

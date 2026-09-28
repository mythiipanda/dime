// Tests for the Explore nav freshness summary (redesign Phase C).
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDateLabel, summarizeFreshness } from "./freshness";
import type { FreshRow } from "./api";

test("freshDateLabel formats ISO timestamps as 'Mon D'", () => {
  assert.equal(freshDateLabel("2026-09-26T14:30:00"), "Sep 26");
  assert.equal(freshDateLabel("2026-01-05"), "Jan 5");
});

test("freshDateLabel returns null on bad input", () => {
  assert.equal(freshDateLabel("never"), null);
  assert.equal(freshDateLabel("2026-13-01"), null);
  assert.equal(freshDateLabel(""), null);
});

const rows: FreshRow[] = [
  { table: "silver_team_games", rows: 1200, last_fetch: "2026-09-24T10:00:00" },
  { table: "silver_gamelogs", rows: 9800, last_fetch: "2026-09-26T14:30:00" },
  { table: "silver_shots", rows: 500, last_fetch: "2026-09-20T08:00:00" },
];

test("summarizeFreshness picks the latest date and counts non-empty tables", () => {
  assert.equal(
    summarizeFreshness(rows),
    "Data through Sep 26 · 3 datasets",
  );
});

test("summarizeFreshness picks latest regardless of row order", () => {
  const shuffled = [rows[2], rows[0], rows[1]];
  assert.equal(
    summarizeFreshness(shuffled),
    "Data through Sep 26 · 3 datasets",
  );
});

test("summarizeFreshness skips zero-row tables in the count", () => {
  const withEmpty: FreshRow[] = [
    ...rows,
    { table: "silver_playoffs", rows: 0, last_fetch: null },
  ];
  assert.equal(
    summarizeFreshness(withEmpty),
    "Data through Sep 26 · 3 datasets",
  );
});

test("summarizeFreshness returns null when nothing has a fetch time", () => {
  assert.equal(summarizeFreshness([]), null);
  assert.equal(
    summarizeFreshness([{ table: "silver_x", rows: 0, last_fetch: null }]),
    null,
  );
});

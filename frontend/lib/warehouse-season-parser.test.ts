import { test } from "node:test";
import assert from "node:assert/strict";
import { parseSeasonValue } from "./warehouse";

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

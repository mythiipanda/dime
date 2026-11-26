import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const runtimeSource = readFileSync(join(__dirname, "runtime.ts"), "utf8");

test("canonical tool map steers cap audits to silver_cap_room, not named cap tools", () => {
  assert.match(runtimeSource, /sql_exec over silver_cap_room/);
  assert.match(runtimeSource, /do not answer from get_cap_table or get_cap_ledger output even when they return rows/);
  assert.match(runtimeSource, /COMMITTED_SALARY plus the projected cap\/tax\/apron lines/);
});

test("canonical tool map has no rebase conflict debris", () => {
  assert.ok(!runtimeSource.includes("|||||||"));
  assert.ok(!runtimeSource.includes("<<<<<<<"));
  assert.ok(!runtimeSource.includes(">>>>>>>"));
});

test("canonical tool map steers per-game leaderboards to the rate categories, not totals", () => {
  assert.match(runtimeSource, /PPG\/RPG\/APG\/SPG\/BPG\/TS_PCT/);
  assert.match(runtimeSource, /season-totals boards/);
});

test("canonical tool map steers raw impact metrics and salary-value mismatch audits to the impact tables", () => {
  assert.match(runtimeSource, /silver_rapm \(one row per player-season: name, rapm, possessions, _season\)/);
  assert.match(runtimeSource, /silver_impact \(BPM, VORP per player-season\)/);
  assert.match(runtimeSource, /neither substitutes for the raw impact tables/);
});

test("canonical tool map bars web_search for warehouse-covered facts", () => {
  assert.match(runtimeSource, /web results reflect the real world, not this warehouse/);
  assert.match(runtimeSource, /web_search can never resolve a player's team, stats, salary, contract, trade/);
});

test("load_skill and run_status teaching uses plain direct calls, not the tools. prefix fiction", () => {
  assert.ok(!/await tools\.load_skill/.test(runtimeSource));
  assert.ok(!/await tools\.run_status/.test(runtimeSource));
  assert.match(runtimeSource, /call load_skill with name 'statistical-modeling' as a plain direct tool call/);
  assert.match(runtimeSource, /a direct run_status call reports elapsed_ms/);
});

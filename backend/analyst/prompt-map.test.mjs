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

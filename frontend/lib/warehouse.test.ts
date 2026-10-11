import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

function read(rel: string[]) {
  return readFileSync(join(process.cwd(), ...rel), "utf8");
}

test("warehouse header wraps at 390px and controls stay reachable", () => {
  const page = read(["app", "warehouse", "page.tsx"]);
  assert.ok(page.includes("flex-wrap"));
  assert.ok(page.includes("min-h-11"));
  assert.ok(page.includes("max-w-full"));
  assert.ok(page.includes("flex-col"));
  assert.ok(page.includes("sm:flex-row"));
  assert.ok(!page.includes("flex h-11 shrink-0 items-center justify-between"));
});

test("warehouse source badges include unknown without guessing origin", () => {
  const api = read(["lib", "api.ts"]);
  assert.ok(api.includes('"unknown"'));
  const page = read(["app", "warehouse", "page.tsx"]);
  assert.ok(page.includes('value: "unknown"'));
  assert.ok(page.includes("Unknown"));
});

test("warehouse loading and empty states are distinct", () => {
  const page = read(["app", "warehouse", "page.tsx"]);
  assert.ok(page.includes("Loading tables"));
  assert.ok(page.includes("No tables in the warehouse."));
  assert.ok(page.includes('role="status"'));
  assert.ok(page.includes("aria-live"));
});

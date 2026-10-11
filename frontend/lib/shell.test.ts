import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { isActiveDestination, normalizeActive } from "./shell";
import { hasSeason2627 } from "./warehouse";

function read(rel: string[]) {
  return readFileSync(join(process.cwd(), ...rel), "utf8");
}

test("duplicate rails are hidden with a descendant selector", () => {
  const shell = read(["components", "site", "WorkspaceShell.tsx"]);
  assert.ok(shell.includes('.workspace-content main aside[aria-label="dime navigation"]'));
  assert.ok(!shell.includes(".workspace-content > main > aside"));
  const page = read(["app", "page.tsx"]);
  assert.ok(page.includes("WorkspaceShell"));
  assert.ok(page.includes("DimeHarness"));
});

test("chat rail resolves active case-insensitively for all destinations", () => {
  assert.equal(normalizeActive("chat"), "chat");
  assert.equal(normalizeActive("Chat"), "chat");
  assert.equal(normalizeActive("Warehouse"), "warehouse");
  assert.ok(isActiveDestination("Chat", normalizeActive("chat")));
  const names = ["Today", "Chat", "Notebook", "Warehouse", "Skills", "History", "Explore", "Standings"];
  for (const name of names) {
    assert.ok(isActiveDestination(name, normalizeActive(name)));
  }
  assert.ok(isActiveDestination("Today", normalizeActive("Today")));
  assert.ok(!isActiveDestination("Chat", normalizeActive("Today")));
});

test("shell and chat use viewport-relative min heights without clipping", () => {
  const shell = read(["components", "site", "WorkspaceShell.tsx"]);
  assert.ok(shell.includes("min-h-[100dvh]"));
  assert.ok(!shell.includes("flex h-[100dvh]"));
  const harness = read(["components", "site", "DimeHarness.tsx"]);
  assert.ok(harness.includes("min-h-[calc(100dvh-20px)]"));
  assert.ok(!harness.includes("flex h-[100dvh]"));
  const page = read(["app", "page.tsx"]);
  assert.ok(page.includes("flex min-h-0 flex-1 flex-col"));
});

test("empty states are honest and share one action", () => {
  const routes: Array<{ dir: string; name: string }> = [
    { dir: "today", name: "Today" },
    { dir: "explore", name: "Explore" },
    { dir: "history", name: "History" },
    { dir: "notebook", name: "Notebook" },
    { dir: "skills", name: "Skills" },
    { dir: "standings", name: "Standings" },
  ];
  const banned = [
    "Daily briefing",
    "League-wide discovery",
    "Your work",
    "Working papers",
    "Analyst toolkit",
    "League table",
    "matchups and questions",
    "follow the evidence",
    "pick up a thread",
    "lasting record",
    "research methods",
    "playoff race",
  ];
  for (const r of routes) {
    const src = read(["app", r.dir, "page.tsx"]);
    assert.ok(src.includes("Not available yet"));
    assert.ok(src.includes("Back to Chat"));
    assert.ok(src.includes(r.name + " is not available yet."));
    for (const phrase of banned) {
      assert.ok(!src.includes(phrase));
    }
  }
});

test("season 2026-27 statement derives from returned rows", () => {
  assert.equal(
    hasSeason2627([
      { name: "a", row_count: 1, column_count: 1, season_range: { min: "2025-26", max: "2026-27" }, source_badge: "nba_official", description: "x" },
    ]),
    true,
  );
  assert.equal(
    hasSeason2627([
      { name: "a", row_count: 1, column_count: 1, season_range: { min: "2025-26", max: "2025-26" }, source_badge: "nba_official", description: "x" },
    ]),
    false,
  );
  assert.equal(hasSeason2627([]), false);
  const page = read(["app", "warehouse", "page.tsx"]);
  assert.ok(page.includes("hasSeason2627(tables)"));
  assert.ok(page.includes("2026-27 season: data available."));
  assert.ok(page.includes("2026-27 season: no data yet (offseason)."));
  assert.ok(page.includes("No tables in the warehouse."));
  assert.ok(page.includes("data-state="));
  assert.ok(page.includes("aria-busy"));
});

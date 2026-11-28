import assert from "node:assert/strict";
import { test } from "node:test";
import { serializeViewContext, withViewContext } from "../dist/view-context.js";

function megaTrade(pickCount = 40) {
  const picks = [];
  for (let i = 0; i < pickCount; i += 1)
    picks.push(`202${i % 9} first-round pick number ${i} (top-4 protected, swap rights detailed)`);
  return {
    kind: "trade",
    summary: "mega 4-team trade",
    entities: {
      teams: ["MIL", "DAL", "ATL", "PHX"],
      packages: ["MIL", "DAL", "ATL", "PHX"].map((team, idx) => ({
        team,
        players: [0, 1, 2, 3].map((n) => `${String.fromCharCode(65 + idx)}`.repeat(38) + ` player ${n}`),
        picks,
      })),
      legal: false,
      issues: ["x".repeat(400)],
    },
  };
}

test("small context passes through with full detail", () => {
  const context = { kind: "trade", summary: "s", entities: { teams: ["MIL"], season: "2026-27" } };
  const out = withViewContext({ q: "evaluate this", context });
  assert.ok(out.includes("<dime-context"));
  assert.ok(out.endsWith("evaluate this"));
});

test("oversize construction degrades: low-value detail stripped, core kept", () => {
  const out = withViewContext({ q: "evaluate this", context: megaTrade() });
  assert.ok(out.includes("<dime-context"), "envelope survives reduction");
  assert.ok(out.includes('"players"'), "player detail kept");
  assert.ok(!out.includes("pick number 5"), "pick detail stripped first");
  assert.ok(out.endsWith("evaluate this"), "question intact");
});

test("irreducible context falls back with a visible note, never silently", () => {
  const huge = { kind: "trade", summary: "x".repeat(1900), entities: { blob: "y".repeat(7900) } };
  const out = withViewContext({ q: "evaluate this", context: huge });
  assert.ok(!out.includes("<dime-context"));
  assert.ok(out.includes("too large to attach"));
  assert.ok(out.startsWith("evaluate this"));
});

test("serialize omits refs when absent", () => {
  const out = serializeViewContext({ kind: "cap_scenario", summary: "s", entities: {} }, "q");
  assert.ok(!out.includes("refs"));
});

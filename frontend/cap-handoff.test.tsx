import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";

test("cap handoff round-trips valid payloads and consumes exactly once", async () => {
  const dom = new JSDOM("", { url: "http://localhost/" });
  Object.assign(globalThis, { window: dom.window, sessionStorage: dom.window.sessionStorage });
  const { writeCapHandoff, consumeCapHandoff } = await import("./lib/cap-handoff");
  const handoff = {
    team: "DAL",
    season: "2026-27",
    moves: [
      { kind: "trade_out" as const, player: "Player One", amount: 40000000 },
      { kind: "trade_in" as const, player: "Player Two", amount: 38000000 },
    ],
    source: "DAL ↔ NYK · 2 players",
  };
  writeCapHandoff(handoff);
  assert.deepEqual(consumeCapHandoff(), handoff);
  assert.equal(consumeCapHandoff(), null, "consumed handoffs never re-apply — one-way, one-shot");
});

test("malformed or empty handoffs are rejected rather than half-applied", async () => {
  const dom = new JSDOM("", { url: "http://localhost/" });
  Object.assign(globalThis, { window: dom.window, sessionStorage: dom.window.sessionStorage });
  const { consumeCapHandoff } = await import("./lib/cap-handoff");
  window.sessionStorage.setItem("dime_cap_handoff_v1", JSON.stringify({ team: "DAL", season: "2026-27", moves: [] }));
  assert.equal(consumeCapHandoff(), null, "empty moves is not a scenario");
  window.sessionStorage.setItem("dime_cap_handoff_v1", "not json");
  assert.equal(consumeCapHandoff(), null);
  window.sessionStorage.setItem("dime_cap_handoff_v1", JSON.stringify({ team: "DAL", season: "2026-27", moves: [{ kind: "nonsense" }] }));
  assert.equal(consumeCapHandoff(), null, "unknown move kinds rejected");
});

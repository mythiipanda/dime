import assert from "node:assert/strict";
import { test } from "node:test";
import { resolveTradeVerdict } from "./dist/trade-verdict.js";
import { resolveCapSummary } from "./dist/cap-summary.js";
import { tradeConstructionFromArgs, capConstructionFromArgs } from "./dist/construction.js";

function record(tool, args, result) {
  return { ref: "r1", callId: "c1", tool, args, response: { content: [], structuredContent: result, isError: false } };
}

const tradeArgs = {
  legs: JSON.stringify([
    { from: "DAL", to: "MIL", players: ["Klay Thompson"], picks: [{ year: 2029, round: 1 }] },
    { from: "MIL", to: "DAL", players: ["Kyle Kuzma"] },
  ]),
  season: "2026-27",
};
const tradeResult = {
  legal: true,
  rows: [
    { team: "DAL", players_out: ["Klay Thompson"], players_in: ["Kyle Kuzma"], outgoing: 16000000, incoming: 15000000, payroll_before: 189000000, payroll_after: 188000000 },
    { team: "MIL", players_out: ["Kyle Kuzma"], players_in: ["Klay Thompson"], outgoing: 15000000, incoming: 16000000, payroll_before: 170000000, payroll_after: 171000000 },
  ],
  issues: [],
};

test("trade_verdict embeds the construction validated against the object payload shape", () => {
  const out = resolveTradeVerdict({ kind: "trade_verdict", title: "t", ref: "r1" }, () => record("get_trade_legality", tradeArgs, tradeResult));
  assert.ok(out.construction, "construction embedded");
  assert.equal(out.construction.season, "2026-27");
  assert.equal(out.construction.legs.length, 2);
  assert.equal(out.construction.legs[0].from, "DAL");
  assert.equal(out.construction.legs[0].picks[0].year, 2029);
});

test("trade construction falls back to the result season echo when args omit it", () => {
  const args = { legs: tradeArgs.legs };
  const out = tradeConstructionFromArgs(args, "2026-27");
  assert.equal(out?.season, "2026-27");
  assert.equal(tradeConstructionFromArgs(args), undefined, "no season anywhere means no construction");
});

test("cap_summary embeds normalized moves: named signings, bare amounts, waive stretch", () => {
  const args = { team: "DAL", signings: "Reggie Bullock=12M, 3000000", waive_players: "Klay Thompson", stretch: true, season: "2026-27" };
  const result = { summary: { team: "DAL", season: "2026-27", payroll_before: 180000000, payroll_after: 189000000 }, rows: [{ kind: "signing", detail: "x", delta: 1, payroll: 2 }] };
  const out = resolveCapSummary({ kind: "cap_summary", title: "t", ref: "r1" }, () => record("get_cap_scenario", args, result));
  assert.ok(out.construction);
  assert.equal(out.construction.team, "DAL");
  const moves = out.construction.moves;
  assert.equal(moves.length, 3);
  assert.deepEqual(moves[0], { kind: "signing", label: "Reggie Bullock", amount: 12000000 });
  assert.equal(moves[1].amount, 3000000);
  assert.deepEqual(moves[2], { kind: "waive", player: "Klay Thompson", stretch: true });
});

test("cap construction covers trade moves and the waiver date", () => {
  const args = { team: "DAL", in_players: "Kyle Kuzma", trade_out_players: "Klay Thompson, Max Christie", waiver_date: "2026-08-15", season: "2026-27" };
  const out = capConstructionFromArgs(args);
  assert.equal(out.waiver_date, "2026-08-15");
  assert.equal(out.moves.filter((m) => m.kind === "trade_in").length, 1);
  assert.equal(out.moves.filter((m) => m.kind === "trade_out").length, 2);
});

test("malformed args never break artifact resolution — construction simply absent", () => {
  const broken = { legs: "not json at all", season: "2026-27" };
  assert.equal(tradeConstructionFromArgs(broken), undefined);
  const out = resolveTradeVerdict({ kind: "trade_verdict", title: "t", ref: "r1" }, () => record("get_trade_legality", broken, tradeResult));
  assert.equal(out.construction, undefined);
  assert.equal(out.legal, true, "artifact itself still resolves");
});

test("schema-incompatible legs are refused rather than embedded lossy", () => {
  const bad = { legs: JSON.stringify([{ from: "DAL", to: "MIL", players: ["x"], evil: "x".repeat(200) }]), season: "2026-27" };
  assert.equal(tradeConstructionFromArgs(bad), undefined, "additionalProperties violation rejected");
});

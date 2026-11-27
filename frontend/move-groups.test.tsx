import assert from "node:assert/strict";
import test from "node:test";
import { mintGroupId, removeUnitAt, ungroupAt, unitizeMoves } from "./lib/move-groups";
import type { ScenarioMove } from "./lib/capsheet-fixture";

const out = (player: string, group?: string): ScenarioMove => ({ kind: "trade_out", player, ...(group ? { group } : {}) });
const sign = (label: string): ScenarioMove => ({ kind: "signing", label, amount: 1000000 });

test("ungrouped moves are singleton units", () => {
  const units = unitizeMoves([sign("a"), sign("b")]);
  assert.equal(units.length, 2);
  assert.equal(units[0].group, null);
  assert.equal(units[0].entries.length, 1);
});

test("consecutive same-group moves collapse into one unit", () => {
  const units = unitizeMoves([sign("a"), out("x", "g1"), out("y", "g1"), sign("b")]);
  assert.equal(units.length, 3);
  assert.equal(units[1].group, "g1");
  assert.equal(units[1].entries.length, 2);
  assert.equal(units[1].entries[0].index, 1);
  assert.equal(units[1].entries[1].index, 2);
});

test("same group id split by another move does not merge", () => {
  const units = unitizeMoves([out("x", "g1"), sign("a"), out("y", "g1")]);
  assert.equal(units.length, 3);
});

test("removing a group unit removes every move of the group, none left behind", () => {
  const moves = [sign("a"), out("x", "g1"), { kind: "trade_in", player: "z", group: "g1" } as ScenarioMove, sign("b")];
  const next = removeUnitAt(moves, 1);
  assert.equal(next.length, 2);
  assert.equal(next.some((move) => move.group === "g1"), false);
  assert.deepEqual(next.map((move) => move.kind), ["signing", "signing"]);
});

test("removing a singleton unit removes exactly that move", () => {
  const next = removeUnitAt([sign("a"), sign("b")], 0);
  assert.equal(next.length, 1);
  assert.equal(next[0].label, "b");
});

test("ungrouping strips the group field but keeps the moves in place", () => {
  const moves = [out("x", "g1"), { kind: "trade_in", player: "z", group: "g1" } as ScenarioMove];
  const next = ungroupAt(moves, 0);
  assert.equal(next.length, 2);
  assert.equal(next.every((move) => move.group === undefined), true);
  assert.equal(next[0].player, "x");
});

test("minted group ids are unique trade-prefixed strings", () => {
  const a = mintGroupId();
  const b = mintGroupId();
  assert.notEqual(a, b);
  assert.equal(a.startsWith("trade-"), true);
});

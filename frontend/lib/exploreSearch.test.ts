// Tests for the Phase 3 search-first header helpers (lib/exploreSearch).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  contextForResult,
  groupLabel,
  matchStats,
  resultHint,
} from "./exploreSearch";

test("matchStats finds categories by case-insensitive substring", () => {
  assert.deepEqual(matchStats("pts"), [{ kind: "stat", stat: "PTS" }]);
  assert.deepEqual(matchStats("REB"), [{ kind: "stat", stat: "REB" }]);
  assert.deepEqual(matchStats("st"), [
    { kind: "stat", stat: "AST" },
    { kind: "stat", stat: "STL" },
  ]);
});

test("matchStats returns [] for short or blank queries", () => {
  assert.deepEqual(matchStats(""), []);
  assert.deepEqual(matchStats("p"), []);
  assert.deepEqual(matchStats("  "), []);
});

test("matchStats returns [] when nothing matches", () => {
  assert.deepEqual(matchStats("xyz"), []);
});

test("matchStats uses plain substring matching, no pattern syntax", () => {
  // Regex metacharacters are literal text, never patterns.
  assert.deepEqual(matchStats(".*"), []);
  assert.deepEqual(matchStats("P+S"), []);
});

test("contextForResult sends a player to Shots with that player", () => {
  assert.deepEqual(contextForResult({ kind: "player", id: 2544, name: "LeBron James" }), {
    panel: "shots",
    playerName: "LeBron James",
    playerId: "2544",
  });
});

test("contextForResult sends a team to Lineups with that team", () => {
  assert.deepEqual(
    contextForResult({ kind: "team", id: 14, name: "Los Angeles Lakers", abbr: "LAL" }),
    { panel: "lineups", teamAbbr: "LAL" },
  );
});

test("contextForResult opens Lineups unfiltered when the abbreviation is unknown", () => {
  assert.deepEqual(
    contextForResult({ kind: "team", id: 99, name: "Unknown", abbr: null }),
    { panel: "lineups" },
  );
});

test("contextForResult sends a stat to Leaders with that category", () => {
  assert.deepEqual(contextForResult({ kind: "stat", stat: "AST" }), {
    panel: "leaders",
    stat: "AST",
  });
});

test("result labels stay factual, never evaluative", () => {
  assert.equal(groupLabel("player"), "Players");
  assert.equal(groupLabel("team"), "Teams");
  assert.equal(groupLabel("stat"), "Stats");
  assert.equal(
    resultHint({ kind: "player", id: 1, name: "X" }),
    "Shots",
  );
  assert.equal(
    resultHint({ kind: "team", id: 1, name: "Y", abbr: "BOS" }),
    "Lineups",
  );
  assert.equal(resultHint({ kind: "stat", stat: "PTS" }), "Leaders");
});

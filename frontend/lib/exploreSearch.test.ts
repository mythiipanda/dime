// Tests for the Phase 3 search-first header helpers (lib/exploreSearch).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildSearchItems,
  contextForResult,
  entityKind,
  groupLabel,
  matchStats,
  placeSearchMenu,
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

// Group isolation (search dropdown): entity type comes from each row's
// own response fields, never from which array the row arrived in. All
// fixture names are made up.
test("entityKind reads the row fields, not the array it arrived in", () => {
  assert.equal(entityKind({ id: 101, full_name: "Test Player One" }), "player");
  assert.equal(
    entityKind({ id: 201, full_name: "Test Team Alpha", abbreviation: "TTA" }),
    "team",
  );
  assert.equal(
    entityKind({ id: 202, full_name: "Test Team Beta", abbreviation: null }),
    "team",
  );
});

test("buildSearchItems keeps team rows out of Players and player rows out of Teams", () => {
  const strayTeam = { id: 201, full_name: "Test Team Alpha", abbreviation: "TTA" };
  const items = buildSearchItems(
    [
      { id: 101, full_name: "Test Player One" },
      strayTeam, // endpoint returned a team row inside the players array
    ],
    [
      { id: 102, full_name: "Test Player Two" }, // player row inside the teams array
      { id: 201, full_name: "Test Team Alpha", abbreviation: "TTA" },
    ],
    [],
  );
  const players = items.filter((r) => r.kind === "player");
  const teams = items.filter((r) => r.kind === "team");
  // The team renders once, under Teams only — never under Players.
  assert.equal(teams.length, 1);
  assert.equal(teams[0].name, "Test Team Alpha");
  assert.ok(players.every((r) => r.kind === "player"));
  assert.ok(!players.some((r) => r.kind === "player" && r.name === "Test Team Alpha"));
  // Both player rows land under Players, including the misplaced one.
  assert.deepEqual(
    players.map((r) => (r.kind === "player" ? r.name : "")),
    ["Test Player One", "Test Player Two"],
  );
});

// Anchor behavior (search dropdown): scrolling repositions the open
// dropdown under the field instead of closing it. placeSearchMenu always
// returns a placement for the field's current rect.
test("placeSearchMenu opens below the field when there is room", () => {
  const p = placeSearchMenu(
    { top: 100, bottom: 140, left: 20, width: 400 },
    { width: 1280, height: 800 },
  );
  assert.equal(p.above, false);
  assert.equal(p.top, 146);
  assert.equal(p.left, 20);
  assert.equal(p.width, 400);
});

test("placeSearchMenu flips above the field when space below runs out", () => {
  const p = placeSearchMenu(
    { top: 700, bottom: 740, left: 20, width: 400 },
    { width: 1280, height: 800 },
  );
  assert.equal(p.above, true);
  assert.equal(p.bottom, 106);
});

test("placeSearchMenu tracks the field on scroll instead of closing", () => {
  const viewport = { width: 1280, height: 800 };
  const field = { top: 120, bottom: 160, left: 20, width: 400 };
  const before = placeSearchMenu(field, viewport);
  // The page scrolls 60px: same field, new rect, still a placement.
  const afterScroll = placeSearchMenu({ ...field, top: 60, bottom: 100 }, viewport);
  assert.equal(before.above, false);
  assert.equal(afterScroll.above, false);
  assert.equal(before.top, 166);
  assert.equal(afterScroll.top, 106);
});

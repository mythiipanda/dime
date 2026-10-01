import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildStreakItems,
  buildWatchItems,
  feedActionFor,
  streakLine,
  type FeedItem,
} from "./exploreFeed";
import {
  abbrForTeamFullName,
  TEAM_ABBR_BY_FULL_NAME,
  TEAM_IDS,
} from "./teams";
import type { ExploreContext } from "./exploreSearch";

function teamRow(over: Partial<FeedItem> = {}): FeedItem {
  return {
    id: "streak-0-vexford",
    kind: "streak",
    entity: "team",
    name: "Vexford",
    statText: "won 3 straight · 10-5",
    rankLabel: "#1",
    rankTitle: "Ranked #1 of 1 team streaks",
    question: null,
    ...over,
  };
}

function playerRow(over: Partial<FeedItem> = {}): FeedItem {
  return {
    id: "mover-0-mara-voss",
    kind: "mover",
    entity: "player",
    name: "Mara Voss",
    statText: "up 6 spots, +2.3 pts",
    rankLabel: "#14",
    rankTitle: "Ranked #14 by points per game",
    question: null,
    ...over,
  };
}

function dispatched(item: FeedItem): { selected: ExploreContext[]; asked: string[] } {
  const selected: ExploreContext[] = [];
  const asked: string[] = [];
  const action = feedActionFor(item);
  if (action.kind === "select") selected.push(action.ctx);
  else if (action.kind === "ask") asked.push(action.question);
  return { selected, asked };
}

const KNOWN_NAMES = Object.keys(TEAM_ABBR_BY_FULL_NAME);
const KNOWN_NAME = KNOWN_NAMES[0];
const KNOWN_ABBR = TEAM_ABBR_BY_FULL_NAME[KNOWN_NAME];

test("team streak rows route to select/lineups with the resolved teamAbbr", () => {
  const [item] = buildStreakItems([{ TEAM: KNOWN_NAME, W: 12, L: 5, STREAK: "W5" }]);
  assert.equal(item.entity, "team");
  const got = feedActionFor(item);
  assert.deepEqual(got, {
    kind: "select",
    ctx: { panel: "lineups", teamAbbr: KNOWN_ABBR, streak: { won: true, games: 5, wins: 12, losses: 5 } },
  });
});

test("team watchlist rows route to select/lineups with the resolved teamAbbr", () => {
  const [item] = buildWatchItems([
    { entity_type: "team", entity_id: "wx-1", snapshot: { found: true, name: KNOWN_NAME, record: "12-5", wins: 12, losses: 5 } },
  ]);
  assert.equal(item.entity, "team");
  const got = feedActionFor(item);
  assert.deepEqual(got, { kind: "select", ctx: { panel: "lineups", teamAbbr: KNOWN_ABBR } });
});

test("the full-name table has 30 entries valued in TEAM_IDS and round-trips every key", () => {
  const entries = Object.entries(TEAM_ABBR_BY_FULL_NAME);
  assert.equal(entries.length, 30);
  for (const [name, abbr] of entries) {
    assert.ok(Object.hasOwn(TEAM_IDS, abbr), `${abbr} for ${name} is not a TEAM_IDS key`);
    assert.equal(abbrForTeamFullName(name), abbr);
  }
});

test("abbrForTeamFullName normalizes trim, whitespace, and case", () => {
  const padded = `  ${KNOWN_NAME.replace(/ /g, "   ").toUpperCase()}  `;
  assert.equal(abbrForTeamFullName(padded), KNOWN_ABBR);
  assert.equal(abbrForTeamFullName("Vexford United"), null);
  assert.equal(abbrForTeamFullName(""), null);
  assert.equal(abbrForTeamFullName("   "), null);
});

test("streak and watchlist team builders emit question:null", () => {
  const [streakItem] = buildStreakItems([{ TEAM: "Vexford", W: 10, L: 5, STREAK: "W3" }]);
  assert.equal(streakItem.question, null);
  const [watchItem] = buildWatchItems([
    { entity_type: "team", entity_id: "wx-2", snapshot: { found: true, name: "Quizport", record: "11-6", wins: 11 } },
  ]);
  assert.equal(watchItem.question, null);
});

test("an unresolvable team name routes to select/lineups with no teamAbbr and never asks", () => {
  const { selected, asked } = dispatched(teamRow({ name: "Vexford United" }));
  assert.deepEqual(selected, [{ panel: "lineups" }]);
  assert.deepEqual(asked, []);
});

test("a team row carrying a stale question still routes to select and never asks", () => {
  const { selected, asked } = dispatched(
    teamRow({ name: KNOWN_NAME, question: "Why has someone won 3 straight?" }),
  );
  assert.deepEqual(selected, [{ panel: "lineups", teamAbbr: KNOWN_ABBR }]);
  assert.deepEqual(asked, []);
});

test("player rows still route to select/shots", () => {
  const got = feedActionFor(playerRow());
  assert.deepEqual(got, { kind: "select", ctx: { panel: "shots", playerName: "Mara Voss" } });
});

test("streakLine formats plain copy from structured detail", () => {
  assert.equal(streakLine({ won: true, games: 12, wins: 68, losses: 14 }), "Won 12 straight · 68-14");
  assert.equal(streakLine({ won: false, games: 3, wins: 10, losses: 5 }), "Lost 3 straight · 10-5");
});

test("streak rows carry structured streak detail into the select ctx", () => {
  const [item] = buildStreakItems([{ TEAM: KNOWN_NAME, W: 12, L: 5, STREAK: "W5" }]);
  assert.deepEqual(item.streak, { won: true, games: 5, wins: 12, losses: 5 });
  const got = feedActionFor(item);
  assert.deepEqual(got, {
    kind: "select",
    ctx: { panel: "lineups", teamAbbr: KNOWN_ABBR, streak: { won: true, games: 5, wins: 12, losses: 5 } },
  });
});

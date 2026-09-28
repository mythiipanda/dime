// Tests for the right-now feed builder (redesign Phase 4). All fixtures
// use made-up names only.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildFeedItems,
  buildMoverItems,
  buildStreakItems,
  buildWatchItems,
  FEED_MOVER_CAP,
  FEED_STREAK_CAP,
  FEED_WATCH_CAP,
} from "./exploreFeed";
import type {
  Mover,
  MoversRows,
  TeamStreak,
  TodayMover,
  WatchItem,
} from "./api";

function mover(player: string, over: Partial<Mover> = {}): Mover {
  return { player, team: "SPR", ...over };
}

function todayMover(player: string, over: Partial<TodayMover> = {}): TodayMover {
  return { PLAYER: player, TEAM: "SPR", ...over };
}

function streak(team: string, over: Partial<TeamStreak> = {}): TeamStreak {
  return { TEAM: team, W: 10, L: 5, STREAK: "W3", ...over };
}

function watch(
  entity_type: "player" | "team",
  entity_id: string,
  snapshot: WatchItem["snapshot"],
): WatchItem {
  return { entity_type, entity_id, snapshot };
}

test("movers combine rank change and points into one factual line", () => {
  const rows: MoversRows = {
    climbers: [mover("Mara Voss", { rank_now: 14, rank_change: 6, pts_change: 2.34 })],
    fallers: [],
    new_entries: [],
  };
  const [item] = buildMoverItems(rows);
  assert.equal(item.statText, "up 6 spots, +2.3 pts");
  assert.equal(item.rankLabel, "#14");
  assert.equal(item.rankTitle, "Ranked #14 by points per game");
  assert.equal(item.entity, "player");
  assert.equal(item.question, null);
});

test("movers fall back to rankOf position when rank_now is missing", () => {
  const rows: MoversRows = {
    climbers: [
      mover("Theo Lindqvist", { rank_change: 2, pts_change: 1.05 }),
      mover("June Park", { rank_change: 1, pts_change: 0.44 }),
    ],
    fallers: [],
    new_entries: [],
  };
  const got = buildMoverItems(rows);
  assert.equal(got[0].rankLabel, "#1");
  assert.equal(got[0].rankTitle, "Ranked #1 of 2 movers by points per game");
  assert.equal(got[1].rankLabel, "#2");
});

test("movers drop rows with no player name or no numbers", () => {
  const rows: MoversRows = {
    climbers: [
      mover("", { rank_now: 3, rank_change: 4, pts_change: 1 }),
      mover("   ", { rank_now: 4, rank_change: 4, pts_change: 1 }),
      mover("Silas Reed", {}),
    ],
    fallers: [mover("Ada Novak", { rank_change: -3, pts_change: -1.2 })],
    new_entries: [],
  };
  const got = buildMoverItems(rows);
  assert.deepEqual(got.map((g) => g.name), ["Ada Novak"]);
  assert.equal(got[0].statText, "down 3 spots, -1.2 pts");
});

test("new entries count as mover items with points and rank", () => {
  const rows: MoversRows = {
    climbers: [],
    fallers: [],
    new_entries: [{ player: "Rufus Clay", team: "QZT", pts: 22.44, rank: 9 }],
  };
  const [item] = buildMoverItems(rows);
  assert.equal(item.kind, "mover");
  assert.equal(item.statText, "22.4 pts");
  assert.equal(item.rankLabel, "#9");
});

test("movers cap at 6 across climbers, fallers, and new entries", () => {
  const names = ["A", "B", "C", "D", "E", "F", "G", "H"].map((n) => `Player ${n}`);
  const rows: MoversRows = {
    climbers: names.slice(0, 4).map((p) => mover(p, { rank_change: 1, pts_change: 1 })),
    fallers: names.slice(4, 6).map((p) => mover(p, { rank_change: -1, pts_change: -1 })),
    new_entries: names.slice(6).map((p) => ({ player: p, pts: 20 })),
  };
  const got = buildMoverItems(rows);
  assert.equal(got.length, FEED_MOVER_CAP);
  assert.equal(FEED_MOVER_CAP, 6);
});

test("today-shaped movers read RANK_CHANGE and PTS_CHANGE", () => {
  const got = buildMoverItems([
    todayMover("Nina Frost", { RANK_CHANGE: "+6", PTS_CHANGE: 2.31 }),
    todayMover("", { RANK_CHANGE: "+2", PTS_CHANGE: 1 }),
    todayMover("Otto Marsh", {}),
    todayMover("Iris Vale", { note: "Back in the rotation" }),
  ]);
  assert.equal(got.length, 2);
  assert.equal(got[0].name, "Nina Frost");
  assert.equal(got[0].statText, "up 6 spots, +2.3 pts");
  assert.equal(got[0].rankLabel, "#1");
  assert.equal(got[1].name, "Iris Vale");
});

test("streaks spell out the streak with the record and ask a question", () => {
  const got = buildStreakItems([
    streak("SPR", { W: 12, L: 5, STREAK: "W5" }),
    streak("QZT", { W: 8, L: 9, STREAK: "L3" }),
  ]);
  assert.equal(got[0].statText, "won 5 straight · 12-5");
  assert.equal(got[0].rankLabel, "#1");
  assert.equal(got[0].rankTitle, "Ranked #1 of 2 team streaks");
  assert.equal(got[0].question, "Why has SPR won 5 straight?");
  assert.equal(got[1].statText, "lost 3 straight · 8-9");
  assert.equal(got[1].question, "Why has QZT lost 3 straight?");
});

test("streaks drop rows with no team or no STREAK string", () => {
  const got = buildStreakItems([
    streak("", { STREAK: "W4" }),
    streak("VX", { STREAK: "" }),
    streak("VX", { STREAK: "W4" }),
  ]);
  assert.equal(got.length, 1);
  assert.equal(got[0].name, "VX");
});

test("streaks cap at 4", () => {
  const rows = ["A", "B", "C", "D", "E", "F"].map((t) => streak(`Team ${t}`));
  assert.equal(buildStreakItems(rows).length, FEED_STREAK_CAP);
  assert.equal(FEED_STREAK_CAP, 4);
});

test("watchlist players rank by ppg with the required title", () => {
  const got = buildWatchItems([
    watch("player", "Mara Voss", { found: true, player: "Mara Voss", team: "SPR", ppg: 18.2 }),
    watch("player", "Theo Lindqvist", { found: true, player: "Theo Lindqvist", team: "QZT", ppg: 24.65 }),
  ]);
  assert.equal(got.length, 2);
  // API order stays; ranks follow ppg.
  assert.equal(got[0].rankLabel, "#2");
  assert.equal(got[0].rankTitle, "Ranked #2 of 2 watched players by PPG");
  assert.equal(got[0].statText, "18.2 ppg");
  assert.equal(got[1].rankLabel, "#1");
  assert.equal(got[1].rankTitle, "Ranked #1 of 2 watched players by PPG");
  assert.equal(got[1].statText, "24.6 ppg");
});

test("watchlist drops found=false rows and empty snapshots", () => {
  const got = buildWatchItems([
    watch("player", "Ghost One", { found: false, player: "Ghost One", ppg: 30 }),
    watch("player", "Ghost Two", { found: true }),
    watch("team", "Ghost Three", { found: true }),
    watch("player", "", { found: true, ppg: 20 }),
    watch("team", "VX", { found: true, name: "Vexford", record: "12-5", wins: 12, losses: 5 }),
  ]);
  assert.equal(got.length, 1);
  assert.equal(got[0].name, "Vexford");
  assert.equal(got[0].statText, "12-5");
  assert.equal(got[0].rankLabel, "#1");
  assert.equal(got[0].rankTitle, "Ranked #1 of 1 watched teams by wins");
  assert.equal(got[0].question, "How is Vexford playing at 12-5?");
});

test("watchlist falls back to W-L when no record string exists", () => {
  const [item] = buildWatchItems([
    watch("team", "KL", { found: true, name: "Kingsport", wins: 9, losses: 8 }),
  ]);
  assert.equal(item.statText, "9-8");
});

test("watchlist caps at 4 combined", () => {
  const rows: WatchItem[] = [1, 2, 3, 4, 5, 6].map((n) =>
    watch("player", `Player ${n}`, { found: true, player: `Player ${n}`, ppg: 10 + n }),
  );
  assert.equal(buildWatchItems(rows).length, FEED_WATCH_CAP);
  assert.equal(FEED_WATCH_CAP, 4);
});

test("buildFeedItems orders movers, streaks, then watchlist", () => {
  const got = buildFeedItems({
    movers: { climbers: [mover("Mara Voss", { rank_change: 1, pts_change: 1 })], fallers: [], new_entries: [] },
    streaks: [streak("SPR")],
    watchlist: [watch("player", "Theo Lindqvist", { found: true, player: "Theo Lindqvist", ppg: 20 })],
  });
  assert.deepEqual(got.map((g) => g.kind), ["mover", "streak", "watchlist"]);
});

test("generated copy never uses evaluative or infrastructure words", () => {
  const banned = [
    "hot", "surging", "elite", "cold", "struggling", "trusted", "tier", "badge",
    "freshness", "system status", "sync", "pipeline", "endpoint", "cache",
    "Data through", "Data freshness",
  ];
  const got = buildFeedItems({
    movers: {
      climbers: [mover("Mara Voss", { rank_now: 2, rank_change: 5, pts_change: 3.1 })],
      fallers: [mover("Theo Lindqvist", { rank_change: -4, pts_change: -2.2 })],
      new_entries: [{ player: "June Park", pts: 21.5, rank: 11 }],
    },
    streaks: [streak("SPR", { STREAK: "W5", W: 12, L: 5 })],
    watchlist: [
      watch("player", "Silas Reed", { found: true, player: "Silas Reed", ppg: 19.9 }),
      watch("team", "QZT", { found: true, name: "Quizport", record: "11-6", wins: 11 }),
    ],
  });
  assert.ok(got.length > 0);
  for (const item of got) {
    const text = `${item.statText} ${item.rankLabel} ${item.rankTitle} ${item.question ?? ""}`.toLowerCase();
    for (const word of banned) {
      assert.ok(!text.includes(word.toLowerCase()), `${word} in ${text}`);
    }
  }
});

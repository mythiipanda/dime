



import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildFeedExpansion,
  buildFeedItems,
  buildMoverItems,
  buildStreakItems,
  buildWatchItems,
  FEED_MOVER_CAP,
  FEED_STREAK_CAP,
  FEED_WATCH_CAP,
  FEED_DEFAULT_VISIBLE,
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

test("streaks spell out the streak with the record and no question", () => {
  const got = buildStreakItems([
    streak("SPR", { W: 12, L: 5, STREAK: "W5" }),
    streak("QZT", { W: 8, L: 9, STREAK: "L3" }),
  ]);
  assert.equal(got[0].statText, "won 5 straight · 12-5");
  assert.equal(got[0].rankLabel, "#1");
  assert.equal(got[0].rankTitle, "Ranked #1 of 2 team streaks");
  assert.equal(got[0].question, null);
  assert.equal(got[1].statText, "lost 3 straight · 8-9");
  assert.equal(got[1].question, null);
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
  assert.equal(got[0].question, null);
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

function sevenStreaks(): TeamStreak[] {
  return [1, 2, 3, 4, 5, 6, 7].map((n) =>
    streak("NXV", { W: 9 + n, L: 5, STREAK: `W${n}` }),
  );
}

test("expansion caps 7 streaks to 4 visible with 3 extra and total 7", () => {
  const expansion = buildFeedExpansion({ streaks: sevenStreaks() });
  assert.equal(expansion.visible.length, 4);
  assert.ok(expansion.visible.every((i) => i.kind === "streak"));
  assert.equal(expansion.extra.length, 3);
  assert.equal(expansion.total, 7);
  const seventh = expansion.extra[2];
  assert.equal(seventh.rankLabel, "#7");
  assert.equal(seventh.rankTitle, "Ranked #7 of 7 team streaks");
});

test("expansion visible plus extra reaches every streak rank 1..7", () => {
  const expansion = buildFeedExpansion({ streaks: sevenStreaks() });
  const ranks = [...expansion.visible, ...expansion.extra].map((i) => i.rankLabel);
  assert.deepEqual(ranks, ["#1", "#2", "#3", "#4", "#5", "#6", "#7"]);
});

test("expansion visible is the first 5 feed items", () => {
  const input = {
    movers: [1, 2, 3, 4, 5, 6, 7].map((n) =>
      todayMover(`Player ${n}`, { RANK_CHANGE: "+1", PTS_CHANGE: 1.1 }),
    ),
    streaks: sevenStreaks(),
    watchlist: [1, 2, 3, 4, 5].map((n) =>
      watch("player", `Player ${n}`, { found: true, player: `Player ${n}`, ppg: 10 + n }),
    ),
  };
  const expansion = buildFeedExpansion(input);
  assert.deepEqual(expansion.visible, buildFeedItems(input).slice(0, FEED_DEFAULT_VISIBLE));
  assert.equal(expansion.visible.length, FEED_DEFAULT_VISIBLE);
  assert.deepEqual(
    [...expansion.visible, ...expansion.extra].slice(0, buildFeedItems(input).length),
    buildFeedItems(input),
  );
});

test("expansion with 3 streaks has no extra and total 3", () => {
  const expansion = buildFeedExpansion({
    streaks: [1, 2, 3].map((n) => streak("NXV", { STREAK: `W${n}` })),
  });
  assert.equal(expansion.visible.length, 3);
  assert.deepEqual(expansion.extra, []);
  assert.equal(expansion.total, 3);
});

test("buildFeedItems output unchanged for a mixed input", () => {
  const got = buildFeedItems({
    movers: { climbers: [mover("Mara Voss", { rank_change: 1, pts_change: 1 })], fallers: [], new_entries: [] },
    streaks: [streak("NXV")],
    watchlist: [watch("player", "Theo Lindqvist", { found: true, player: "Theo Lindqvist", ppg: 20 })],
  });
  assert.deepEqual(got.map((g) => g.kind), ["mover", "streak", "watchlist"]);
  assert.equal(got[0].statText, "up 1 spot, +1.0 pts");
  assert.equal(got[0].rankTitle, "Ranked #1 of 1 movers by points per game");
  assert.equal(got[1].statText, "won 3 straight · 10-5");
  assert.equal(got[1].rankTitle, "Ranked #1 of 1 team streaks");
  assert.equal(got[2].statText, "20.0 ppg");
  assert.equal(got[2].rankTitle, "Ranked #1 of 1 watched players by PPG");
});

test("expansion extra includes the 6th and 7th movers when movers exceed cap", () => {
  const rows = [1, 2, 3, 4, 5, 6, 7].map((n) =>
    todayMover(`Player ${n}`, { RANK_CHANGE: "+1", PTS_CHANGE: 1.1 }),
  );
  const expansion = buildFeedExpansion({ movers: rows });
  assert.equal(expansion.visible.length, FEED_DEFAULT_VISIBLE);
  assert.equal(expansion.extra.length, 2);
  assert.equal(expansion.extra[0].name, "Player 6");
  assert.equal(expansion.extra[1].name, "Player 7");
  assert.equal(expansion.extra[1].rankLabel, "#7");
  assert.equal(expansion.extra[1].rankTitle, "Ranked #7 of 7 movers by points per game");
  assert.equal(expansion.total, 7);
});

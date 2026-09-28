// Tests for data-driven Explore quick-ask starters (redesign Phase C).
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildQuickStarters, watchDisplayName } from "./quickStart";
import type { WatchItem } from "./api";

const playerItem = (player: string): WatchItem => ({
  entity_type: "player",
  entity_id: "x",
  snapshot: { player },
});
const teamItem = (team: string): WatchItem => ({
  entity_type: "team",
  entity_id: "y",
  snapshot: { team },
});

test("watchDisplayName prefers snapshot player/team over entity id", () => {
  assert.equal(watchDisplayName(playerItem("A Player")), "A Player");
  assert.equal(watchDisplayName(teamItem("Some Team")), "Some Team");
  assert.equal(
    watchDisplayName({ entity_type: "player", entity_id: "p-9", snapshot: {} }),
    "p-9",
  );
});

test("watchlist players come first, then movers fill the remaining slots", () => {
  const got = buildQuickStarters({
    watchlist: [playerItem("A Player"), playerItem("B Player")],
    climbers: [{ player: "C Player", rank_change: 4 }],
    streaks: [{ TEAM: "OKC", STREAK: "W5" }],
  });
  assert.equal(got.length, 3);
  assert.equal(got[0].label, "Watchlist");
  assert.ok(got[0].question.includes("A Player"));
  assert.equal(got[1].label, "Watchlist");
  assert.ok(got[1].question.includes("B Player"));
  assert.equal(got[2].label, "Movers");
  assert.ok(got[2].question.includes("C Player"));
});

test("team watchlist items ask a team question", () => {
  const got = buildQuickStarters({ watchlist: [teamItem("Some Team")] });
  assert.equal(got[0].label, "Watchlist");
  assert.ok(got[0].question.includes("Some Team"));
  assert.ok(got[0].question.includes("performing this season"));
});

test("streak starter names the team and streak length", () => {
  const got = buildQuickStarters({ streaks: [{ TEAM: "OKC", STREAK: "W5" }] });
  assert.equal(got.length, 1);
  assert.equal(got[0].label, "Streaks");
  assert.equal(
    got[0].question,
    "What is behind OKC's 5-game winning streak?",
  );
});

test("losing streaks parse too, and malformed streaks are skipped", () => {
  const got = buildQuickStarters({
    streaks: [{ TEAM: "WAS", STREAK: "L4" }, { TEAM: "X", STREAK: "?" }],
  });
  assert.equal(got.length, 1);
  assert.ok(got[0].question.includes("4-game losing streak"));
});

test("cap is 3 even with a full watchlist, movers, and streaks", () => {
  const got = buildQuickStarters({
    watchlist: [playerItem("A"), playerItem("B"), playerItem("C")],
    climbers: [{ player: "D" }],
    streaks: [{ TEAM: "OKC", STREAK: "W5" }],
  });
  assert.equal(got.length, 3);
  assert.deepEqual(
    got.map((s) => s.label),
    ["Watchlist", "Watchlist", "Movers"],
  );
});

test("nameless movers are skipped", () => {
  const got = buildQuickStarters({ climbers: [{ rank_change: 2 }] });
  assert.equal(got.length, 1);
  assert.equal(got[0].label, "Ask");
});

test("empty input falls back to one generic starter", () => {
  const got = buildQuickStarters({});
  assert.equal(got.length, 1);
  assert.equal(got[0].label, "Ask");
  assert.ok(got[0].question.length > 10);
});

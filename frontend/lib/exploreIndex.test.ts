// Tests for the Explore overview index card summaries (redesign Phase B).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  combineSummary,
  countPlayoffGames,
  fetchIndexSummaries,
  formatStat,
  playoffChampion,
  topLeaders,
} from "./exploreIndex";

test("topLeaders picks the top 3 by value, desc", () => {
  const rows = [
    { PLAYER_NAME: "B Player", PTS: 28.4 },
    { PLAYER_NAME: "A Player", PTS: 32.1 },
    { PLAYER_NAME: "D Player", PTS: 24.0 },
    { PLAYER_NAME: "C Player", PTS: 30.2 },
  ];
  const got = topLeaders(rows, "PTS");
  assert.deepEqual(
    got.map((l) => l.name),
    ["A Player", "C Player", "B Player"],
  );
  assert.deepEqual(
    got.map((l) => l.rank),
    [1, 2, 3],
  );
  assert.equal(got[0].value, "32.1");
});

test("topLeaders tolerates the alternate PLAYER key and integer values", () => {
  const rows = [
    { PLAYER: "X", PTS: 30 },
    { PLAYER: "Y", PTS: 29 },
  ];
  const got = topLeaders(rows, "PTS");
  assert.equal(got[0].name, "X");
  assert.equal(got[0].value, "30");
  assert.equal(formatStat(28.45), "28.4");
});

test("topLeaders drops rows with no name or non-numeric value", () => {
  const rows = [
    { PLAYER_NAME: "", PTS: 40 },
    { PLAYER_NAME: "Ghost", PTS: "40" },
    { PLAYER_NAME: "Real", PTS: 20 },
  ];
  const got = topLeaders(rows, "PTS");
  assert.equal(got.length, 1);
  assert.equal(got[0].name, "Real");
});

test("topLeaders returns [] on empty input", () => {
  assert.deepEqual(topLeaders([], "PTS"), []);
});

test("playoffChampion finds the decided Finals winner", () => {
  // NBA playoff ids carry the round at chars 6-7 ("04" = Finals).
  const rows: Record<string, unknown>[] = [];
  for (let i = 1; i <= 7; i++) {
    const id = `004250040${i}`;
    rows.push({
      GAME_ID: id,
      TEAM_ABBREVIATION: "OKC",
      TEAM_NAME: "Oklahoma City Thunder",
      WL: i <= 4 ? "W" : "L",
    });
    rows.push({
      GAME_ID: id,
      TEAM_ABBREVIATION: "IND",
      TEAM_NAME: "Indiana Pacers",
      WL: i <= 4 ? "L" : "W",
    });
  }
  const got = playoffChampion(rows);
  assert.ok(got);
  assert.equal(got!.champion, "Oklahoma City Thunder");
  assert.equal(got!.runnerUp, "Indiana Pacers");
  assert.equal(got!.series, "4-3");
});

test("playoffChampion is null before the Finals are decided", () => {
  const rows = [
    { GAME_ID: "0042500401", TEAM_ABBREVIATION: "OKC", TEAM_NAME: "Thunder", WL: "W" },
    { GAME_ID: "0042500401", TEAM_ABBREVIATION: "IND", TEAM_NAME: "Pacers", WL: "L" },
  ];
  assert.equal(playoffChampion(rows), null);
  assert.equal(playoffChampion([]), null);
});

test("countPlayoffGames counts distinct game ids, 0 when empty", () => {
  const rows = [
    { GAME_ID: "0042500401", TEAM_ABBREVIATION: "OKC" },
    { GAME_ID: "0042500401", TEAM_ABBREVIATION: "IND" },
    { GAME_ID: "0042500402", TEAM_ABBREVIATION: "OKC" },
    { TEAM_ABBREVIATION: "NOP" },
  ];
  assert.equal(countPlayoffGames(rows), 2);
  assert.equal(countPlayoffGames([]), 0);
});

test("combineSummary reports the prospect count, null when empty", () => {
  assert.equal(combineSummary([{}, {}, {}], "2025"), "3 prospects · 2025 class");
  assert.equal(combineSummary([], "2025"), null);
});

// fetchIndexSummaries: each dataset fetch is isolated (allSettled), so one
// failed request never blanks the cards whose data arrived fine.

function okRows(data: Record<string, unknown>[]) {
  return { ok: true, data };
}

function finalsRows(): Record<string, unknown>[] {
  const rows: Record<string, unknown>[] = [];
  for (let i = 1; i <= 4; i++) {
    rows.push({
      GAME_ID: `004250040${i}`,
      TEAM_ABBREVIATION: "OKC",
      TEAM_NAME: "Oklahoma City Thunder",
      WL: "W",
    });
    rows.push({
      GAME_ID: `004250040${i}`,
      TEAM_ABBREVIATION: "IND",
      TEAM_NAME: "Indiana Pacers",
      WL: "L",
    });
  }
  return rows;
}

const GOOD = {
  leaders: okRows([
    { PLAYER_NAME: "A Player", PTS: 32.1 },
    { PLAYER_NAME: "B Player", PTS: 30.2 },
  ]),
  playoffs: okRows(finalsRows()),
  combine: okRows([{}, {}, {}]),
};

test("fetchIndexSummaries builds all summaries when every fetch succeeds", async () => {
  const got = await fetchIndexSummaries(async (name) => GOOD[name as keyof typeof GOOD], "2025-26");
  assert.deepEqual(got.leaders, ["1. A Player — 32.1", "2. B Player — 30.2"]);
  assert.deepEqual(got.playoffs, ["Oklahoma City Thunder · 4-0 over Indiana Pacers"]);
  assert.deepEqual(got.draft, ["3 prospects · 2025 class"]);
});

test("fetchIndexSummaries isolates a rejected fetch: other cards still render", async () => {
  const got = await fetchIndexSummaries(async (name) => {
    if (name === "leaders") throw new Error("network down");
    return GOOD[name as keyof typeof GOOD];
  }, "2025-26");
  assert.equal(got.leaders, undefined);
  assert.deepEqual(got.playoffs, ["Oklahoma City Thunder · 4-0 over Indiana Pacers"]);
  assert.deepEqual(got.draft, ["3 prospects · 2025 class"]);
});

test("fetchIndexSummaries treats ok:false like a failure, keeps the rest", async () => {
  const got = await fetchIndexSummaries(async (name) => {
    if (name === "playoffs") return { ok: false, error: "500" };
    return GOOD[name as keyof typeof GOOD];
  }, "2025-26");
  assert.deepEqual(got.leaders, ["1. A Player — 32.1", "2. B Player — 30.2"]);
  assert.equal(got.playoffs, undefined);
  assert.deepEqual(got.draft, ["3 prospects · 2025 class"]);
});

test("fetchIndexSummaries returns {} when every fetch rejects", async () => {
  const got = await fetchIndexSummaries(async () => {
    throw new Error("backend unreachable");
  }, "2025-26");
  assert.deepEqual(got, {});
});

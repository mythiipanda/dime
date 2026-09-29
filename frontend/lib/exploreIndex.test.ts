
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  combineSummary,
  countPlayoffGames,
  fetchIndexSummaries,
  formatStat,
  lineupsHeadline,
  playoffChampion,
  shotsHeadline,
  shortPlayerName,
  topLeaders,
  tradeHeadline,
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



test("shotsHeadline reports the charted count, null when empty", () => {
  assert.equal(shotsHeadline("A Player", 412), "A Player · 412 shots charted");
  assert.equal(shotsHeadline("", 412), null);
  assert.equal(shotsHeadline("A Player", 0), null);
  assert.equal(shotsHeadline("A Player", NaN), null);
});

test("shortPlayerName shortens to initial plus surname", () => {
  assert.equal(shortPlayerName("LeBron James"), "L. James");
  assert.equal(shortPlayerName("  Luka   Doncic  "), "L. Doncic");
  assert.equal(shortPlayerName("Giannis"), "Giannis");
});

test("lineupsHeadline names the most-used unit and its minutes", () => {
  const rows = [
    { GROUP_NAME: "A One - B Two - C Three - D Four - E Five", MIN: 120.4 },
    { GROUP_NAME: "F Six - G Seven - H Eight - I Nine - J Ten", MIN: 240.7 },
  ];
  assert.equal(
    lineupsHeadline("BOS", rows),
    "BOS · F. Six, G. Seven, H. Eight, I. Nine, J. Ten · 241 min",
  );
  assert.equal(lineupsHeadline("BOS", []), null);
  assert.equal(lineupsHeadline("", rows), null);
  assert.equal(lineupsHeadline("BOS", [{ GROUP_NAME: "", MIN: 10 }]), null);
});

test("tradeHeadline reports both payrolls, null when either is missing", () => {
  const v = {
    team_a: { team: "LAL", payroll: 178_400_000 },
    team_b: { team: "DEN", payroll: 182_100_000 },
  };
  assert.equal(tradeHeadline(v), "LAL $178.4M · DEN $182.1M");
  assert.equal(tradeHeadline(null), null);
  assert.equal(
    tradeHeadline({ team_a: { team: "LAL" }, team_b: { team: "DEN", payroll: 1 } }),
    null,
  );
});

test("fetchIndexSummaries adds shots/trade/lineups cards from the extra callbacks", async () => {
  const got = await fetchIndexSummaries(
    async (name) => GOOD[name as keyof typeof GOOD],
    "2025-26",
    {
      topScorerShots: async () => ({ name: "A Player", count: 300 }),
      tradeCheck: async () => ({
        team_a: { team: "LAL", payroll: 178_400_000 },
        team_b: { team: "DEN", payroll: 182_100_000 },
      }),
      defaultLineups: async () => ({
        team: "BOS",
        rows: [{ GROUP_NAME: "A One - B Two - C Three - D Four - E Five", MIN: 200 }],
      }),
    },
  );
  assert.deepEqual(got.shots, ["A Player · 300 shots charted"]);
  assert.deepEqual(got.trade, ["LAL $178.4M · DEN $182.1M"]);
  assert.deepEqual(got.lineups, [
    "BOS · A. One, B. Two, C. Three, D. Four, E. Five · 200 min",
  ]);
});

test("fetchIndexSummaries isolates a failing extra callback: other cards still render", async () => {
  const got = await fetchIndexSummaries(
    async (name) => GOOD[name as keyof typeof GOOD],
    "2025-26",
    {
      topScorerShots: async () => {
        throw new Error("resolve down");
      },
      tradeCheck: async () => null,
      defaultLineups: async () => ({ team: "BOS", rows: [] }),
    },
  );
  assert.equal(got.shots, undefined);
  assert.equal(got.trade, undefined);
  assert.equal(got.lineups, undefined);
  assert.deepEqual(got.leaders, ["1. A Player — 32.1", "2. B Player — 30.2"]);
});

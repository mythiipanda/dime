// Tests for the leaders rank/percentile helper (redesign Phase 2).
import { test } from "node:test";
import assert from "node:assert/strict";
import { rankOf } from "./rankContext";

const ROWS = [
  { PLAYER_NAME: "A Player", TEAM: "BOS", PTS: 32.1 },
  { PLAYER_NAME: "B Player", TEAM: "DEN", PTS: 30.2 },
  { PLAYER_NAME: "C Player", TEAM: "OKC", PTS: 28.4 },
  { PLAYER_NAME: "D Player", TEAM: "NYK", PTS: 27.9 },
  { PLAYER_NAME: "E Player", TEAM: "LAL", PTS: 26.5 },
];

test("rankOf returns the 1-based position in the returned list", () => {
  assert.deepEqual(
    ROWS.map((_, i) => rankOf(i, ROWS.length).rank),
    [1, 2, 3, 4, 5],
  );
});

test("percentile follows (total - rank) / (total - 1) * 100, rounded", () => {
  assert.equal(rankOf(0, 10).percentile, 100);
  assert.equal(rankOf(9, 10).percentile, 0);
  assert.equal(rankOf(2, 10).percentile, 78);
});

test("a single-row list is the 100th percentile", () => {
  const got = rankOf(0, 1);
  assert.equal(got.rank, 1);
  assert.equal(got.percentile, 100);
});

test("ties keep position-based ranks, no averaging", () => {
  const tied = [
    { PLAYER_NAME: "A Player", TEAM: "BOS", PTS: 30.0 },
    { PLAYER_NAME: "B Player", TEAM: "DEN", PTS: 30.0 },
    { PLAYER_NAME: "C Player", TEAM: "OKC", PTS: 30.0 },
  ];
  assert.deepEqual(
    tied.map((_, i) => rankOf(i, tied.length).rank),
    [1, 2, 3],
  );
});

test("chip renders the rank with a # prefix", () => {
  assert.equal(rankOf(0, 10).chip, "#1");
  assert.equal(rankOf(2, 10).chip, "#3");
  assert.equal(rankOf(9, 10).chip, "#10");
});

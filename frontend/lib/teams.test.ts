// Tests for the shared team lookup table (lib/teams).
import { test } from "node:test";
import assert from "node:assert/strict";
import { abbrForTeamId, isTeamAbbr, TEAM_IDS } from "./teams";

test("abbrForTeamId inverts the table by numeric id", () => {
  assert.equal(abbrForTeamId(1610612738), "BOS");
  assert.equal(abbrForTeamId("1610612747"), "LAL");
  assert.equal(abbrForTeamId(0), null);
  assert.equal(abbrForTeamId("nope"), null);
});

test("the table covers 30 teams", () => {
  assert.equal(Object.keys(TEAM_IDS).length, 30);
});

test("isTeamAbbr matches case-insensitively", () => {
  assert.equal(isTeamAbbr("bos"), true);
  assert.equal(isTeamAbbr("BOS"), true);
  assert.equal(isTeamAbbr("XX"), false);
});

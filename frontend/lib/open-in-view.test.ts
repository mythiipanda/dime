import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { viewTargetForArtifact } from "./open-in-view";
import type { DimeArtifact } from "./dime-stream";

function tableArtifact(source: string, title: string, rows: (string | number)[][] = []): DimeArtifact {
  return {
    kind: "table",
    title,
    source,
    columns: [{ key: "a", label: "A" }],
    rows,
  };
}

describe("viewTargetForArtifact", () => {
  it("maps cap tools to the cap view", () => {
    for (const tool of ["get_cap_table", "get_cap_ledger", "get_cap_scenario"]) {
      const target = viewTargetForArtifact(tableArtifact(tool, "Cap ledger"));
      assert.equal(target?.tab, "cap");
    }
  });

  it("maps trade tools to the trades view", () => {
    for (const tool of ["get_trade_check", "get_trade_value", "get_trade_legality"]) {
      const target = viewTargetForArtifact(tableArtifact(tool, "Trade check"));
      assert.equal(target?.tab, "trades");
    }
  });

  it("reads the tool head before the provenance separator", () => {
    const target = viewTargetForArtifact(tableArtifact("get_cap_ledger · silver_salaries", "x"));
    assert.equal(target?.tab, "cap");
  });

  it("returns null for tools without a view home", () => {
    assert.equal(viewTargetForArtifact(tableArtifact("get_standings", "Standings")), null);
    assert.equal(viewTargetForArtifact(tableArtifact(undefined as never, "No source")), null);
  });

  it("extracts the team from the artifact title", () => {
    const target = viewTargetForArtifact(tableArtifact("get_cap_ledger", "Boston Celtics BOS cap ledger"));
    assert.equal(target?.team, "BOS");
  });

  it("extracts the team from table rows when the title lacks one", () => {
    const target = viewTargetForArtifact(tableArtifact(
      "get_trade_check", "Trade check result",
      [["team", "LAL"], ["out", 10000000]]));
    assert.equal(target?.team, "LAL");
  });

  it("ignores lowercase substrings and non-team uppercase words", () => {
    const target = viewTargetForArtifact(tableArtifact("get_cap_ledger", "Cap minimum discussion THE END"));
    assert.equal(target?.team, undefined);
  });

  it("maps matchup/scout tools to their views with team", () => {
    const matchup = viewTargetForArtifact(tableArtifact("get_matchup_preview", "DEN at MIN preview"));
    assert.equal(matchup?.tab, "matchups");
    assert.equal(matchup?.team, "DEN");
    const scout = viewTargetForArtifact(tableArtifact("get_scout_pack", "Scout pack: PHI"));
    assert.equal(scout?.tab, "scout");
    assert.equal(scout?.team, "PHI");
  });

  it("maps award and compare tools without a team", () => {
    const awards = viewTargetForArtifact(tableArtifact("get_award_race", "MVP race"));
    assert.equal(awards?.tab, "awards");
    assert.equal(awards?.team, undefined);
    const compare = viewTargetForArtifact(tableArtifact("get_comps", "Comps for player"));
    assert.equal(compare?.tab, "compare");
  });

  it("uses the team_card name when present", () => {
    const card: DimeArtifact = {
      kind: "team_card",
      title: "Team card",
      source: "get_cap_table",
      teamName: "Denver Nuggets DEN",
      sourceRef: "r1",
      sourceRow: 0,
      nameColumn: "TEAM",
      metrics: [],
    };
    const target = viewTargetForArtifact(card);
    assert.equal(target?.team, "DEN");
  });
});

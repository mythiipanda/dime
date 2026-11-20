import { ACTIVITY_CONTRACT_FIXTURE } from "./activity";

const answer = "## Make Denver defend in space\n\nOklahoma City’s synthetic net rating of 9.4 is a starting point, not a complete scouting recommendation.\n\n- **Create space.** Keep a shooter in the weak-side corner.\n- **Test the bench.** Compare second-unit combinations before changing the rotation.\n- **Know the limits.** Tracking-level matchup and injury data are missing.\n\nAll statistics in this development replay are synthetic, not current warehouse evidence.";

export const scoutingQuestion = "Where does Oklahoma City have an edge against Denver?";
export const scoutingEvents: { type: string; data: Record<string, unknown> }[] = [
  ...ACTIVITY_CONTRACT_FIXTURE.map(({ type, ...data }) => ({ type: String(type), data: { ...data, node: "analytics" } })),
  { type: "custom_data", data: { node: "analytics", tables: [
    { tool: "team_ratings", rows: [{ Team: "Oklahoma City", GP: 82, "Off rating": 119.8, "Def rating": 110.4, "Net rating": 9.4 }, { Team: "Denver", GP: 82, "Off rating": 118.2, "Def rating": 113.6, "Net rating": 4.6 }], meta: { source: "Synthetic development fixture", season: "2025-26", qualification: "Replay only; not real warehouse statistics" } },
    { tool: "team_ratings", output_id: "NET_RATING", subject_type: "team", subject_id: "OKC", value: "9.4", unit: "points_per_100_possessions", provenance: { capability: "team_ratings", season: "2025-26", source: "Synthetic development fixture" } },
  ] } },
  ...answer.match(/[\s\S]{1,110}(?:\s|$)/g)!.map((text) => ({ type: "token", data: { text } })),
  { type: "final_answer", data: { text: answer, carry: { run_id: "dev-replay-scouting", verification: "pass", verified_claims: 1 } } },
  { type: "graph_end", data: {} },
];
=======
export const scoutingEvents: [string, unknown][] = [
  ["status", { text: "Reading player evidence" }],
  ["tool_call", { event_id: "replay-tool", name: "player_season", data: { player: "Shai Gilgeous-Alexander" } }],
  ["tool_result", { event_id: "replay-tool", name: "player_season", rows: 1, ms: 86 }],
  ["token", { text: "## A lead creator to build around\n\n" }],
  ["token", { text: "Gilgeous-Alexander pairs high-volume scoring with efficient decision-making. " }],
  ["custom_data", { node: "analytics", artifacts: [{ kind: "table", title: "Illustrative player season", columns: [{ key: "player", label: "Player" }, { key: "gp", label: "GP", numeric: true }, { key: "ppg", label: "PPG", numeric: true }, { key: "ts", label: "TS%", numeric: true }], rows: [["Shai Gilgeous-Alexander", "76", "32.7", "63.7%"]] }] }],
  ["final_answer", {
    text: "## A lead creator to build around\n\nGilgeous-Alexander averaged 32.7 points per game with 63.7% true shooting in this illustrative scouting sample.",
    carry: {
      verification: "partial", verified_claims: 0, gaps: [], run_id: "development-scouting-replay",
      source_refs: ["replay-player"],
      sources: [{ ref: "replay-player", tool: "player_season", response: { content: [{ type: "text", text: JSON.stringify({ rows: [{ PLAYER: "Shai Gilgeous-Alexander", GP: 76, PPG: 32.7, TS_PCT: 0.637 }], declared_column_semantics: { GP: { unit: "games" }, PPG: { unit: "points/game" }, TS_PCT: { unit: "ratio" } }, meta: { tables: ["Player season · illustrative replay"], season: "2024-25", source: "Development fixture, not live data", table: "player_season" } }) }] } }],
      submission: { blocks: [{ text: "Gilgeous-Alexander averaged 32.7 points per game with 63.7% true shooting in this illustrative scouting sample.", anchors: [{ ref: "replay-player", row: 0, columns: ["PPG", "TS_PCT"] }] }] },
    },
    suggestions: ["Compare his creation load with another lead guard"],
  }],
  ["graph_end", {}],
];
>>>>>>> origin/dev

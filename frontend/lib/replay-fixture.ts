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

import type { DimeArtifact, PlayerCardArtifactPayload } from "./dime-stream";

export const playerCardFixture: PlayerCardArtifactPayload = {
  kind: "player_card", title: "Illustrative player snapshot", playerName: "Alex Example", team: "Fixture City",
  sourceRef: "design-player-fixture", sourceRow: 0, nameColumn: "player", teamColumn: "team",
  provenance: { origin: "undeclared", capability: "Design fixture · no live query", season: "Illustrative season", liveSources: [] },
  metrics: [
    { column: "points", label: "Scoring", value: 24.6, unit: "points/game" },
    { column: "assists", label: "Playmaking", value: 7.2, unit: "assists/game" },
    { column: "ts", label: "True shooting", value: 0.612, unit: "ratio" },
    { column: "games", label: "Sample", value: 48, unit: "games" },
    { column: "missed", label: "Missed games", value: 0, unit: "games" },
    { column: "impact", label: "Impact", value: null },
  ],
};

export const generativeFixtures: DimeArtifact[] = [
  playerCardFixture,
  { kind: "chart", title: "Illustrative scoring trend", unit: "points/game", xLabels: ["Oct", "Nov", "Dec", "Jan", "Feb"], series: [
    { name: "Alex Example", values: [22.4, 24.1, null, 25.6, 24.6], tone: "accent" },
    { name: "Blake Example", values: [20.1, 21.8, 23.2, 22.8, 23.5], tone: "muted" },
  ], footnote: "Fictional values. December is missing, not zero." },
  { kind: "chart", title: "Illustrative cap-space leaderboard", subtitle: "Practical space vs the fictional max slot · fixture", variant: "bar", unit: "$M",
    xLabels: ["Fixture A", "Fixture B", "Fixture C", "Fixture D", "Fixture E", "Fixture F"],
    xLabel: "Practical cap space",
    series: [{ name: "Illustrative space", values: [74.2, 63.1, 58.7, 55.9, 54.6, 41.5], tone: "accent" }],
    marks: [{ value: 54.45, label: "Max-slot threshold" }],
    annotations: [{ index: 4, text: "Last fixture that clears a full max slot" }],
    labelValues: true,
    footnote: "Fictional values. 6 fixtures shown of 30." },
  { kind: "table", title: "Illustrative shortlist", columns: [{ key: "player", label: "Player" }, { key: "points", label: "Points/game", numeric: true }, { key: "assists", label: "Assists/game", numeric: true }, { key: "impact", label: "Impact", numeric: true }], rows: [
    ["Alex Example", 24.6, 7.2, ""], ["Blake Example", 23.5, 5.8, 1.4], ["Casey Example", 18.2, 8.1, 0],
  ] },
  { kind: "compare", title: "Illustrative head-to-head", aName: "Alex Example", bName: "Blake Example", rows: [
    { label: "Points/game", a: 24.6, b: 23.5 }, { label: "Assists/game", a: 7.2, b: 5.8 }, { label: "True shooting", a: 61.2, b: 58.4 },
  ] },
  { kind: "scatter", title: "Illustrative usage vs efficiency", xLabel: "Usage rate", yLabel: "True shooting", xMid: 25, yMid: 58, points: [
    { label: "Alex Example", x: 31.2, y: 61.2, highlight: true }, { label: "Blake Example", x: 27.8, y: 58.4 },
    { label: "Casey Example", x: 22.1, y: 55.9 }, { label: "Drew Example", x: 19.4, y: 60.1 },
  ], footnote: "Fictional values. Above-right is high usage and high efficiency." },
  { kind: "shot_chart", title: "Illustrative shot profile", zones: [
    { x: 0, y: 0, att: 120, makes: 79, pct: 65.8, label: "Rim", delta: 3.1 },
    { x: -160, y: 60, att: 44, makes: 18, pct: 40.9, label: "Left mid", delta: -1.2 },
    { x: 160, y: 60, att: 38, makes: 15, pct: 39.5, label: "Right mid", delta: -2.6 },
    { x: -220, y: 230, att: 61, makes: 26, pct: 42.6, label: "Left three", delta: 4.4 },
    { x: 220, y: 230, att: 57, makes: 20, pct: 35.1, label: "Right three", delta: -3.1 },
    { x: 0, y: 300, att: 34, makes: 12, pct: 35.3, label: "Top three", delta: -2.0 },
  ], footnote: "Fictional zone data. Color marks zone fg% vs league average." },
  { kind: "team_card", title: "Illustrative team snapshot", teamName: "Fixture City", sourceRef: "design-team-fixture", sourceRow: 0, nameColumn: "team",
    provenance: { origin: "undeclared", capability: "Design fixture · no live query", season: "Illustrative season", liveSources: [] },
    metrics: [
      { column: "wins", label: "Wins", value: 41, unit: "games" },
      { column: "net_rtg", label: "Net rating", value: 2.4, unit: "per 100" },
      { column: "pace", label: "Pace", value: 99.8, unit: "poss/48" },
    ],
    sections: [
      { label: "Payroll", sourceRef: "design-cap-fixture", sourceRow: 0, metrics: [
        { column: "payroll", label: "Payroll", value: 172, unit: "$M" },
        { column: "apron_room", label: "Room below 1st apron", value: 6, unit: "$M" },
      ], fields: [{ column: "apron", label: "Apron status", value: "below first apron" }],
      provenance: { origin: "undeclared", capability: "Design fixture · no live query", season: "Illustrative season", liveSources: [] } },
      { label: "Four factors", sourceRef: "design-4f-fixture", sourceRow: 0, metrics: [
        { column: "efg", label: "eFG%", value: 55.1, unit: "%" },
        { column: "tov", label: "TOV%", value: 13.2, unit: "%" },
      ], provenance: { origin: "undeclared", capability: "Design fixture · no live query", season: "Illustrative season", liveSources: [] } },
    ] },
  { kind: "memo", title: "Illustrative scouting memo", subtitle: "Fixture City", text: "Fixture City outscores opponents behind rim pressure and corner shooting.",
    provenance: { origin: "undeclared", capability: "Design fixture · no live query", season: "Illustrative season", liveSources: [] },
    sections: [
      { heading: "Offense", body: "65.8% at the rim on this sample; the left wing three is the second-best look.", anchors: [{ ref: "design-fixture", row: 0, columns: ["zone", "pct"] }] },
      { heading: "Watchouts", body: "Midrange attempts are down but efficiency there lags both corners." },
    ],
    footnote: "Fictional memo. Section citations reference fixture rows only." },
];

export const generativeEvents: [string, unknown][] = [
  ["status", { text: "Reading illustrative source rows" }],
  ["tool_call", { event_id: "fx-t1", name: "get_leaders", data: { stat: "pts" } }],
  ["tool_call", { event_id: "fx-t2", name: "sql_exec", data: { sql: "select …" } }],
  ["tool_result", { event_id: "fx-t1", name: "get_leaders", status: "ok", rows: 48, ms: 210 }],
  ["tool_call", { event_id: "fx-t3", name: "get_shot_zones", data: { player: "Alex Example" } }],
  ["tool_result", { event_id: "fx-t2", name: "sql_exec", status: "ok", rows: 12, ms: 88 }],
  ["tool_result", { event_id: "fx-t3", name: "get_shot_zones", status: "ok", rows: 14, ms: 164 }],
  ["tool_call", { event_id: "fx-t4", name: "web_search", data: { query: "illustrative context" } }],
  ["tool_result", { event_id: "fx-t4", name: "web_search", status: "fail", error: "Fixture failure state" }],
  ["token", { text: "## Generative answer fixture\n\nFictional players and values. No provider or warehouse call was made.\n\nAlex Example has 24.6 points per game in this sample. Source values are not a verification.\n" }],
  ["custom_data", { artifacts: generativeFixtures }],
  ["final_answer", { text: "## Generative answer fixture\n\nFictional players and values. No provider or warehouse call was made.\n\nAlex Example has 24.6 points per game in this sample. Source values are not a verification.", carry: { verification: "unknown", verified_claims: 0, gaps: [] } }],
  ["graph_end", {}],
];

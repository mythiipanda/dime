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
  { kind: "table", title: "Illustrative shortlist", columns: [{ key: "player", label: "Player" }, { key: "points", label: "Points/game", numeric: true }, { key: "assists", label: "Assists/game", numeric: true }, { key: "impact", label: "Impact", numeric: true }], rows: [
    ["Alex Example", 24.6, 7.2, ""], ["Blake Example", 23.5, 5.8, 1.4], ["Casey Example", 18.2, 8.1, 0],
  ] },
];

export const generativeEvents: [string, unknown][] = [
  ["status", { text: "Reading illustrative source rows" }],
  ["token", { text: "## Generative answer fixture\n\nFictional players and values. No provider or warehouse call was made.\n\nAlex Example has 24.6 points per game in this sample. Source values are not a verification.\n" }],
  ["custom_data", { artifacts: generativeFixtures }],
  ["final_answer", { text: "## Generative answer fixture\n\nFictional players and values. No provider or warehouse call was made.\n\nAlex Example has 24.6 points per game in this sample. Source values are not a verification.", carry: { verification: "unknown", verified_claims: 0, gaps: [] } }],
  ["graph_end", {}],
];

import type { DimeArtifact, PlayerCardArtifactPayload } from "./dime-stream";

export const worstcasePlayerCard: PlayerCardArtifactPayload = {
  kind: "player_card", title: "Worst-case player snapshot", playerName: "Dikembe Mutombo Mpolondo Mukamba Jean-Jacques Wamutombo", team: "Valančiūnas Fixture-O'Neill",
  sourceRef: "worstcase-player-fixture", sourceRow: 0, nameColumn: "player", teamColumn: "team",
  provenance: { origin: "undeclared", capability: "Worst-case fixture · no live query", season: "Illustrative season", liveSources: [] },
  metrics: [
    { column: "points", label: "Scoring", value: 0, unit: "points/game" },
    { column: "plusminus", label: "Plus-minus", value: -482, unit: "total" },
    { column: "ts", label: "True shooting", value: 1, unit: "ratio" },
    { column: "games", label: "Sample", value: 1, unit: "games" },
    { column: "salary", label: "Salary", value: 55700000, unit: "usd_dollars" },
    { column: "impact", label: "Impact", value: null },
  ],
};

const bigRows: (string | number | null)[][] = Array.from({ length: 54 }, (_, i) => [
  i % 7 === 0 ? "Jonas Valančiūnas" : i % 5 === 0 ? "De'Aaron Fox" : `Fixture Player ${i + 1}`,
  Math.round((30 - i * 0.5) * 10) / 10,
  i % 3 === 0 ? null : Math.round(Math.random() * 0) + i % 9,
  i === 0 ? -482 : i === 1 ? 0 : i,
]);

export const worstcaseFixtures: DimeArtifact[] = [
  worstcasePlayerCard,
  { kind: "team_card", title: "Worst-case team snapshot", teamName: "Valančiūnas Fixture-O'Neill Long-Name Athletics", sourceRef: "worstcase-team-fixture", sourceRow: 0, nameColumn: "team",
    provenance: { origin: "undeclared", capability: "Worst-case fixture · no live query", season: "Illustrative season", liveSources: [] },
    metrics: [
      { column: "wins", label: "Wins", value: 82, unit: "games" },
      { column: "net_rtg", label: "Net rating", value: -13.4, unit: "per 100" },
      { column: "pace", label: "Pace", value: 108.9, unit: "poss/48" },
    ],
    sections: [
      { label: "Payroll", sourceRef: "worstcase-cap-fixture", sourceRow: 0, metrics: [
        { column: "payroll", label: "Payroll", value: 234, unit: "$M" },
        { column: "apron_room", label: "Room below 1st apron", value: 0, unit: "$M" },
      ], fields: [{ column: "apron", label: "Apron status", value: "hard-capped at the second apron with no exceptions remaining and a frozen first-round pick in 2032" }],
      provenance: { origin: "undeclared", capability: "Worst-case fixture · no live query", season: "Illustrative season", liveSources: [] } },
    ] },
  { kind: "compare", title: "Worst-case head-to-head", aName: "Nikola Jokić", bName: "Dikembe Mutombo Mpolondo Mukamba Jean-Jacques Wamutombo", rows: [
    { label: "Points/game", a: 0, b: 0 }, { label: "Plus-minus", a: -482, b: 523 }, { label: "True shooting", a: 100, b: 0 }, { label: "Games", a: 1, b: 82 },
  ] },
  { kind: "table", title: "Worst-case leaderboard (54 rows)", columns: [{ key: "player", label: "Player" }, { key: "points", label: "Points/game", numeric: true }, { key: "assists", label: "Assists/game", numeric: true }, { key: "plusminus", label: "Plus-minus", numeric: true }], rows: bigRows as (string | number)[][] },
  { kind: "table", title: "Worst-case empty table", columns: [{ key: "player", label: "Player" }, { key: "points", label: "Points/game", numeric: true }], rows: [] },
  { kind: "scatter", title: "Worst-case dense scatter (40 points)", xLabel: "Usage rate", yLabel: "True shooting", xMid: 25, yMid: 58, points: Array.from({ length: 40 }, (_, i) => ({
    label: `Fixture ${i + 1}`, x: 10 + (i * 37 % 30) + (i % 3) * 0.4, y: 48 + (i * 23 % 20) + (i % 2) * 0.3, highlight: i === 0,
  })), footnote: "Density probe. Labels should stay hover-only beyond 8 points." },
  { kind: "scatter", title: "Worst-case single-point scatter", xLabel: "Usage rate", yLabel: "True shooting", points: [
    { label: "Luka Dončić", x: 35.4, y: 60.1, highlight: true },
  ], footnote: "One-game sample. Degenerate axes are the probe." },
  { kind: "chart", title: "Worst-case scoring trend", unit: "points/game", xLabels: ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"], series: [
    { name: "Nikola Jokić", values: [0, null, 48.2, 0, 100, 3.1], tone: "accent" },
  ], footnote: "Extreme values probe: zero is real zero, null is missing." },
  { kind: "shot_chart", title: "Worst-case shot profile", zones: [
    { x: 0, y: 0, att: 1, makes: 1, pct: 100, label: "Rim", delta: 34.2 },
    { x: -220, y: 230, att: 9, makes: 0, pct: 0, label: "Left three", delta: -38.9 },
  ], footnote: "One-attempt and zero-makes zones. Extreme deltas probe color saturation." },
  { kind: "memo", title: "Worst-case scouting memo", subtitle: "Valančiūnas Fixture-O'Neill Long-Name Athletics", text: "A very long memo lead-in designed to probe wrapping behavior with an extended run of prose that keeps going well beyond what any reasonable summary should contain, because real model outputs sometimes produce exactly this kind of unedited verbosity when the steering is weak.",
    provenance: { origin: "undeclared", capability: "Worst-case fixture · no live query", season: "Illustrative season", liveSources: [] },
    sections: [
      { heading: "Offense", body: "Nikola Jokić, Jonas Valančiūnas, and Luka Dončić all appear here to probe unicode rendering inside prose sections." },
    ],
    footnote: "Fictional memo. Unicode probe." },
  { kind: "trade_verdict", title: "Worst-case illegal aggregation", legal: false, sourceRef: "worstcase-verdict-fixture",
    issues: ["Valančiūnas Fixture-O'Neill Long-Name Athletics takes back too much", "Aggregation is prohibited above the second apron for the 2026-27 season and this issue string is deliberately verbose to probe wrapping inside the issue list"],
    teams: [
      { team: "VFL", playersOut: ["Dikembe Mutombo Mpolondo Mukamba Jean-Jacques Wamutombo"], playersIn: ["Nikola Jokić", "Jonas Valančiūnas"], picksIn: [{ year: 2028, round: 1, protection: "top-3 protected through 2030 conveyance" }, { year: 2029, round: 2, swap: true }], outgoing: 18125000, incoming: 57078728, payrollBefore: 157719786, payrollAfter: 196675514, allowedIncoming: 27128000, matchRule: "outgoing salary plus $9.096M (below the first apron)", hardCap: "first apron", matchingFailed: true },
      { team: "PHX", playersOut: ["Nikola Jokić", "Jonas Valančiūnas"], playersIn: ["Dikembe Mutombo Mpolondo Mukamba Jean-Jacques Wamutombo"], outgoing: 57078728, incoming: 18125000, payrollBefore: 193393075, payrollAfter: 154439347, allowedIncoming: 57078728, matchRule: "100% of outgoing (above the first apron)", overApron1: true, overApron2: true, tpeCreation: { amount: 38953728, condition: "would generate only if this construction is executed as a non-simultaneous trade" } },
    ],
    checks: [
      { rule: "salary matching", note: "VFL incoming exceeds the band by $29.9M" },
      { rule: "second apron aggregation", note: "no aggregation above the second apron" },
    ],
    evaluationTool: "get_trade_check",
    provenance: { origin: "undeclared", capability: "Worst-case fixture · no live query", season: "Illustrative season", liveSources: [] } },
  { kind: "cap_summary", title: "Worst-case apron-crunch scenario", sourceRef: "worstcase-cap-fixture",
    team: "PHX", season: "2031-32",
    payrollBefore: 231440997654321, payrollAfter: 267440997654321, delta: 36000000000000,
    capRoom: 0, capRoomBefore: 0, taxRoom: -12000000, roomApron1: -30500000, roomApron2: -48600000,
    rosterBefore: 15, rosterAfter: 19,
    overTax: true, overApron1: true, overApron2: true, hardCap: "first apron",
    issues: ["roster would be 19 players - must trim to 15", "signing Jonas Valančiūnas Fixture-O'Neill for the full non-taxpayer midlevel exception is impossible while hard-capped at the first apron and this issue string is deliberately verbose to probe wrapping inside the issue list"],
    steps: [
      { kind: "payroll", detail: "PHX committed payroll", delta: 0, payroll: 231440997654321 },
      { kind: "signing", detail: "sign Nikola Jokić-Valančiūnas Hyphenated Fixture-Name-Extra-Long", delta: 36000000000000, payroll: 267440997654321 },
      { kind: "post_move", detail: "post-move payroll", delta: 0, payroll: 267440997654321 },
    ],
    restrictions: [
      { threshold: "second apron", rule: "aggregating salaries, sending cash, or using a sign-and-trade generated exception in a deal hard-caps the team at the second apron and this rule copy is deliberately verbose" },
      { threshold: "first apron", rule: "acquiring a sign-and-traded player hard-caps the team at the first apron" },
    ],
    evaluationTool: "get_cap_scenario",
    provenance: { origin: "undeclared", capability: "Worst-case fixture · no live query", season: "Illustrative season", liveSources: [] } },
];

export const worstcaseEvents: [string, unknown][] = [
  ["status", { text: "Reading worst-case source rows" }],
  ["token", { text: "## Worst-case fixture\n\nFictional adversarial content. No provider or warehouse call was made.\n" }],
  ["custom_data", { artifacts: worstcaseFixtures }],
  ["final_answer", { text: "## Worst-case fixture\n\nFictional adversarial content. No provider or warehouse call was made.", carry: { verification: "unknown", verified_claims: 0, gaps: [] } }],
  ["graph_end", {}],
];

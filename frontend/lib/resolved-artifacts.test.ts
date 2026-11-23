import assert from "node:assert/strict";
import test from "node:test";
import { asResolvedArtifacts, deriveArtifacts, reduceBackendEvent } from "./dime-stream";

test("a chart the backend resolved renders as a chart", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      {
        kind: "chart",
        title: "Scoring trend",
        series: [
          { name: "Gilgeous-Alexander", values: [30, 22, 41] },
          { name: "Doncic", values: [27, 25, 30] },
        ],
        footnote: "points per game",
      },
    ],
  });

  assert.equal(chunks.length, 1);
  const only = chunks[0];
  assert.equal(only.type, "artifact");
  if (only.type !== "artifact") return;
  assert.equal(only.artifact.kind, "chart");
  if (only.artifact.kind !== "chart") return;
  assert.equal(only.artifact.title, "Scoring trend");
  assert.deepEqual(only.artifact.series[0].values, [30, 22, 41]);
  assert.equal(only.artifact.footnote, "points per game");
});

test("a chart artifact preserves unit, xLabels, and series tone", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      {
        kind: "chart",
        title: "Net Rating Trend",
        unit: "NetRtg",
        xLabels: ["Oct", "Nov", "Dec"],
        series: [
          { name: "Thunder", values: [8.2, 10.5, 12.1], tone: "ink" },
          { name: "League", values: [0.0, 0.0, 0.0], tone: "muted" },
        ],
      },
    ],
  });

  assert.equal(chunks.length, 1);
  const only = chunks[0];
  assert.equal(only.type, "artifact");
  if (only.type !== "artifact" || only.artifact.kind !== "chart") return;
  assert.equal(only.artifact.unit, "NetRtg");
  assert.deepEqual(only.artifact.xLabels, ["Oct", "Nov", "Dec"]);
  assert.equal(only.artifact.series[0].tone, "ink");
  assert.equal(only.artifact.series[1].tone, "muted");
});

test("a chart artifact preserves accent, good, and warn tones and drops invalid tones", () => {
  const artifacts = asResolvedArtifacts([
    {
      kind: "chart",
      title: "Tone Palette",
      series: [
        { name: "Primary", values: [1, 2], tone: "accent" },
        { name: "Positive", values: [3, 4], tone: "good" },
        { name: "Warning", values: [5, 6], tone: "warn" },
        { name: "Unknown", values: [7, 8], tone: "neon" },
      ],
    },
  ]);

  assert.equal(artifacts.length, 1);
  const chart = artifacts[0];
  assert.equal(chart.kind, "chart");
  if (chart.kind !== "chart") return;
  assert.equal(chart.series[0].tone, "accent");
  assert.equal(chart.series[1].tone, "good");
  assert.equal(chart.series[2].tone, "warn");
  assert.equal(chart.series[3].tone, undefined);
});

test("a resolved chart and a derived table both reach the stream", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [
      {
        output_id: "PTS",
        display_name: "Points",
        subject_display_name: "Gilgeous-Alexander",
        value: "30",
        unit: "points per game",
      },
    ],
    artifacts: [
      {
        kind: "chart",
        title: "Trend",
        series: [{ name: "Gilgeous-Alexander", values: [30, 22] }],
      },
    ],
  });

  assert.deepEqual(
    chunks.map((chunk) =>
      chunk.type === "artifact" ? chunk.artifact.kind : chunk.type),
    ["table", "chart"],
  );
});

test("a malformed resolved artifact is dropped instead of rendered blank", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [{ kind: "chart", title: "no series" }],
  });

  assert.deepEqual(chunks, []);
});

test("an artifact kind the UI cannot draw is dropped", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [{ kind: "pie", title: "x", series: [{ name: "a", values: [1] }] }],
  });

  assert.deepEqual(chunks, []);
});

test("a chart series with no numbers is dropped", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      { kind: "chart", title: "empty", series: [{ name: "a", values: [] }] },
    ],
  });

  assert.deepEqual(chunks, []);
});

test("deriveArtifacts still derives the table and compare from evidence rows", () => {
  const derived = deriveArtifacts([
    {
      output_id: "PTS",
      display_name: "Points",
      subject_display_name: "Gilgeous-Alexander",
      value: "30",
      unit: "points per game",
    },
  ]);

  assert.equal(derived.length, 1);
  assert.equal(derived[0].kind, "table");
});

test("a player_card with sections resolves per-section rows, fields and provenance", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      {
        kind: "player_card",
        title: "Player snapshot",
        playerName: "Shai Gilgeous-Alexander",
        team: "OKC",
        sourceRef: "ref-identity",
        sourceRow: 0,
        nameColumn: "player_name",
        metrics: [{ column: "pts", label: "PTS", value: 32.1, unit: "points/game" }],
        sections: [
          {
            label: "Contract",
            sourceRef: "ref-contract",
            sourceRow: 0,
            metrics: [{ column: "salary", label: "Salary", value: 30000000 }],
            fields: [{ column: "contract_type", label: "Deal", value: "DVET-EXT" }],
            provenance: { capability: "sql_exec", origin: "undeclared", dataset: "bref_contracts", season: "2026-27" },
          },
          {
            label: "Availability",
            sourceRef: "ref-injury",
            sourceRow: 0,
            fields: [{ column: "status", label: "Status", value: "Questionable" }],
          },
        ],
      },
    ],
  });

  assert.equal(chunks.length, 1);
  const only = chunks[0];
  if (only.type !== "artifact" || only.artifact.kind !== "player_card") assert.fail("expected player_card artifact");
  const card = only.artifact;
  assert.equal(card.sections?.length, 2);
  assert.equal(card.sections?.[0].label, "Contract");
  assert.equal(card.sections?.[0].metrics?.[0].value, 30000000);
  assert.equal(card.sections?.[0].fields?.[0].value, "DVET-EXT");
  assert.equal(card.sections?.[0].provenance?.dataset, "bref_contracts");
  assert.equal(card.sections?.[1].fields?.[0].value, "Questionable");
});

test("a player_card section with forged or malformed values is dropped with the artifact", () => {
  const base = {
    kind: "player_card",
    title: "Player snapshot",
    playerName: "Shai Gilgeous-Alexander",
    sourceRef: "ref-identity",
    sourceRow: 0,
    nameColumn: "player_name",
    metrics: [{ column: "pts", label: "PTS", value: 32.1 }],
  };
  for (const sections of [
    [{ label: "S", sourceRef: "r", sourceRow: 0 }],
    [{ label: "S", sourceRef: "r", sourceRow: 0, metrics: [{ column: "v", label: "V", value: "forged" }] }],
    [{ label: "S", sourceRef: "r", sourceRow: -1, metrics: [{ column: "v", label: "V", value: 1 }] }],
  ]) {
    const chunks = reduceBackendEvent("custom_data", { tables: [], artifacts: [{ ...base, sections }] });
    assert.deepEqual(chunks, []);
  }
});

test("a team_card with sections resolves per-section rows, fields and provenance", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      {
        kind: "team_card",
        title: "Team snapshot",
        teamName: "Example City Club",
        sourceRef: "ref-team",
        sourceRow: 0,
        nameColumn: "team_name",
        metrics: [{ column: "net_rating", label: "Net Rtg", value: 4.1, unit: "points/100 possessions" }],
        sections: [
          {
            label: "Payroll",
            sourceRef: "ref-cap",
            sourceRow: 0,
            metrics: [{ column: "total_salary", label: "Payroll", value: 187000000 }],
            fields: [{ column: "cap_status", label: "Cap status", value: "Above first apron" }],
            provenance: { capability: "sql_exec", origin: "undeclared", dataset: "bref_cap", season: "2026-27" },
          },
        ],
      },
    ],
  });

  assert.equal(chunks.length, 1);
  const only = chunks[0];
  if (only.type !== "artifact" || only.artifact.kind !== "team_card") assert.fail("expected team_card artifact");
  const card = only.artifact;
  assert.equal(card.teamName, "Example City Club");
  assert.equal(card.metrics[0].unit, "points/100 possessions");
  assert.equal(card.sections?.length, 1);
  assert.equal(card.sections?.[0].label, "Payroll");
  assert.equal(card.sections?.[0].fields?.[0].value, "Above first apron");
  assert.equal(card.sections?.[0].provenance?.dataset, "bref_cap");
});

test("a team_card with forged or malformed values is dropped with the artifact", () => {
  const base = {
    kind: "team_card",
    title: "Team snapshot",
    teamName: "Example City Club",
    sourceRef: "ref-team",
    sourceRow: 0,
    nameColumn: "team_name",
    metrics: [{ column: "net_rating", label: "Net Rtg", value: 4.1 }],
  };
  for (const artifact of [
    { ...base, teamName: 42 },
    { ...base, metrics: [] },
    { ...base, metrics: [{ column: "v", label: "V", value: "forged" }] },
    { ...base, sections: [{ label: "S", sourceRef: "r", sourceRow: 0 }] },
    { ...base, sections: [{ label: "S", sourceRef: "r", sourceRow: -1, metrics: [{ column: "v", label: "V", value: 1 }] }] },
    { ...base, sections: [{ label: "S", sourceRef: "r", sourceRow: 0, fields: [{ column: "f", label: "F", value: 5 }] }] },
  ]) {
    const chunks = reduceBackendEvent("custom_data", { tables: [], artifacts: [artifact] });
    assert.deepEqual(chunks, []);
  }
});
test("a player_card with sections resolves per-section rows, fields and provenance", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      {
        kind: "player_card",
        title: "Player snapshot",
        playerName: "Shai Gilgeous-Alexander",
        team: "OKC",
        sourceRef: "ref-identity",
        sourceRow: 0,
        nameColumn: "player_name",
        metrics: [{ column: "pts", label: "PTS", value: 32.1, unit: "points/game" }],
        sections: [
          {
            label: "Contract",
            sourceRef: "ref-contract",
            sourceRow: 0,
            metrics: [{ column: "salary", label: "Salary", value: 30000000 }],
            fields: [{ column: "contract_type", label: "Deal", value: "DVET-EXT" }],
            provenance: { capability: "sql_exec", origin: "undeclared", dataset: "bref_contracts", season: "2026-27" },
          },
          {
            label: "Availability",
            sourceRef: "ref-injury",
            sourceRow: 0,
            fields: [{ column: "status", label: "Status", value: "Questionable" }],
          },
        ],
      },
    ],
  });

  assert.equal(chunks.length, 1);
  const only = chunks[0];
  if (only.type !== "artifact" || only.artifact.kind !== "player_card") assert.fail("expected player_card artifact");
  const card = only.artifact;
  assert.equal(card.sections?.length, 2);
  assert.equal(card.sections?.[0].label, "Contract");
  assert.equal(card.sections?.[0].metrics?.[0].value, 30000000);
  assert.equal(card.sections?.[0].fields?.[0].value, "DVET-EXT");
  assert.equal(card.sections?.[0].provenance?.dataset, "bref_contracts");
  assert.equal(card.sections?.[1].fields?.[0].value, "Questionable");
});

test("a player_card section with forged or malformed values is dropped with the artifact", () => {
  const base = {
    kind: "player_card",
    title: "Player snapshot",
    playerName: "Shai Gilgeous-Alexander",
    sourceRef: "ref-identity",
    sourceRow: 0,
    nameColumn: "player_name",
    metrics: [{ column: "pts", label: "PTS", value: 32.1 }],
  };
  for (const sections of [
    [{ label: "S", sourceRef: "r", sourceRow: 0 }],
    [{ label: "S", sourceRef: "r", sourceRow: 0, metrics: [{ column: "v", label: "V", value: "forged" }] }],
    [{ label: "S", sourceRef: "r", sourceRow: -1, metrics: [{ column: "v", label: "V", value: 1 }] }],
  ]) {
    const chunks = reduceBackendEvent("custom_data", { tables: [], artifacts: [{ ...base, sections }] });
    assert.deepEqual(chunks, []);
  }
});
test("a memo the agent submitted resolves with sections and citations", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      {
        kind: "memo",
        title: "Cap & roster strategy",
        subtitle: "Owner briefing",
        sections: [
          { heading: "Cap position", body: "Under the first apron.", anchors: [{ ref: "src-1", row: 0, columns: ["payroll"] }] },
          { heading: "Trade options", body: "Aggregate mid-tier salary." },
        ],
        footnote: "Sources: silver_salaries",
      },
    ],
  });

  assert.equal(chunks.length, 1);
  const only = chunks[0];
  assert.equal(only.type, "artifact");
  if (only.type !== "artifact") return;
  assert.equal(only.artifact.kind, "memo");
  if (only.artifact.kind !== "memo") return;
  assert.equal(only.artifact.title, "Cap & roster strategy");
  assert.equal(only.artifact.subtitle, "Owner briefing");
  assert.equal(only.artifact.sections?.length, 2);
  assert.equal(only.artifact.sections?.[0].anchors?.[0].ref, "src-1");
  assert.equal(only.artifact.footnote, "Sources: silver_salaries");
});

test("a memo with no valid sections is dropped", () => {
  const chunks = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      { kind: "memo", title: "empty", sections: [{ heading: "", body: "x" }] },
      { kind: "memo", title: "none" },
    ],
  });

  assert.deepEqual(chunks, []);
});
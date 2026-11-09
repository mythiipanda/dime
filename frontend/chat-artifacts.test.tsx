import test from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ArtifactBody, AssistantTurn, LiveAssistant, artifactToCopyText } from "./components/site/DimeHarness";
import { DimeStream, type DimeArtifact, type StreamSnapshot } from "./lib/dime-stream";
import { assistantMessageFromSnapshot } from "./components/site/DimeHarness";

function render(artifact: DimeArtifact): string {
  return renderToStaticMarkup(<ArtifactBody artifact={artifact} />);
}

type LiveRun = StreamSnapshot & { id: number; startedAt: number };

const ANSWER_TEXT = "QA FIXTURE ONLY: Fixture metric is 12.3.";

function liveProvenance() {
  return {
    capability: "fixture_capability",
    origin: "live",
    warehouse_id: null,
    season: "fixture-season",
    as_of: "2000-01-01",
    live_sources: ["https://fixture.invalid/source"],
  };
}

function warehouseProvenance() {
  return {
    capability: "fixture_capability",
    origin: "warehouse",
    warehouse_id: "fixture-warehouse",
    season: "fixture-season",
    as_of: "2000-01-01",
    live_sources: [],
  };
}

function row(subject: string, provenance?: unknown) {
  return {
    output_id: "fixture-metric",
    display_name: "Fixture metric",
    subject_type: "player",
    subject_id: `fixture-${subject}`,
    subject_display_name: `QA Fixture ${subject}`,
    value: 12.3,
    unit: "points",
    ...(provenance === undefined ? {} : { provenance }),
  };
}

function runOf(frames: [string, unknown][]): LiveRun {
  const stream = new DimeStream();
  for (const [type, data] of frames) stream.handle(type, data);
  stream.finish();
  return { id: 1, startedAt: 0, ...stream.snapshot() };
}

function persistedAnswer(run: LiveRun): string {
  return renderToStaticMarkup(
    <AssistantTurn
      text={run.text}
      artifacts={run.artifacts}
      suggestions={[]}
      failure={run.failed}
      carry={run.carry}
      onFollowUp={() => {}}
    />,
  );
}

function liveAnswer(run: LiveRun): string {
  return renderToStaticMarkup(<LiveAssistant live={run} />);
}

const CHECKMARK_PATH = "M20 6L9 17l-5-5";

const STATIC_DEMO_ROWS = ["Reading flavor briefs", "Scanning supplier lists", "Comparing tasting notes", "Writing the scoop report"];

function statusRun(finished: boolean): LiveRun {
  const run = runOf([
    ["node_update", { node: "entry", status: "running" }],
    ["node_update", { node: "tools", status: "running" }],
    ["node_update", { node: "analytics", status: "running" }],
    ["final_answer", { text: ANSWER_TEXT, carry: PARTIAL_CARRY }],
    ["graph_end", {}],
  ]);
  return finished ? run : { ...run, done: false };
}

test("a running live stream shows one plain-language phase line and no checkmark rows", () => {
  const run = statusRun(false);
  assert.equal(run.thinking.length, 3);
  const html = liveAnswer(run);
  for (const row of STATIC_DEMO_ROWS) {
    assert.ok(!html.includes(row), html);
  }
  assert.ok(!html.includes(CHECKMARK_PATH), html);
  assert.ok(html.includes("Checking the numbers"), html);
  assert.ok(html.includes("shimmer-text"), html);
  assert.ok(html.includes(ANSWER_TEXT), html);
});

test("a finished live stream collapses to one settled line and leaks no demo chrome", () => {
  const run = statusRun(true);
  const html = liveAnswer(run);
  for (const row of STATIC_DEMO_ROWS) {
    assert.ok(!html.includes(row), html);
  }
  assert.ok(!html.includes(CHECKMARK_PATH), html);
  assert.ok(!html.includes("shimmer-text"), html);
  assert.ok(!html.includes("Thought for 4 seconds"), html);
  assert.match(html, /Thought for \d+ seconds/, html);
  assert.ok(html.includes(ANSWER_TEXT), html);
});

function bothAnswers(run: LiveRun): string {
  return `${persistedAnswer(run)}${liveAnswer(run)}`;
}

test("streamed chart artifacts render a chart", () => {
  const html = render({
    kind: "chart",
    title: "Scoring trend",
    series: [
      { name: "Gilgeous-Alexander", values: [24, 31, 28] },
      { name: "Doncic", values: [27, 25, 30] },
    ],
    footnote: "points per game",
  });
  assert.ok(html.includes("<svg"), html.slice(0, 120));
  assert.ok(html.includes("Gilgeous-Alexander"), html);
});

test("streamed shot chart artifacts render a court", () => {
  const html = render({
    kind: "shot_chart",
    title: "Shot chart",
    zones: [
      { x: 50, y: 12, att: 142, pct: 71 },
      { x: 32, y: 22, att: 88, pct: 52 },
    ],
  });
  assert.ok(html.includes("<svg"), html.slice(0, 120));
});

test("chart and shot artifacts with no data render nothing", () => {
  assert.equal(
    render({ kind: "chart", title: "empty", series: [] }),
    "",
  );
  assert.equal(
    render({ kind: "shot_chart", title: "empty", zones: [] }),
    "",
  );
  assert.equal(
    render({ kind: "scatter", title: "empty", xLabel: "TS%", yLabel: "USG%", points: [] }),
    "",
  );
});

test("streamed scatter artifacts render SVG circles, labels, and axes", () => {
  const html = render({
    kind: "scatter",
    title: "Efficiency vs Volume",
    xLabel: "True Shooting %",
    yLabel: "Usage %",
    xMid: 58.0,
    yMid: 20.0,
    footnote: "Minimum 500 minutes",
    points: [
      { label: "Nikola Jokic", x: 65.0, y: 28.5, highlight: true },
      { label: "Shai Gilgeous-Alexander", x: 63.6, y: 32.0, highlight: true },
      { label: "Role Player", x: 54.0, y: 15.0 },
    ],
  });
  assert.ok(html.includes("<svg"), html.slice(0, 120));
  assert.ok(html.includes('role="img"'), html);
  assert.ok(html.includes("<circle"), html);
  assert.ok(html.includes("Nikola Jokic"), html);
  assert.ok(html.includes("Shai Gilgeous-Alexander"), html);
  assert.ok(html.includes("True Shooting %"), html);
  assert.ok(html.includes("Usage %"), html);
  assert.ok(html.includes("Minimum 500 minutes"), html);
});

test("table and compare artifacts still render their rows", () => {
  const table = render({
    kind: "table",
    title: "Verified numbers",
    columns: [{ key: "metric", label: "Metric" }],
    rows: [["Wins", "OKC"]],
  });
  assert.ok(table.includes("Wins"), table);

  const compare = render({
    kind: "compare",
    title: "Head-to-head",
    aName: "SGA",
    bName: "Luka",
    rows: [{ label: "PPG", a: 31.2, b: 28.4 }],
  });
  assert.ok(compare.includes("SGA"), compare);
  assert.ok(compare.includes("Luka"), compare);
});

const PARTIAL_CARRY = {
  run_id: "run-fixture",
  verification: "partial",
  verified_claims: 0,
  gaps: [{ kind: "fixture-gap", blocks: [] }],
};

const PASS_CARRY = { run_id: "run-fixture", verification: "pass", verified_claims: 1, gaps: [] };

function answerFrames(tables: unknown[], carry: unknown, artifacts: unknown[] = []): [string, unknown][] {
  return [
    ["custom_data", { node: "analytics", tables, artifacts, unverified_numbers: [] }],
    ["final_answer", { text: ANSWER_TEXT, carry }],
    ["graph_end", {}],
  ];
}

test("live evidence is disclosed with its sources, season and as-of date", () => {
  const run = runOf(answerFrames([row("A", liveProvenance())], PARTIAL_CARRY));
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(html.includes(ANSWER_TEXT), html);
    assert.ok(!/Verified numbers/i.test(html), html);
    assert.ok(!/dime warehouse/i.test(html), html);
    assert.match(html, /live/i);
    assert.ok(html.includes("fixture-season"), html);
    assert.ok(html.includes("2000-01-01"), html);
    assert.ok(html.includes('href="https://fixture.invalid/source"'), html);
    assert.match(html, /partial/i);
    assert.match(html, /0 verified claims/);
    assert.ok(html.includes("fixture-gap"), html);
  }
});

test("every stream artifact offers accessible provenance inspection", () => {
  const run = runOf(answerFrames([row("A", liveProvenance())], PARTIAL_CARRY));
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.match(html, /<details/, html);
    assert.match(html, /<summary[^>]*>[^<]*([Ss]ources|[Pp]rovenance|[Cc]itation)/, html);
  }
});

test("declared warehouse evidence with a passing carry is disclosed as verified", () => {
  const run = runOf(answerFrames([row("A", warehouseProvenance())], PASS_CARRY));
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(!/Verified numbers/i.test(html), html);
    assert.match(html, /Verified/, html);
    assert.match(html, /warehouse/, html);
    assert.ok(html.includes("fixture-warehouse"), html);
  }
});

test("warehouse evidence with a partial carry is never disclosed as verified", () => {
  const run = runOf(answerFrames([row("A", warehouseProvenance())], PARTIAL_CARRY));
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(!/Verified numbers/i.test(html), html);
    assert.match(html, /partial/i);
    assert.match(html, /0 verified claims/);
    assert.ok(html.includes("fixture-gap"), html);
  }
});

test("a mixed live and warehouse answer stays mixed", () => {
  const run = runOf(
    answerFrames([row("A", liveProvenance()), row("B", warehouseProvenance())], PARTIAL_CARRY),
  );
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(!/Verified numbers/i.test(html), html);
    assert.match(html, /mixed/i);
    assert.ok(html.includes('href="https://fixture.invalid/source"'), html);
    assert.ok(html.includes("2000-01-01"), html);
  }
});

test("undeclared evidence is disclosed as undeclared, not as a warehouse", () => {
  const run = runOf(answerFrames([row("A")], undefined));
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(!/Verified numbers/i.test(html), html);
    assert.ok(!/dime warehouse/i.test(html), html);
    assert.match(html, /unknown|undeclared|not declared|not reported/i);
  }
});

test("malformed provenance never renders an unsafe source link", () => {
  const run = runOf(
    answerFrames(
      [
        row("A", {
          origin: "warehouse",
          warehouse_id: 42,
          season: [],
          as_of: {},
          live_sources: ["javascript:alert(1)", "https://fixture.invalid/safe"],
        }),
      ],
      { verification: "pass", verified_claims: -1, gaps: "bad" },
    ),
  );
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(!/javascript:/i.test(html), html);
    assert.ok(!/data:/i.test(html), html);
    assert.ok(html.includes('href="https://fixture.invalid/safe"'), html);
    assert.ok(!/Verified numbers/i.test(html), html);
    assert.ok(!/dime warehouse/i.test(html), html);
    assert.ok(!html.includes("[]"), html);
    assert.ok(!html.includes("[object Object]"), html);
  }
});

test("a resolved artifact keeps its provenance through the answer", () => {
  const run = runOf(
    answerFrames([], PARTIAL_CARRY, [
      {
        kind: "chart",
        title: "QA FIXTURE resolved chart",
        series: [{ name: "QA Fixture A", values: [12.3] }],
        provenance: liveProvenance(),
      },
    ]),
  );
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(!/Verified numbers/i.test(html), html);
    assert.ok(!/dime warehouse/i.test(html), html);
    assert.match(html, /live/i);
    assert.ok(html.includes("fixture-season"), html);
    assert.ok(html.includes("2000-01-01"), html);
    assert.ok(html.includes('href="https://fixture.invalid/source"'), html);
    assert.match(html, /partial/i);
    assert.match(html, /0 verified claims/);
    assert.ok(html.includes("fixture-gap"), html);
  }
});

test("a resolved artifact with no provenance is disclosed as undeclared", () => {
  const run = runOf(
    answerFrames([], PASS_CARRY, [
      {
        kind: "chart",
        title: "QA FIXTURE resolved chart",
        series: [{ name: "QA Fixture A", values: [12.3] }],
      },
    ]),
  );
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(!/Verified numbers/i.test(html), html);
    assert.ok(!/dime warehouse/i.test(html), html);
    assert.match(html, /unknown|undeclared|not declared|not verified/i);
  }
});

test("an answer with no evidence and no carry shows no verification note", () => {
  const run = runOf([["final_answer", { text: ANSWER_TEXT }]]);
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(!/<details/.test(html), html);
    assert.ok(!/Verification/.test(html), html);
  }
});

test("a typed failure still renders alongside provenance and a partial carry", () => {
  const run = runOf([
    ...answerFrames([row("A", liveProvenance())], PARTIAL_CARRY),
    ["failure", { kind: "quota", message: "quota exhausted" }],
    ["error", { message: "Unable to complete this run." }],
  ]);
  const html = persistedAnswer(run);
  assert.match(html, /out of quota/i);
  assert.ok(html.includes("fixture-gap"), html);
  assert.ok(html.includes('href="https://fixture.invalid/source"'), html);
  assert.ok(!/Verified numbers/i.test(html), html);
  assert.ok(!/dime warehouse/i.test(html), html);
});

test("two rows with different provenance render both seasons, dates and capabilities", () => {
  const run = runOf(
    answerFrames(
      [
        row("A", liveProvenance()),
        row("B", {
          ...warehouseProvenance(),
          capability: "fixture_capability_2",
          warehouse_id: "fixture-warehouse-2",
          season: "fixture-season-2",
          as_of: "2001-02-03",
        }),
      ],
      PARTIAL_CARRY,
    ),
  );
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.match(html, /<summary[^>]*>[^<]*([Ss]ources|[Pp]rovenance|[Cc]itation)/, html);
    assert.ok(html.includes("QA Fixture A"), html);
    assert.ok(html.includes("QA Fixture B"), html);
    assert.ok(html.includes("fixture-season"), html);
    assert.ok(html.includes("fixture-season-2"), html);
    assert.ok(html.includes("2000-01-01"), html);
    assert.ok(html.includes("2001-02-03"), html);
    assert.ok(html.includes("fixture_capability"), html);
    assert.ok(html.includes("fixture_capability_2"), html);
    assert.ok(html.includes("fixture-warehouse-2"), html);
    assert.ok(!/>Verified</.test(html), html);
  }
});

test("an unknown provenance artifact blocks a verified claim and stays inspectable", () => {
  const run = runOf(
    answerFrames(
      [row("A", warehouseProvenance())],
      PASS_CARRY,
      [
        {
          kind: "chart",
          title: "QA FIXTURE unknown provenance chart",
          series: [{ name: "QA Fixture A", values: [12.3] }],
        },
      ],
    ),
  );
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(!/>Verified</.test(html), html);
    assert.match(html, /not declared/i, html);
    assert.match(html, /partly undeclared/i, html);
    assert.ok(html.includes("QA FIXTURE unknown provenance chart"), html);
    assert.equal((html.match(/<summary/g) ?? []).length, 2, html);
  }
});

test("a malformed gap report is never disclosed as verified", () => {
  const run = runOf(
    answerFrames([row("A", warehouseProvenance())], {
      verification: "pass",
      verified_claims: 1,
      gaps: "invalid",
    }),
  );
  const html = bothAnswers(run);
  assert.ok(!/>Verified</.test(html), html);
  assert.match(html, /gap report could not be read/i, html);
  assert.ok(!html.includes("[]"), html);
});

test("one malformed gap entry is never disclosed as a complete gap report", () => {
  const run = runOf(
    answerFrames([row("A", warehouseProvenance())], {
      verification: "pass",
      verified_claims: 1,
      gaps: [{ kind: "fixture-gap", blocks: ["second_metric"] }, { blocks: [] }],
    }),
  );
  const html = bothAnswers(run);
  assert.ok(!/>Verified</.test(html), html);
  assert.match(html, /gap report could not be read/i, html);
  assert.ok(html.includes("fixture-gap"), html);
});

test("an unreported verification status never claims the run passed", () => {
  const run = runOf(
    answerFrames([row("A", warehouseProvenance())], {
      verification: "unknown",
      verified_claims: 1,
      gaps: [],
    }),
  );
  const html = bothAnswers(run);
  assert.ok(!/>Verified</.test(html), html);
  assert.ok(!html.includes("The run reported a pass"), html);
  assert.match(html, /did not report a verification status/i, html);
  assert.match(html, /Verification status: not reported/, html);
});

test("zero verified claims never headline as partly verified", () => {
  const run = runOf(answerFrames([row("A", warehouseProvenance())], PARTIAL_CARRY));
  const html = bothAnswers(run);
  assert.ok(!/>Verified</.test(html), html);
  assert.ok(!/>Partially verified</.test(html), html);
  assert.match(html, />No verified claims</, html);
  assert.match(html, /Verification status: partial/, html);
  assert.match(html, /0 verified claims/, html);
  assert.ok(html.includes("fixture-gap"), html);
});

test("a gap ledger renders as human-wording disclosure, not as enum kinds", () => {
  const run = runOf(
    answerFrames([row("A", warehouseProvenance())], {
      run_id: "run-fixture",
      verification: "partial",
      verified_claims: 1,
      gaps: [
        { kind: "missing_evidence", blocks: ["requirement:req_season_series"] },
        { kind: "source_conflict", blocks: [] },
        { kind: "fixture-gap", blocks: [] },
      ],
    }),
  );
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.match(html, /What this answer could not confirm/, html);
    assert.ok(
      html.includes("Some of what you asked for isn&#x27;t backed by data."),
      html,
    );
    assert.ok(
      html.includes("The sources behind this disagree with each other."),
      html,
    );
    assert.ok(
      html.includes("Part of this answer could not be fully verified."),
      html,
    );
    assert.ok(html.includes('data-gap-kind="missing_evidence"'), html);
    assert.ok(html.includes('data-gap-kind="source_conflict"'), html);
    assert.ok(html.includes('data-gap-kind="fixture-gap"'), html);
    const withoutAttributes = html.replace(/data-gap-kind="[^"]*"/g, "");
    assert.ok(!withoutAttributes.includes("missing_evidence"), withoutAttributes);
    assert.ok(!withoutAttributes.includes("source_conflict"), withoutAttributes);
    assert.ok(!/>Gap: /.test(html), html);
  }
});

test("backend gap block ids never reach the visible answer text", () => {
  const run = runOf(
    answerFrames([row("A", warehouseProvenance())], {
      run_id: "run-fixture",
      verification: "partial",
      verified_claims: 1,
      gaps: [
        { kind: "missing_evidence", blocks: ["requirement:req_season_series"] },
        { kind: "fixture-gap", blocks: ["claim:17", "requirement:req_head_to_head"] },
      ],
    }),
  );
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.match(html, /What this answer could not confirm/, html);
    assert.ok(
      html.includes("Some of what you asked for isn&#x27;t backed by data."),
      html,
    );
    assert.ok(html.includes("Part of this answer could not be fully verified."), html);
    const visible = html.replace(/<[^>]*>/g, "");
    for (const block of [
      "requirement:req_season_series",
      "requirement:req_head_to_head",
      "claim:17",
    ]) {
      assert.ok(!visible.includes(block), `${block} reached the visible copy`);
    }
  }
});

test("an unreadable gap report is never shown as gap wording", () => {
  const run = runOf(
    answerFrames([row("A", warehouseProvenance())], {
      verification: "pass",
      verified_claims: 1,
      gaps: "invalid",
    }),
  );
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.match(html, /gap report could not be read/i, html);
    assert.ok(!/What this answer could not confirm/.test(html), html);
  }
});

function idProvenance() {
  return {
    capability: "fixture_capability",
    origin: "live",
    warehouse_id: null,
    season: "fixture-season",
    as_of: "2000-01-01",
    live_sources: ["nba_api", "espn"],
  };
}

function mixedIdProvenance() {
  return {
    capability: "fixture_capability",
    origin: "mixed",
    warehouse_id: "fixture-warehouse",
    season: "fixture-season",
    as_of: "2000-01-01",
    live_sources: ["basketball_reference"],
  };
}

function interruptedRun(frames: [string, unknown][], transport: string | null): LiveRun {
  const stream = new DimeStream();
  for (const [type, data] of frames) stream.handle(type, data);
  if (transport !== null) stream.fail("connection", transport);
  stream.finish();
  return { id: 1, startedAt: 0, ...stream.snapshot() };
}

test("enum source ids render as text without links", () => {
  const run = runOf(answerFrames([row("A", idProvenance())], PARTIAL_CARRY));
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.ok(html.includes("nba_api"), html);
    assert.ok(html.includes("espn"), html);
    assert.ok(!html.includes('href="nba_api"'), html);
    assert.ok(!html.includes('href="espn"'), html);
    assert.match(html, /live/i);
    assert.ok(!/dime warehouse/i.test(html), html);
  }
});

test("a mixed warehouse id with enum ids stays mixed", () => {
  const run = runOf(answerFrames([row("A", mixedIdProvenance())], PARTIAL_CARRY));
  for (const html of [persistedAnswer(run), liveAnswer(run)]) {
    assert.match(html, /mixed/i);
    assert.ok(html.includes("basketball_reference"), html);
    assert.ok(!html.includes('href="basketball_reference"'), html);
    assert.ok(html.includes("fixture-warehouse"), html);
    assert.ok(!/partly undeclared/i.test(html), html);
  }
});

test("a typed quota failure then an EOF keeps text artifacts carry and quota", () => {
  const run = interruptedRun(
    [
      ["custom_data", { node: "analytics", tables: [row("A", idProvenance())], artifacts: [] }],
      ["final_answer", { text: ANSWER_TEXT, carry: PARTIAL_CARRY }],
      ["failure", { kind: "quota", message: "quota exhausted" }],
    ],
    "Connection to the backend ended before the run completed. Try again.",
  );
  const msg = assistantMessageFromSnapshot(run, "Connection to the backend ended before the run completed. Try again.");
  assert.equal(msg.text, ANSWER_TEXT);
  assert.equal(msg.artifacts.length, 1);
  assert.deepEqual(msg.failure, { kind: "quota", message: "quota exhausted" });
  assert.deepEqual(msg.carry?.gaps, [{ kind: "fixture-gap", blocks: [] }]);
  const html = persistedAnswer({ ...run });
  assert.ok(html.includes(ANSWER_TEXT), html);
  assert.match(html, /out of quota/i);
  assert.ok(!/reach Dime/.test(html), html);
  assert.ok(html.includes("nba_api"), html);
  assert.ok(html.includes("fixture-gap"), html);
});

test("an untyped interruption keeps text artifacts carry with a connection failure", () => {
  const run = interruptedRun(
    [
      ["custom_data", { node: "analytics", tables: [row("A", idProvenance())], artifacts: [] }],
      ["final_answer", { text: ANSWER_TEXT, carry: PARTIAL_CARRY }],
    ],
    "socket closed",
  );
  const msg = assistantMessageFromSnapshot(run, "socket closed");
  assert.equal(msg.text, ANSWER_TEXT);
  assert.equal(msg.artifacts.length, 1);
  assert.deepEqual(msg.failure, { kind: "connection", message: "socket closed" });
  const html = persistedAnswer({ ...run, failed: msg.failure });
  assert.ok(html.includes(ANSWER_TEXT), html);
  assert.match(html, /reach Dime/);
  assert.ok(html.includes("fixture-gap"), html);
});

test("a normal graph_end keeps text artifacts carry with no failure", () => {
  const run = runOf(answerFrames([row("A", idProvenance())], PARTIAL_CARRY));
  const msg = assistantMessageFromSnapshot(run, "");
  assert.equal(msg.text, ANSWER_TEXT);
  assert.equal(msg.artifacts.length, 1);
  assert.equal(msg.failure, null);
  assert.equal(msg.carry?.verifiedClaims, 0);
  const html = persistedAnswer(run);
  assert.ok(html.includes(ANSWER_TEXT), html);
  assert.ok(!/reach Dime/.test(html), html);
  assert.ok(!/out of quota/i.test(html), html);
});

test("artifactToCopyText formats table artifacts as CSV with proper header and escaped cells", () => {
  const tableArtifact: DimeArtifact = {
    kind: "table",
    title: "League leaders",
    columns: [
      { key: "player", label: "Player" },
      { key: "team", label: "Team" },
      { key: "notes", label: "" },
      { key: "ppg", label: "PPG", numeric: true },
    ],
    rows: [
      ["Shai Gilgeous-Alexander", "OKC", "MVP candidate, elite scorer", 31.1],
      ['Luka "Magic" Doncic', "DAL\nTexas", '30+ ppg, "clutch"', 33.9],
    ],
  };

  const csv = artifactToCopyText(tableArtifact);
  assert.equal(
    csv,
    'Player,Team,notes,PPG\nShai Gilgeous-Alexander,OKC,"MVP candidate, elite scorer",31.1\n"Luka ""Magic"" Doncic","DAL\nTexas","30+ ppg, ""clutch""",33.9',
  );
});

test("artifactToCopyText formats compare artifacts", () => {
  const compareArtifact: DimeArtifact = {
    kind: "compare",
    title: "Head-to-head",
    aName: "SGA",
    bName: "Luka",
    rows: [
      { label: "PPG", a: 31.2, b: 28.4 },
      { label: "TS%", a: 63.5, b: 61.2 },
    ],
  };

  const text = artifactToCopyText(compareArtifact);
  assert.equal(
    text,
    "Head-to-head (SGA vs Luka)\nPPG: SGA 31.2 · Luka 28.4\nTS%: SGA 63.5 · Luka 61.2",
  );
});

test("artifactToCopyText formats chart series", () => {
  const chartArtifact: DimeArtifact = {
    kind: "chart",
    title: "Scoring trend",
    series: [
      { name: "Gilgeous-Alexander", values: [24, 31, 28] },
      { name: "Doncic", values: [27, 25, 30] },
    ],
    footnote: "points per game",
  };

  const text = artifactToCopyText(chartArtifact);
  assert.equal(
    text,
    "Scoring trend\nGilgeous-Alexander: 24, 31, 28\nDoncic: 27, 25, 30\npoints per game",
  );

  const chartWithoutFootnote: DimeArtifact = {
    kind: "chart",
    title: "Scoring trend",
    series: [{ name: "Gilgeous-Alexander", values: [30] }],
  };
  assert.equal(
    artifactToCopyText(chartWithoutFootnote),
    "Scoring trend\nGilgeous-Alexander: 30",
  );
});

test("artifactToCopyText formats shot chart zones", () => {
  const shotArtifact: DimeArtifact = {
    kind: "shot_chart",
    title: "Shot chart",
    zones: [
      { x: 50, y: 12, att: 142, pct: 71 },
      { x: 32, y: 22, att: 88, pct: 52 },
    ],
  };

  const text = artifactToCopyText(shotArtifact);
  assert.equal(
    text,
    "Shot chart\nx=50, y=12: 142 att, 71%\nx=32, y=22: 88 att, 52%",
  );
});

test("artifactToCopyText formats scatter points as CSV", () => {
  const scatterArtifact: DimeArtifact = {
    kind: "scatter",
    title: "Efficiency vs Volume",
    xLabel: "TS%",
    yLabel: "USG%",
    points: [
      { label: "Nikola Jokic", x: 65.0, y: 28.5, highlight: true },
      { label: 'Luka "Magic" Doncic', x: 61.2, y: 35.5 },
    ],
  };

  const csv = artifactToCopyText(scatterArtifact);
  assert.equal(
    csv,
    'Label,TS%,USG%\nNikola Jokic,65,28.5\n"Luka ""Magic"" Doncic",61.2,35.5',
  );
});

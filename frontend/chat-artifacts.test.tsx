import test from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ArtifactBody, AssistantTurn, LiveAssistant } from "./components/site/DimeHarness";
import { DimeStream, type DimeArtifact, type StreamSnapshot } from "./lib/dime-stream";

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

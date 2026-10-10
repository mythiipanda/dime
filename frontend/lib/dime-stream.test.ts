import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DimeStream,
  deriveArtifacts,
  failureCopy,
  mergeArtifactProvenance,
  mergeProvenance,
  originPhrase,
  parseCarry,
  parseProvenance,
  provenanceSource,
  reduceBackendEvent,
  thinkingLabelFor,
  toolLabelFor,
  verificationDisclosure,
  type DimeArtifact,
  type DimeProvenance,
} from "./dime-stream";

function streamed(events: [string, unknown][]): DimeStream {
  const stream = new DimeStream();
  for (const [type, data] of events) stream.handle(type, data);
  return stream;
}

test("sql_exec maps to a human warehouse label", () => {
  assert.equal(toolLabelFor("sql_exec"), "Querying warehouse");
  assert.equal(toolLabelFor("sql_exec", "ok"), "Queried warehouse");
  assert.equal(toolLabelFor("lineups", "running"), "Pulling lineup data");
  assert.equal(toolLabelFor("lineups", "ok"), "Pulled lineup data");
  assert.equal(toolLabelFor("game_prediction", "ok"), "Ran game prediction");
  assert.equal(toolLabelFor("web_fetch", "ok"), "Read a web page");
});

test("unknown tool names fall back to a generic label", () => {
  assert.equal(toolLabelFor("mystery_capability"), "Running a tool");
  assert.equal(toolLabelFor(undefined), "Running a tool");
  assert.equal(toolLabelFor("mystery_capability", "ok"), "Ran a tool");
});

test("tool narration switches to past tense once the tool finishes", () => {
  const stream = streamed([
    ["tool_call", { name: "lineups", event_id: "d:4" }],
  ]);
  assert.equal(stream.snapshot().tools[0].label, "Pulling lineup data");
  stream.handle("tool_result", {
    name: "lineups", event_id: "d:4", status: "ok", rows: 8, ms: 240,
  });
  assert.equal(stream.snapshot().tools[0].label, "Pulled lineup data");
});

test("tool narration never leaks capability names", () => {
  const names = [
    "sql_exec", "lineups", "entity_resolution", "web_search",
    "matchup_brief", "unknown_capability",
  ];
  for (const name of names) {
    for (const status of ["running", "ok"] as const) {
      const label = toolLabelFor(name, status);
      assert.ok(!label.includes("_"), label);
      assert.ok(!/^[a-z][a-z0-9_]+$/.test(label), label);
    }
  }
});

test("node names map to human thinking labels without stage names", () => {
  for (const node of ["entry", "data_retrieval", "tools", "analytics", "presentation"]) {
    const label = thinkingLabelFor(node);
    assert.ok(!label.includes("data_retrieval"), label);
    assert.ok(!label.includes("verifier"), label);
    assert.ok(label.length > 0, node);
  }
  assert.equal(thinkingLabelFor("entry"), "Understanding your question");
});

test("token events append streaming text", () => {
  const snap = streamed([
    ["token", { text: "Hello " }],
    ["token", { text: "world." }],
  ]).snapshot();
  assert.equal(snap.text, "Hello world.");
});

test("final_answer sets the authoritative text", () => {
  const snap = streamed([
    ["token", { text: "partial draft" }],
    ["final_answer", { text: "verified final answer", carry: {} }],
  ]).snapshot();
  assert.equal(snap.text, "verified final answer");
});

test("tool_call then tool_result updates one running chip", () => {
  const stream = streamed([
    ["tool_call", { name: "sql_exec", event_id: "a:1" }],
    ["tool_result", { name: "sql_exec", event_id: "a:1", status: "ok", rows: 12, ms: 412 }],
  ]);
  const snap = stream.snapshot();
  assert.equal(snap.tools.length, 1);
  assert.equal(snap.tools[0].label, "Queried warehouse");
  assert.equal(snap.tools[0].status, "ok");
  assert.equal(snap.tools[0].rows, 12);
  assert.equal(snap.tools[0].ms, 412);
});

test("failed tool results mark the chip failed", () => {
  const snap = streamed([
    ["tool_call", { name: "standings", event_id: "b:2" }],
    ["tool_result", { name: "standings", event_id: "b:2", status: "fail" }],
  ]).snapshot();
  assert.equal(snap.tools[0].status, "fail");
});

test("repeated same-name calls without ids stay separate and match in order", () => {
  const snap = streamed([
    ["tool_call", { name: "sql_exec" }],
    ["tool_call", { name: "sql_exec" }],
    ["tool_result", { name: "sql_exec", status: "ok", rows: 3 }],
  ]).snapshot();
  assert.equal(snap.tools.length, 2);
  assert.equal(snap.tools[1].status, "ok");
  assert.equal(snap.tools[1].rows, 3);
  assert.equal(snap.tools[0].status, "running");
});

test("node_update running feeds human thinking rows and dedupes repeats", () => {
  const snap = streamed([
    ["node_update", { node: "entry", status: "running" }],
    ["node_update", { node: "entry", status: "running" }],
    ["node_update", { node: "tools", status: "running" }],
    ["node_update", { node: "tools", status: "complete" }],
  ]).snapshot();
  assert.deepEqual(
    snap.thinking.map((t) => t.label),
    ["Understanding your question", "Gathering the numbers"],
  );
});

test("status text passes through as thinking", () => {
  const snap = streamed([["status", { text: "Checking SGA for 2025-26…" }]]).snapshot();
  assert.equal(snap.thinking[0].label, "Checking SGA for 2025-26…");
});

test("two-subject metric tables derive a compare artifact", () => {
  const artifacts = deriveArtifacts([
    { output_id: "ppg", display_name: "PPG", subject_display_name: "SGA", value: "31.2", unit: "points" },
    { output_id: "ppg", display_name: "PPG", subject_display_name: "Luka", value: "28.4", unit: "points" },
    { output_id: "ts", display_name: "TS%", subject_display_name: "SGA", value: 0.64, unit: "unitless" },
    { output_id: "ts", display_name: "TS%", subject_display_name: "Luka", value: 0.61, unit: "unitless" },
  ]);
  assert.equal(artifacts.length, 1);
  const compare = artifacts[0];
  assert.equal(compare.kind, "compare");
  if (compare.kind === "compare") {
    assert.equal(compare.aName, "SGA");
    assert.equal(compare.bName, "Luka");
    assert.equal(compare.rows.length, 2);
    assert.deepEqual(compare.rows[0], { label: "PPG", a: 31.2, b: 28.4 });
  }
});

test("single-subject tables derive a table artifact", () => {
  const artifacts = deriveArtifacts([
    { output_id: "wins", display_name: "Wins", subject_display_name: "OKC", value: 57, unit: "unitless" },
  ]);
  assert.equal(artifacts.length, 1);
  const table = artifacts[0];
  assert.equal(table.kind, "table");
  if (table.kind === "table") {
    assert.deepEqual(
      table.columns.map((c) => c.label),
      ["Metric", "Subject", "Value", "Unit"],
    );
    assert.deepEqual(table.rows, [["Wins", "OKC", 57, ""]]);
  }
});

test("empty or invalid tables derive no artifacts", () => {
  assert.deepEqual(deriveArtifacts([]), []);
  assert.deepEqual(deriveArtifacts(undefined), []);
  assert.deepEqual(deriveArtifacts([{ nope: true }]), []);
});

test("failure event records a typed failure", () => {
  const snap = streamed([
    ["failure", { kind: "quota", message: "The model ran out of quota." }],
  ]).snapshot();
  assert.deepEqual(snap.failed, {
    kind: "quota",
    message: "The model ran out of quota.",
  });
});

test("legacy error event maps to a typed failure", () => {
  const snap = streamed([["error", { message: "rate limited, retry soon" }]]).snapshot();
  assert.equal(snap.failed?.kind, "rate_limited");
});

test("a typed failure survives the compatibility error frame that follows it", () => {
  const cases: [string, string][] = [
    ["quota", "quota exhausted"],
    ["timeout", "the analysis ran past its time limit"],
    ["provider_error", "the model provider did not respond"],
    ["rate_limited", "too many requests right now"],
  ];
  for (const [kind, message] of cases) {
    const stream = streamed([
      ["token", { text: "partial answer" }],
      ["failure", { kind, message }],
      ["error", { message: "Unable to complete this run." }],
      ["graph_end", {}],
    ]);
    stream.finish();
    const snap = stream.snapshot();
    assert.deepEqual(snap.failed, { kind, message }, kind);
    assert.equal(snap.done, true, kind);
    assert.equal(snap.text, "partial answer", kind);
  }
});

test("a standalone compatibility error still surfaces a failure", () => {
  const snap = streamed([
    ["error", { message: "Unable to complete this run." }],
  ]).snapshot();
  assert.deepEqual(snap.failed, {
    kind: "execution_failure",
    message: "Unable to complete this run.",
  });
});

test("a compatibility error with no message falls back to failure copy", () => {
  const snap = streamed([["error", {}]]).snapshot();
  assert.equal(snap.failed?.kind, "execution_failure");
  assert.equal(snap.failed?.message, failureCopy("execution_failure").body);
});

test("a later typed failure replaces a compatibility error fallback", () => {
  const snap = streamed([
    ["error", { message: "Unable to complete this run." }],
    ["failure", { kind: "quota", message: "quota exhausted" }],
  ]).snapshot();
  assert.deepEqual(snap.failed, { kind: "quota", message: "quota exhausted" });
});

test("the latest typed failure wins even across a compatibility error", () => {
  const snap = streamed([
    ["failure", { kind: "quota", message: "quota exhausted" }],
    ["error", { message: "Unable to complete this run." }],
    ["failure", { kind: "timeout", message: "the analysis ran past its time limit" }],
  ]).snapshot();
  assert.deepEqual(snap.failed, {
    kind: "timeout",
    message: "the analysis ran past its time limit",
  });
});

test("repeated compatibility errors keep the latest fallback", () => {
  const snap = streamed([
    ["error", { message: "Unable to complete this run." }],
    ["error", { message: "the stream closed early" }],
  ]).snapshot();
  assert.deepEqual(snap.failed, {
    kind: "execution_failure",
    message: "the stream closed early",
  });
});

test("a transport failure does not replace a typed failure", () => {
  const stream = streamed([["failure", { kind: "quota", message: "quota exhausted" }]]);
  stream.fail("connection", "socket closed");
  assert.deepEqual(stream.snapshot().failed, {
    kind: "quota",
    message: "quota exhausted",
  });
});

test("a transport failure with no typed failure still records itself", () => {
  const stream = streamed([["token", { text: "hello" }]]);
  stream.fail("connection", "socket closed");
  const snap = stream.snapshot();
  assert.deepEqual(snap.failed, { kind: "connection", message: "socket closed" });
  assert.equal(snap.text, "hello");
});

test("unknown events are ignored", () => {
  const stream = streamed([
    ["ping", { ok: true }],
    ["work_log", { run_id: "run-abc", status: "complete" }],
    ["graph_end", {}],
  ]);
  const snap = stream.snapshot();
  assert.equal(snap.text, "");
  assert.equal(snap.thinking.length, 0);
  assert.equal(snap.failed, null);
});

test("suggestions are captured from the suggestions event", () => {
  const snap = streamed([
    ["suggestions", { items: ["Compare their clutch numbers", "", 42] }],
  ]).snapshot();
  assert.deepEqual(snap.suggestions, ["Compare their clutch numbers"]);
});

test("failure copy stays human with no infra jargon", () => {
  for (const kind of ["timeout", "quota", "rate_limited", "execution_failure",
                      "provider_error", "connection", "startup"]) {
    const copy = failureCopy(kind);
    assert.ok(copy.title.length > 0, kind);
    assert.ok(!/gemini|verifier|stage|sse/i.test(copy.title + copy.body), kind);
  }
  assert.equal(failureCopy("unknown_kind").title, "Something went wrong");
});

test("tool rows carry the arguments the backend declared safe to show", () => {
  const events = reduceBackendEvent("tool_call", {
    name: "lineups",
    event_id: "c:3",
    data: {
      arguments: [
        { name: "season", value: "2025-26" },
        { name: "stat", value: "PTS" },
      ],
      argument_count: 4,
      unknown_argument_count: 2,
    },
  });
  assert.equal(events.length, 1);
  const event = events[0];
  assert.equal(event.type, "tool_activity");
  if (event.type === "tool_activity") {
    assert.deepEqual(event.args, ["season=2025-26", "stat=PTS", "+2 more not shown"]);
  }
});

test("only the arguments the backend declared safe are shown", () => {
  const call = reduceBackendEvent("tool_call", {
    name: "sql_exec",
    event_id: "c:4",
    q: "SELECT secret FROM vault",
    data: { arguments: [{ name: "season", value: "2025-26" }] },
  });
  const result = reduceBackendEvent("tool_result", {
    name: "sql_exec",
    event_id: "c:4",
    status: "ok",
    rows: 12,
    sql: "SELECT secret FROM vault",
  });
  const event = call[0];
  assert.equal(event.type, "tool_activity");
  if (event.type === "tool_activity") {
    assert.deepEqual(event.args, ["season=2025-26"]);
    assert.ok(!JSON.stringify(call).includes("SELECT"), JSON.stringify(call));
  }
  assert.ok(!JSON.stringify(result).includes("SELECT"), JSON.stringify(result));
  const row = streamed([
    [
      "tool_call",
      { name: "sql_exec", event_id: "c:5", q: "SELECT secret FROM vault", data: call[0] },
    ],
    ["tool_result", { name: "sql_exec", event_id: "c:5", status: "ok", rows: 12, sql: "SELECT secret FROM vault" }],
  ]).snapshot().tools;
  assert.equal(row.length, 1);
  assert.ok(!JSON.stringify(row).includes("SELECT"), JSON.stringify(row));
});

test("declared arguments reach the tool row the drawer reads", () => {
  const snap = streamed([
    [
      "tool_call",
      {
        name: "lineups",
        event_id: "g:1",
        data: {
          arguments: [
            { name: "season", value: "2025-26" },
            { name: "stat", value: "PTS" },
          ],
          argument_count: 4,
          unknown_argument_count: 2,
        },
      },
    ],
  ]).snapshot();
  assert.equal(snap.tools.length, 1);
  assert.equal(snap.tools[0].label, "Pulling lineup data");
  assert.deepEqual(snap.tools[0].args, ["season=2025-26", "stat=PTS", "+2 more not shown"]);
});

test("a tool row keeps its declared arguments once the call completes", () => {
  const snap = streamed([
    [
      "tool_call",
      {
        name: "lineups",
        event_id: "g:2",
        data: { arguments: [{ name: "season", value: "2025-26" }] },
      },
    ],
    ["tool_result", { name: "lineups", event_id: "g:2", status: "ok", rows: 8, ms: 240 }],
  ]).snapshot();
  assert.equal(snap.tools.length, 1);
  assert.equal(snap.tools[0].key, "g:2");
  assert.equal(snap.tools[0].status, "ok");
  assert.equal(snap.tools[0].rows, 8);
  assert.deepEqual(snap.tools[0].args, ["season=2025-26"]);
});

test("a call with no declared arguments exposes no drawer control", () => {
  const empty = streamed([
    [
      "tool_call",
      { name: "lineups", event_id: "h:1", data: { arguments: [], argument_count: 0 } },
    ],
  ]).snapshot();
  assert.equal(empty.tools.length, 1);
  assert.equal(empty.tools[0].args, undefined);
  const absent = streamed([
    ["tool_call", { name: "lineups", event_id: "h:2" }],
  ]).snapshot();
  assert.equal(absent.tools.length, 1);
  assert.equal(absent.tools[0].args, undefined);
});

test("no query text reaches the tool row from a call or its result", () => {
  const snap = streamed([
    [
      "tool_call",
      {
        name: "sql_exec",
        event_id: "i:1",
        q: "SELECT secret FROM vault",
        data: { arguments: [{ name: "season", value: "2025-26" }] },
      },
    ],
    [
      "tool_result",
      { name: "sql_exec", event_id: "i:1", status: "ok", rows: 12, sql: "SELECT secret FROM vault" },
    ],
  ]).snapshot();
  assert.equal(snap.tools.length, 1);
  assert.equal(snap.tools[0].status, "ok");
  assert.equal(snap.tools[0].rows, 12);
  assert.deepEqual(snap.tools[0].args, ["season=2025-26"]);
  assert.ok(!Object.keys(snap.tools[0]).includes("sql"), JSON.stringify(snap.tools[0]));
  assert.ok(!Object.keys(snap.tools[0]).includes("q"), JSON.stringify(snap.tools[0]));
  assert.ok(!JSON.stringify(snap.tools).includes("SELECT"), JSON.stringify(snap.tools));
});

test("repeated calls to the same tool keep independent argument drawers", () => {
  const stream = streamed([
    [
      "tool_call",
      {
        name: "lineups",
        event_id: "x:1",
        data: { arguments: [{ name: "season", value: "2025-26" }] },
      },
    ],
    [
      "tool_call",
      {
        name: "lineups",
        event_id: "x:2",
        data: { arguments: [{ name: "season", value: "2024-25" }] },
      },
    ],
  ]);
  const tools = stream.snapshot().tools;
  assert.equal(tools.length, 2);
  assert.equal(tools[0].key, "x:1");
  assert.equal(tools[1].key, "x:2");
  assert.notEqual(tools[0].key, tools[1].key);
  assert.equal(tools[0].label, tools[1].label);
  assert.deepEqual(tools[0].args, ["season=2025-26"]);
  assert.deepEqual(tools[1].args, ["season=2024-25"]);
});

test("the result of a repeated call marks only its own row", () => {
  const snap = streamed([
    [
      "tool_call",
      {
        name: "lineups",
        event_id: "x:1",
        data: { arguments: [{ name: "season", value: "2025-26" }] },
      },
    ],
    [
      "tool_call",
      {
        name: "lineups",
        event_id: "x:2",
        data: { arguments: [{ name: "season", value: "2024-25" }] },
      },
    ],
    ["tool_result", { name: "lineups", event_id: "x:2", status: "ok", rows: 4, ms: 120 }],
  ]).snapshot();
  assert.equal(snap.tools.length, 2);
  assert.equal(snap.tools[0].key, "x:1");
  assert.equal(snap.tools[0].status, "running");
  assert.equal(snap.tools[0].rows, undefined);
  assert.deepEqual(snap.tools[0].args, ["season=2025-26"]);
  assert.equal(snap.tools[1].key, "x:2");
  assert.equal(snap.tools[1].status, "ok");
  assert.equal(snap.tools[1].rows, 4);
  assert.equal(snap.tools[1].ms, 120);
  assert.deepEqual(snap.tools[1].args, ["season=2024-25"]);
});

const LIVE_PROVENANCE = {
  capability: "fixture_capability",
  origin: "live",
  warehouse_id: null,
  season: "fixture-season",
  as_of: "2000-01-01",
  live_sources: ["https://fixture.invalid/source"],
};

const WAREHOUSE_PROVENANCE = {
  capability: "fixture_capability",
  origin: "warehouse",
  warehouse_id: "fixture-warehouse",
  season: "fixture-season",
  as_of: "2000-01-01",
  live_sources: [],
};

function evidenceRow(subject: string, provenance?: unknown) {
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

function firstArtifact(artifacts: DimeArtifact[]): DimeArtifact {
  assert.equal(artifacts.length > 0, true, "expected one derived artifact");
  return artifacts[0];
}

test("derived evidence keeps the live provenance the run declared", () => {
  const artifact = firstArtifact(deriveArtifacts([evidenceRow("A", LIVE_PROVENANCE)]));
  assert.equal(artifact.kind, "table");
  assert.deepEqual(artifact.provenance, {
    origin: "live",
    capability: "fixture_capability",
    season: "fixture-season",
    asOf: "2000-01-01",
    liveSources: ["https://fixture.invalid/source"],
  });
  assert.equal(artifact.source, "live sources");
  assert.ok(!/dime warehouse/i.test(artifact.source ?? ""), artifact.source);
  assert.ok(!/verified numbers/i.test(artifact.title), artifact.title);
});

test("derived evidence keeps declared warehouse provenance", () => {
  const artifact = firstArtifact(deriveArtifacts([evidenceRow("A", WAREHOUSE_PROVENANCE)]));
  assert.deepEqual(artifact.provenance, {
    origin: "warehouse",
    capability: "fixture_capability",
    warehouseId: "fixture-warehouse",
    season: "fixture-season",
    asOf: "2000-01-01",
    liveSources: [],
  });
  assert.equal(artifact.source, "dime warehouse · fixture-warehouse");
});

test("a warehouse claim without a declared warehouse id is not warehouse provenance", () => {
  const artifact = firstArtifact(
    deriveArtifacts([evidenceRow("A", { ...WAREHOUSE_PROVENANCE, warehouse_id: 42 })]),
  );
  assert.equal(artifact.provenance?.origin, "undeclared");
  assert.equal(artifact.provenance?.warehouseId, undefined);
  assert.ok(!/dime warehouse/i.test(artifact.source ?? ""), artifact.source);
});

test("missing provenance metadata is reported as undeclared", () => {
  const artifact = firstArtifact(deriveArtifacts([evidenceRow("A")]));
  assert.deepEqual(artifact.provenance, { origin: "undeclared", liveSources: [] });
  assert.equal(artifact.source, "source not declared");
  assert.ok(!/dime warehouse/i.test(artifact.source ?? ""), artifact.source);
});

test("malformed provenance fields are dropped instead of shown", () => {
  const artifact = firstArtifact(
    deriveArtifacts([
      evidenceRow("A", {
        origin: "warehouse",
        warehouse_id: 42,
        season: [],
        as_of: {},
        live_sources: ["javascript:alert(1)", "https://fixture.invalid/safe"],
      }),
    ]),
  );
  assert.deepEqual(artifact.provenance, {
    origin: "undeclared",
    liveSources: ["https://fixture.invalid/safe"],
  });
});

test("compare artifacts keep live and warehouse origins as mixed", () => {
  const artifacts = deriveArtifacts([
    evidenceRow("A", LIVE_PROVENANCE),
    evidenceRow("B", WAREHOUSE_PROVENANCE),
  ]);
  const compare = firstArtifact(artifacts);
  assert.equal(compare.kind, "compare");
  assert.equal(compare.provenance?.origin, "mixed");
  assert.equal(compare.provenance?.season, "fixture-season");
  assert.equal(compare.provenance?.asOf, "2000-01-01");
  assert.deepEqual(compare.provenance?.liveSources, ["https://fixture.invalid/source"]);
  assert.equal(compare.source, "mixed sources");
  assert.ok(!/dime warehouse/i.test(compare.source ?? ""), compare.source);
  assert.ok(!/verified numbers/i.test(compare.title), compare.title);
});

test("provenance merges refuse to invent an origin", () => {
  assert.equal(mergeProvenance([parseProvenance(undefined)]).origin, "undeclared");
  assert.equal(
    mergeProvenance([parseProvenance(LIVE_PROVENANCE), parseProvenance(undefined)]).origin,
    "partly-undeclared",
  );
  assert.equal(
    mergeProvenance([parseProvenance(WAREHOUSE_PROVENANCE), parseProvenance(WAREHOUSE_PROVENANCE)]).origin,
    "warehouse",
  );
  assert.equal(
    mergeProvenance([
      parseProvenance(WAREHOUSE_PROVENANCE),
      parseProvenance({ ...WAREHOUSE_PROVENANCE, warehouse_id: "other-warehouse" }),
    ]).warehouseId,
    undefined,
  );
});

test("merged provenance carries nested evidence only when every entry is readable", () => {
  const live = parseProvenance(LIVE_PROVENANCE);
  const warehouse = parseProvenance(WAREHOUSE_PROVENANCE);
  const withEvidence = (entry: DimeProvenance, label: string): DimeProvenance => ({
    ...entry,
    evidence: [{ label, provenance: entry }],
  });
  const merged = mergeProvenance([
    withEvidence(live, "QA Fixture A · Fixture metric"),
    withEvidence(warehouse, "QA Fixture B · Fixture metric"),
    withEvidence(live, "QA Fixture A · Fixture metric"),
  ]);
  assert.equal(merged.origin, "mixed");
  assert.deepEqual(
    merged.evidence?.map((item) => [item.label, item.provenance.origin]),
    [
      ["QA Fixture A · Fixture metric", "live"],
      ["QA Fixture B · Fixture metric", "warehouse"],
    ],
  );
  assert.equal(mergeProvenance([live, warehouse]).evidence, undefined);
  const malformed = mergeProvenance([
    withEvidence(live, "QA Fixture A · Fixture metric"),
    { ...warehouse, evidence: [{ label: "", provenance: warehouse }] },
  ]);
  assert.equal(malformed.origin, "mixed");
  assert.equal(malformed.evidence, undefined);
});

test("a producer declared mixed origin keeps its warehouse id and live sources", () => {
  const declared = {
    ...LIVE_PROVENANCE,
    origin: "mixed",
    warehouse_id: "fixture-warehouse",
  };
  const provenance = parseProvenance(declared);
  assert.equal(provenance.origin, "mixed");
  assert.equal(provenance.warehouseId, "fixture-warehouse");
  assert.deepEqual(provenance.liveSources, ["https://fixture.invalid/source"]);
  assert.equal(provenanceSource(provenance), "mixed sources");
  const artifact = firstArtifact(deriveArtifacts([evidenceRow("A", declared)]));
  assert.equal(artifact.provenance?.origin, "mixed");
  assert.equal(artifact.provenance?.warehouseId, "fixture-warehouse");
  assert.equal(originPhrase(artifact.provenance), "mixed live and warehouse sources");
});

test("a declared mixed origin missing one side is not called mixed live and warehouse", () => {
  const noLive = parseProvenance({
    origin: "mixed",
    warehouse_id: "fixture-warehouse",
    live_sources: [],
  });
  assert.equal(noLive.origin, "partly-undeclared");
  assert.equal(noLive.warehouseId, "fixture-warehouse");
  assert.ok(
    !originPhrase(noLive).includes("mixed live and warehouse"),
    originPhrase(noLive),
  );
  const noWarehouse = parseProvenance({
    origin: "mixed",
    live_sources: ["https://fixture.invalid/source"],
  });
  assert.equal(noWarehouse.origin, "partly-undeclared");
  assert.ok(
    !originPhrase(noWarehouse).includes("mixed live and warehouse"),
    originPhrase(noWarehouse),
  );
  const neither = parseProvenance({ origin: "mixed" });
  assert.equal(neither.origin, "undeclared");
});

test("rows with different provenance keep every value inspectable per row", () => {
  const artifact = firstArtifact(
    deriveArtifacts([
      evidenceRow("A", LIVE_PROVENANCE),
      evidenceRow("B", {
        ...WAREHOUSE_PROVENANCE,
        capability: "fixture_capability_2",
        warehouse_id: "fixture-warehouse-2",
        season: "fixture-season-2",
        as_of: "2001-02-03",
      }),
    ]),
  );
  assert.equal(artifact.kind, "compare");
  const evidence = artifact.provenance?.evidence ?? [];
  assert.equal(evidence.length, 2);
  assert.deepEqual(evidence.map((entry) => entry.label), [
    "QA Fixture A · Fixture metric",
    "QA Fixture B · Fixture metric",
  ]);
  assert.deepEqual(evidence.map((entry) => entry.provenance.origin), ["live", "warehouse"]);
  assert.deepEqual(evidence.map((entry) => entry.provenance.capability), [
    "fixture_capability",
    "fixture_capability_2",
  ]);
  assert.deepEqual(evidence.map((entry) => entry.provenance.warehouseId), [
    undefined,
    "fixture-warehouse-2",
  ]);
  assert.deepEqual(evidence.map((entry) => entry.provenance.season), [
    "fixture-season",
    "fixture-season-2",
  ]);
  assert.deepEqual(evidence.map((entry) => entry.provenance.asOf), ["2000-01-01", "2001-02-03"]);
  assert.equal(artifact.provenance?.origin, "mixed");
  assert.equal(artifact.provenance?.capability, undefined);
  assert.equal(artifact.provenance?.warehouseId, undefined);
  assert.equal(artifact.provenance?.season, undefined);
  assert.equal(artifact.provenance?.asOf, undefined);
});

test("an unknown row stays in the inspectable evidence instead of being erased", () => {
  const artifact = firstArtifact(
    deriveArtifacts([evidenceRow("A", LIVE_PROVENANCE), evidenceRow("B")]),
  );
  const evidence = artifact.provenance?.evidence ?? [];
  assert.deepEqual(evidence.map((entry) => entry.provenance.origin), ["live", "undeclared"]);
  assert.equal(artifact.provenance?.origin, "partly-undeclared");
  assert.ok(
    !originPhrase(artifact.provenance).includes("mixed live and warehouse"),
    originPhrase(artifact.provenance),
  );
  assert.deepEqual(artifact.provenance?.liveSources, ["https://fixture.invalid/source"]);
});

test("an artifact without provenance is merged as undeclared instead of being dropped", () => {
  const table = firstArtifact(deriveArtifacts([evidenceRow("A", WAREHOUSE_PROVENANCE)]));
  const chart: DimeArtifact = {
    kind: "chart",
    title: "QA FIXTURE unknown provenance chart",
    series: [{ name: "QA Fixture A", values: [12.3] }],
  };
  const merged = mergeArtifactProvenance([table, chart]);
  assert.equal(merged?.origin, "partly-undeclared");
  const pass = parseCarry({ run_id: "run-fixture", verification: "pass", verified_claims: 1, gaps: [] });
  const disclosure = verificationDisclosure(pass, merged);
  assert.notEqual(disclosure.state, "verified");
  assert.ok(!/^Verified$/m.test(disclosure.headline), disclosure.headline);
  assert.match(disclosure.detail, /partly undeclared/);
});

test("a resolved artifact keeps provenance the run declared", () => {
  const events = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      {
        kind: "chart",
        title: "QA FIXTURE resolved chart",
        series: [{ name: "QA Fixture A", values: [12.3] }],
        provenance: LIVE_PROVENANCE,
      },
    ],
  });
  assert.equal(events.length, 1);
  const chunk = events[0];
  assert.equal(chunk.type, "artifact");
  if (chunk.type !== "artifact") return;
  assert.deepEqual(chunk.artifact.provenance, {
    origin: "live",
    capability: "fixture_capability",
    season: "fixture-season",
    asOf: "2000-01-01",
    liveSources: ["https://fixture.invalid/source"],
  });
  assert.equal(chunk.artifact.source, "live sources");
  assert.ok(!/verified numbers/i.test(chunk.artifact.title), chunk.artifact.title);
});

test("a resolved artifact without provenance is not given one", () => {
  const events = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      { kind: "chart", title: "QA FIXTURE resolved chart", series: [{ name: "QA Fixture A", values: [12.3] }] },
    ],
  });
  const chunk = events[0];
  assert.equal(chunk.type, "artifact");
  if (chunk.type !== "artifact") return;
  assert.equal(chunk.artifact.provenance, undefined);
  assert.equal(chunk.artifact.source, undefined);
});

test("the terminal carry keeps verification, claim count and gaps", () => {
  const snap = streamed([
    [
      "final_answer",
      {
        text: "answer",
        carry: {
          run_id: "run-fixture",
          verification: "partial",
          verified_claims: 0,
          gaps: [{ kind: "fixture-gap", blocks: [] }],
        },
      },
    ],
  ]).snapshot();
  assert.deepEqual(snap.carry, {
    runId: "run-fixture",
    verification: "partial",
    verifiedClaims: 0,
    gaps: [{ kind: "fixture-gap", blocks: [] }],
    gapsReadable: true,
  });
});

test("a gap entry without a readable kind is dropped, not invented", () => {
  const snap = streamed([
    [
      "final_answer",
      {
        text: "answer",
        carry: {
          run_id: "run-fixture",
          verification: "partial",
          verified_claims: 0,
          gaps: [{ kind: "fixture-gap", blocks: ["second_metric"] }, { blocks: [] }],
        },
      },
    ],
  ]).snapshot();
  assert.deepEqual(snap.carry?.gaps, [
    { kind: "fixture-gap", blocks: ["second_metric"] },
  ]);
  assert.equal(snap.carry?.gapsReadable, false);
});

test("a malformed gap entry never makes the report readable", () => {
  const warehouse = parseProvenance(WAREHOUSE_PROVENANCE);
  for (const gap of [
    { blocks: [] },
    { kind: "", blocks: [] },
    { kind: 7, blocks: [] },
    { kind: "fixture-gap", blocks: "second_metric" },
    { kind: "fixture-gap", blocks: ["second_metric", 3] },
    { kind: "fixture-gap", blocks: [" "] },
    "fixture-gap",
    null,
    ["fixture-gap"],
  ]) {
    const label = JSON.stringify(gap);
    const carry = parseCarry({
      verification: "pass",
      verified_claims: 1,
      gaps: [{ kind: "fixture-gap", blocks: [] }, gap],
    });
    assert.deepEqual(carry?.gaps, [{ kind: "fixture-gap", blocks: [] }], label);
    assert.equal(carry?.gapsReadable, false, label);
    const disclosure = verificationDisclosure(carry, warehouse);
    assert.notEqual(disclosure.state, "verified", label);
    assert.ok(!/^Verified$/m.test(disclosure.headline), label);
    assert.match(disclosure.detail, /gap report could not be read/, label);
  }
  const noBlocks = parseCarry({
    verification: "pass",
    verified_claims: 1,
    gaps: [{ kind: "fixture-gap" }],
  });
  assert.equal(noBlocks?.gapsReadable, true);
  assert.deepEqual(noBlocks?.gaps, [{ kind: "fixture-gap", blocks: [] }]);
});

test("a malformed carry keeps the declared status but is never disclosed as verified", () => {
  const snap = streamed([
    [
      "final_answer",
      { text: "answer", carry: { verification: "pass", verified_claims: -1, gaps: "bad" } },
    ],
  ]).snapshot();
  assert.deepEqual(snap.carry, {
    verification: "pass",
    verifiedClaims: null,
    gaps: [],
    gapsReadable: false,
  });
  const disclosure = verificationDisclosure(snap.carry, parseProvenance(undefined));
  assert.equal(disclosure.state, "unverified");
  assert.ok(!/^Verified/i.test(disclosure.headline), disclosure.headline);
  assert.match(disclosure.detail, /not declared/);
});

test("a malformed or missing gap report is never read as no gaps", () => {
  const warehouse = parseProvenance(WAREHOUSE_PROVENANCE);
  for (const raw of [
    { verification: "pass", verified_claims: 1, gaps: "invalid" },
    { verification: "pass", verified_claims: 1 },
    { verification: "pass", verified_claims: 1, gaps: { kind: "fixture-gap", blocks: [] } },
  ]) {
    const label = JSON.stringify(raw);
    const carry = parseCarry(raw);
    assert.deepEqual(carry?.gaps, [], label);
    assert.equal(carry?.gapsReadable, false, label);
    const disclosure = verificationDisclosure(carry, warehouse);
    assert.notEqual(disclosure.state, "verified", label);
    assert.ok(!/^Verified$/m.test(disclosure.headline), disclosure.headline);
    assert.match(disclosure.detail, /gap report could not be read/);
  }
  const safe = parseCarry({
    verification: "pass",
    verified_claims: 1,
    gaps: [{ kind: "fixture-gap", blocks: ["second_metric"] }],
  });
  assert.equal(safe?.gapsReadable, true);
  assert.deepEqual(safe?.gaps, [{ kind: "fixture-gap", blocks: ["second_metric"] }]);
});

test("a claim count that is not a nonnegative integer is never reported as checked", () => {
  for (const raw of [1.5, -1, "1", null, true]) {
    const carry = parseCarry({ verification: "pass", verified_claims: raw, gaps: [] });
    assert.equal(carry?.verifiedClaims, null, JSON.stringify(raw));
    const disclosure = verificationDisclosure(carry, parseProvenance(WAREHOUSE_PROVENANCE));
    assert.notEqual(disclosure.state, "verified", JSON.stringify(raw));
    assert.match(disclosure.detail, /not reported|not how many claims it checked/);
    assert.ok(!/\d+ verified claims?/.test(disclosure.detail), disclosure.detail);
  }
});

test("an unreported verification status never claims the run passed", () => {
  const carry = parseCarry({
    run_id: "run-fixture",
    verification: "unknown",
    verified_claims: 1,
    gaps: [],
  });
  assert.equal(carry?.verification, "unknown");
  assert.equal(carry?.verifiedClaims, 1);
  const disclosure = verificationDisclosure(carry, parseProvenance(WAREHOUSE_PROVENANCE));
  assert.equal(disclosure.state, "unverified");
  assert.ok(!disclosure.detail.includes("reported a pass"), disclosure.detail);
  assert.match(disclosure.detail, /did not report a verification status/);
  assert.ok(!/^Verified$/m.test(disclosure.headline), disclosure.headline);
});

test("zero verified claims do not headline as partly verified", () => {
  const carry = parseCarry({
    run_id: "run-fixture",
    verification: "partial",
    verified_claims: 0,
    gaps: [{ kind: "fixture-gap", blocks: [] }],
  });
  const disclosure = verificationDisclosure(carry, parseProvenance(WAREHOUSE_PROVENANCE));
  assert.equal(disclosure.state, "partial");
  assert.ok(!/partially verified/i.test(disclosure.headline), disclosure.headline);
  assert.match(disclosure.headline, /no verified claims/i);
  assert.match(disclosure.detail, /0 verified claims/);
  assert.match(disclosure.detail, /1 gap reported/);
  assert.deepEqual(disclosure.gaps, [{ kind: "fixture-gap", blocks: [] }]);
});

test("an absent or empty carry is not reported as verification", () => {
  assert.equal(streamed([["final_answer", { text: "answer" }]]).snapshot().carry, null);
  assert.equal(streamed([["final_answer", { text: "answer", carry: {} }]]).snapshot().carry, null);
  assert.equal(verificationDisclosure(null, undefined).state, "unknown");
});

test("verified is claimed only for a declared warehouse with verified claims", () => {
  const warehouse = parseProvenance(WAREHOUSE_PROVENANCE);
  const live = parseProvenance(LIVE_PROVENANCE);
  const undeclared = parseProvenance(undefined);
  const pass = parseCarry({ run_id: "run-fixture", verification: "pass", verified_claims: 1, gaps: [] });
  const partial = parseCarry({
    run_id: "run-fixture",
    verification: "partial",
    verified_claims: 0,
    gaps: [{ kind: "fixture-gap", blocks: [] }],
  });

  const verified = verificationDisclosure(pass, warehouse);
  assert.equal(verified.state, "verified");
  assert.match(verified.detail, /1 verified claim/);

  assert.equal(verificationDisclosure(pass, live).state, "unverified");
  assert.equal(verificationDisclosure(pass, undeclared).state, "unverified");
  assert.match(verificationDisclosure(pass, undeclared).detail, /not declared/);
  assert.equal(verificationDisclosure(pass, undefined).state, "unverified");
  assert.equal(verificationDisclosure(partial, warehouse).state, "partial");
  assert.equal(verificationDisclosure(partial, live).state, "partial");

  const partialLive = verificationDisclosure(partial, live);
  assert.match(partialLive.headline, /no verified claims/i);
  assert.match(partialLive.detail, /0 verified claims/);
  assert.match(partialLive.detail, /live/i);
  assert.deepEqual(partialLive.gaps, [{ kind: "fixture-gap", blocks: [] }]);

  const mixed = verificationDisclosure(pass, mergeProvenance([live, warehouse]));
  assert.equal(mixed.state, "unverified");
  assert.match(mixed.detail, /mixed/);
});

test("zero verified claims are never disclosed as verified", () => {
  const zero = parseCarry({ verification: "pass", verified_claims: 0, gaps: [] });
  assert.equal(verificationDisclosure(zero, parseProvenance(WAREHOUSE_PROVENANCE)).state, "partial");
  const unknownCount = parseCarry({ verification: "partial", verified_claims: null, gaps: [] });
  const disclosure = verificationDisclosure(unknownCount, parseProvenance(WAREHOUSE_PROVENANCE));
  assert.notEqual(disclosure.state, "verified");
  assert.match(disclosure.detail, /not reported/);
});

test("artifact provenance merges across the answer", () => {
  assert.equal(mergeArtifactProvenance([]), undefined);
  assert.equal(
    mergeArtifactProvenance([{ kind: "chart", title: "a", series: [{ name: "s", values: [1] }] }])?.origin,
    "undeclared",
  );
  const artifacts = deriveArtifacts([
    evidenceRow("A", LIVE_PROVENANCE),
    evidenceRow("B", WAREHOUSE_PROVENANCE),
  ]);
  assert.equal(mergeArtifactProvenance(artifacts)?.origin, "mixed");
});

test("provenance source labels never invent a warehouse", () => {
  assert.equal(provenanceSource(parseProvenance(WAREHOUSE_PROVENANCE)), "dime warehouse · fixture-warehouse");
  assert.equal(provenanceSource(parseProvenance(LIVE_PROVENANCE)), "live sources");
  assert.equal(provenanceSource(mergeProvenance([parseProvenance(LIVE_PROVENANCE), parseProvenance(WAREHOUSE_PROVENANCE)])), "mixed sources");
  assert.equal(provenanceSource(parseProvenance(undefined)), "source not declared");
  assert.equal(provenanceSource(undefined), undefined);
});

test("provenance and carry survive a typed failure and the compatibility error after it", () => {
  const stream = streamed([
    ["custom_data", { node: "analytics", tables: [evidenceRow("A", LIVE_PROVENANCE)], artifacts: [] }],
    [
      "final_answer",
      {
        text: "partial answer",
        carry: {
          run_id: "run-fixture",
          verification: "partial",
          verified_claims: 0,
          gaps: [{ kind: "fixture-gap", blocks: [] }],
        },
      },
    ],
    ["failure", { kind: "quota", message: "quota exhausted" }],
    ["error", { message: "Unable to complete this run." }],
    ["graph_end", {}],
  ]);
  stream.finish();
  const snap = stream.snapshot();
  assert.deepEqual(snap.failed, { kind: "quota", message: "quota exhausted" });
  assert.equal(snap.done, true);
  assert.equal(snap.text, "partial answer");
  assert.equal(snap.artifacts[0].provenance?.origin, "live");
  assert.equal(snap.artifacts[0].provenance?.asOf, "2000-01-01");
  assert.deepEqual(snap.carry?.gaps, [{ kind: "fixture-gap", blocks: [] }]);
});

test("failed tools carry plain failure copy instead of a raw payload", () => {
  const events = reduceBackendEvent("tool_result", {
    name: "standings",
    event_id: "e:5",
    status: "fail",
    error: "Tool failed",
  });
  const event = events[0];
  assert.equal(event.type, "tool_activity");
  if (event.type === "tool_activity") {
    assert.equal(event.status, "fail");
    assert.equal(event.error, "Tool failed");
    assert.equal(event.label, "Pulled standings");
  }
});

test("a live producer with enum source ids keeps them apart from urls", () => {
  const provenance = parseProvenance({
    capability: "fixture_capability",
    origin: "live",
    warehouse_id: null,
    season: "fixture-season",
    as_of: "2000-01-01",
    live_sources: ["nba_api", "espn", "https://fixture.invalid/source", "javascript:alert(1)"],
  });
  assert.equal(provenance.origin, "live");
  assert.deepEqual(provenance.liveSources, ["https://fixture.invalid/source"]);
  assert.deepEqual(provenance.liveSourceIds, ["nba_api", "espn"]);
  assert.equal(provenanceSource(provenance), "live sources");
});

test("unknown source ids are dropped and unsafe urls stay excluded", () => {
  const provenance = parseProvenance({
    origin: "live",
    live_sources: ["not_a_source", "NBA_API", "", 42, "data:text/plain,hi"],
  });
  assert.equal(provenance.origin, "live");
  assert.deepEqual(provenance.liveSources, []);
  assert.equal(provenance.liveSourceIds, undefined);
});

test("a mixed producer with a warehouse id and enum ids stays mixed", () => {
  const provenance = parseProvenance({
    capability: "fixture_capability",
    origin: "mixed",
    warehouse_id: "fixture-warehouse",
    season: "fixture-season",
    as_of: "2000-01-01",
    live_sources: ["basketball_reference", "nba_api"],
  });
  assert.equal(provenance.origin, "mixed");
  assert.equal(provenance.warehouseId, "fixture-warehouse");
  assert.deepEqual(provenance.liveSourceIds, ["basketball_reference", "nba_api"]);
  assert.deepEqual(provenance.liveSources, []);
  assert.equal(provenanceSource(provenance), "mixed sources");
  assert.equal(originPhrase(provenance), "mixed live and warehouse sources");
});

test("a mixed producer with urls and ids keeps both", () => {
  const provenance = parseProvenance({
    origin: "mixed",
    warehouse_id: "fixture-warehouse",
    live_sources: ["espn", "https://fixture.invalid/source"],
  });
  assert.equal(provenance.origin, "mixed");
  assert.deepEqual(provenance.liveSources, ["https://fixture.invalid/source"]);
  assert.deepEqual(provenance.liveSourceIds, ["espn"]);
});

test("merged provenance unions enum ids without inventing an origin", () => {
  const a = parseProvenance({ origin: "live", live_sources: ["nba_api"] });
  const b = parseProvenance({
    origin: "mixed",
    warehouse_id: "fixture-warehouse",
    live_sources: ["espn", "https://fixture.invalid/source"],
  });
  const merged = mergeProvenance([a, b]);
  assert.equal(merged.origin, "mixed");
  assert.deepEqual(merged.liveSourceIds, ["nba_api", "espn"]);
  assert.deepEqual(merged.liveSources, ["https://fixture.invalid/source"]);
  assert.deepEqual(mergeProvenance([a]).liveSourceIds, ["nba_api"]);
  assert.equal(parseProvenance(undefined).liveSourceIds, undefined);
});

test("derived evidence keeps enum ids from the declaring run", () => {
  const artifact = firstArtifact(
    deriveArtifacts([
      evidenceRow("A", {
        capability: "fixture_capability",
        origin: "live",
        warehouse_id: null,
        season: "fixture-season",
        as_of: "2000-01-01",
        live_sources: ["nba_api"],
      }),
    ]),
  );
  assert.equal(artifact.provenance?.origin, "live");
  assert.deepEqual(artifact.provenance?.liveSourceIds, ["nba_api"]);
  assert.deepEqual(artifact.provenance?.liveSources, []);
  assert.equal(artifact.source, "live sources");
});

test("a resolved artifact keeps enum ids the run declared", () => {
  const events = reduceBackendEvent("custom_data", {
    tables: [],
    artifacts: [
      {
        kind: "chart",
        title: "QA FIXTURE resolved chart",
        series: [{ name: "QA Fixture A", values: [12.3] }],
        provenance: {
          capability: "fixture_capability",
          origin: "live",
          warehouse_id: null,
          season: "fixture-season",
          as_of: "2000-01-01",
          live_sources: ["basketball_reference"],
        },
      },
    ],
  });
  assert.equal(events.length, 1);
  const chunk = events[0];
  assert.equal(chunk.type, "artifact");
  if (chunk.type !== "artifact") return;
  assert.deepEqual(chunk.artifact.provenance?.liveSourceIds, ["basketball_reference"]);
  assert.deepEqual(chunk.artifact.provenance?.liveSources, []);
});

test("a typed quota failure then a transport interruption keeps every accumulated field", () => {
  const stream = streamed([
    ["custom_data", { node: "analytics", tables: [evidenceRow("A", LIVE_PROVENANCE)], artifacts: [] }],
    ["suggestions", { items: ["Try a narrower question"] }],
    [
      "final_answer",
      {
        text: "partial answer",
        carry: {
          run_id: "run-fixture",
          verification: "partial",
          verified_claims: 0,
          gaps: [{ kind: "fixture-gap", blocks: [] }],
        },
      },
    ],
    ["failure", { kind: "quota", message: "quota exhausted" }],
  ]);
  stream.fail("connection", "Connection to the backend ended before the run completed. Try again.");
  stream.finish();
  const snap = stream.snapshot();
  assert.deepEqual(snap.failed, { kind: "quota", message: "quota exhausted" });
  assert.equal(snap.text, "partial answer");
  assert.equal(snap.artifacts.length, 1);
  assert.equal(snap.artifacts[0].provenance?.origin, "live");
  assert.deepEqual(snap.suggestions, ["Try a narrower question"]);
  assert.deepEqual(snap.carry?.gaps, [{ kind: "fixture-gap", blocks: [] }]);
  assert.equal(snap.carry?.verifiedClaims, 0);
  assert.equal(snap.done, true);
});

test("an untyped interruption keeps accumulated data with a connection failure", () => {
  const stream = streamed([
    ["custom_data", { node: "analytics", tables: [evidenceRow("A", LIVE_PROVENANCE)], artifacts: [] }],
    [
      "final_answer",
      {
        text: "partial answer",
        carry: {
          run_id: "run-fixture",
          verification: "partial",
          verified_claims: 0,
          gaps: [{ kind: "fixture-gap", blocks: [] }],
        },
      },
    ],
  ]);
  stream.fail("connection", "socket closed");
  stream.finish();
  const snap = stream.snapshot();
  assert.deepEqual(snap.failed, { kind: "connection", message: "socket closed" });
  assert.equal(snap.text, "partial answer");
  assert.equal(snap.artifacts.length, 1);
  assert.equal(snap.carry?.verifiedClaims, 0);
});

test("a normal graph_end keeps accumulated data with no failure", () => {
  const stream = streamed([
    ["custom_data", { node: "analytics", tables: [evidenceRow("A", LIVE_PROVENANCE)], artifacts: [] }],
    [
      "final_answer",
      {
        text: "partial answer",
        carry: {
          run_id: "run-fixture",
          verification: "partial",
          verified_claims: 0,
          gaps: [{ kind: "fixture-gap", blocks: [] }],
        },
      },
    ],
    ["graph_end", {}],
  ]);
  stream.finish();
  const snap = stream.snapshot();
  assert.equal(snap.failed, null);
  assert.equal(snap.done, true);
  assert.equal(snap.text, "partial answer");
  assert.equal(snap.artifacts.length, 1);
  assert.equal(snap.carry?.verifiedClaims, 0);
});

test("streamDimeChat passes the authoritative snapshot to onError on an EOF without graph_end", async () => {
  const { streamDimeChat } = await import("./dime-stream");
  const encoder = new TextEncoder();
  function frame(type: string, data: unknown): Uint8Array {
    return encoder.encode(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`);
  }
  const tables = [
    {
      output_id: "fixture-metric",
      display_name: "Fixture metric",
      subject_display_name: "QA Fixture A",
      value: 12.3,
      unit: "points",
      provenance: {
        capability: "fixture_capability",
        origin: "live",
        warehouse_id: null,
        season: "fixture-season",
        as_of: "2000-01-01",
        live_sources: ["nba_api"],
      },
    },
  ];
  const carry = {
    run_id: "run-fixture",
    verification: "partial",
    verified_claims: 0,
    gaps: [{ kind: "fixture-gap", blocks: [] }],
  };
  const chunks = [
    frame("custom_data", { tables, artifacts: [] }),
    frame("final_answer", { text: "partial answer", carry }),
    frame("failure", { kind: "quota", message: "quota exhausted" }),
  ];
  let index = 0;
  const reader = {
    read(): Promise<{ done: boolean; value?: Uint8Array }> {
      if (index < chunks.length) {
        const value = chunks[index];
        index += 1;
        return Promise.resolve({ done: false, value });
      }
      return Promise.resolve({ done: true });
    },
  };
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    headers: { get: () => "text/event-stream" },
    body: { getReader: () => reader },
  });
  try {
    const result = await new Promise<{ snap: import("./dime-stream").StreamSnapshot; message: string }>(
      (resolve, reject) => {
        const timer = setTimeout(() => reject(new Error("onError never fired")), 5000);
        streamDimeChat(
          "fixture question",
          {
            onUpdate: () => undefined,
            onDone: () => reject(new Error("onDone must not fire without graph_end")),
            onError: (snap, message) => {
              clearTimeout(timer);
              resolve({ snap, message });
            },
          },
          {},
        );
      },
    );
    assert.deepEqual(result.snap.failed, { kind: "quota", message: "quota exhausted" });
    assert.equal(result.snap.text, "partial answer");
    assert.equal(result.snap.artifacts.length, 1);
    assert.equal(result.snap.artifacts[0].provenance?.origin, "live");
    assert.deepEqual(result.snap.artifacts[0].provenance?.liveSourceIds, ["nba_api"]);
    assert.equal(result.snap.carry?.verifiedClaims, 0);
    assert.deepEqual(result.snap.carry?.gaps, [{ kind: "fixture-gap", blocks: [] }]);
    assert.ok(result.message.length > 0);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("streamDimeChat keeps a true connection failure when no typed failure arrived", async () => {
  const { streamDimeChat } = await import("./dime-stream");
  const encoder = new TextEncoder();
  const chunks = [
    encoder.encode(`event: token\ndata: ${JSON.stringify({ text: "partial answer" })}\n\n`),
  ];
  let index = 0;
  const reader = {
    read(): Promise<{ done: boolean; value?: Uint8Array }> {
      if (index < chunks.length) {
        const value = chunks[index];
        index += 1;
        return Promise.resolve({ done: false, value });
      }
      return Promise.resolve({ done: true });
    },
  };
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    headers: { get: () => "text/event-stream" },
    body: { getReader: () => reader },
  });
  try {
    const result = await new Promise<{ snap: import("./dime-stream").StreamSnapshot; message: string }>(
      (resolve, reject) => {
        const timer = setTimeout(() => reject(new Error("onError never fired")), 5000);
        streamDimeChat(
          "fixture question",
          {
            onUpdate: () => undefined,
            onDone: () => reject(new Error("onDone must not fire without graph_end")),
            onError: (snap, message) => {
              clearTimeout(timer);
              resolve({ snap, message });
            },
          },
          {},
        );
      },
    );
    assert.equal(result.snap.failed?.kind, "connection");
    assert.equal(result.snap.text, "partial answer");
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("streamDimeChat completes through graph_end without an error", async () => {
  const { streamDimeChat } = await import("./dime-stream");
  const encoder = new TextEncoder();
  function frame(type: string, data: unknown): Uint8Array {
    return encoder.encode(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`);
  }
  const chunks = [
    frame("token", { text: "partial answer" }),
    frame("graph_end", {}),
  ];
  let index = 0;
  const reader = {
    read(): Promise<{ done: boolean; value?: Uint8Array }> {
      if (index < chunks.length) {
        const value = chunks[index];
        index += 1;
        return Promise.resolve({ done: false, value });
      }
      return Promise.resolve({ done: true });
    },
  };
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    headers: { get: () => "text/event-stream" },
    body: { getReader: () => reader },
  });
  try {
    const snap = await new Promise<import("./dime-stream").StreamSnapshot>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("onDone never fired")), 5000);
      streamDimeChat(
        "fixture question",
        {
          onUpdate: () => undefined,
          onDone: (doneSnap) => {
            clearTimeout(timer);
            resolve(doneSnap);
          },
          onError: () => reject(new Error("onError must not fire after graph_end")),
        },
        {},
      );
    });
    assert.equal(snap.failed, null);
    assert.equal(snap.text, "partial answer");
    assert.equal(snap.done, true);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

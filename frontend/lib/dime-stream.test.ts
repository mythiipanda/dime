import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DimeStream,
  deriveArtifacts,
  failureCopy,
  reduceBackendEvent,
  thinkingLabelFor,
  toolLabelFor,
} from "./dime-stream";

function streamed(events: [string, unknown][]): DimeStream {
  const stream = new DimeStream();
  for (const [type, data] of events) stream.handle(type, data);
  return stream;
}

test("sql_exec maps to a human warehouse label", () => {
  assert.equal(toolLabelFor("sql_exec"), "Querying warehouse");
});

test("unknown tool names fall back to a generic label", () => {
  assert.equal(toolLabelFor("mystery_capability"), "Running a tool");
  assert.equal(toolLabelFor(undefined), "Running a tool");
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
  assert.equal(snap.tools[0].label, "Querying warehouse");
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
  for (const kind of ["timeout", "quota", "rate_limited", "execution_failure", "connection", "startup"]) {
    const copy = failureCopy(kind);
    assert.ok(copy.title.length > 0, kind);
    assert.ok(!/gemini|verifier|stage|sse/i.test(copy.title + copy.body), kind);
  }
  assert.equal(failureCopy("unknown_kind").title, "Something went wrong");
});

test("reduceBackendEvent never exposes raw args or sql", () => {
  const events = reduceBackendEvent("tool_call", {
    name: "sql_exec",
    event_id: "c:3",
    data: { arguments: [{ name: "q", value: "SELECT secret" }] },
  });
  assert.equal(events.length, 1);
  const text = JSON.stringify(events);
  assert.ok(!text.includes("SELECT"), text);
});

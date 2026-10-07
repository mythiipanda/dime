import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ActivityTimeline, { describePair } from "./components/ActivityTimeline";
import AgentActivity from "./components/AgentActivity";
import { pairToolItems } from "./lib/activity";
import type { ActivityRecord, AiMessage } from "./lib/chat";

function rec(partial: Record<string, unknown>): ActivityRecord {
  return {
    eventId: "e0",
    sequence: 0,
    kind: "tool_call",
    title: "t",
    data: {},
    ...partial,
  } as ActivityRecord;
}

const ITEMS: ActivityRecord[] = [
  rec({
    eventId: "e1",
    sequence: 1,
    kind: "tool_call",
    title: "Tool call",
    status: "running",
    node: "tools",
    data: { name: "get_leaders", argument_count: 1 },
  }),
  rec({
    eventId: "e2",
    sequence: 2,
    kind: "tool_result",
    title: "Tool result",
    status: "complete",
    transition: "succeeded",
    node: "tools",
    data: { name: "get_leaders", rows: 30 },
  }),
  rec({
    eventId: "e3",
    sequence: 3,
    kind: "node_update",
    title: "Node",
    status: "complete",
    node: "analytics",
    data: {},
  }),
];

function doneAi(): AiMessage {
  return {
    text: "done",
    done: true,
    nodes: {
      tools: {
        status: "complete",
        thoughts: [],
        toolCalls: [{ name: "get_leaders", args: {}, status: "ok", rows: 30 }],
        toolResults: [],
        tables: [],
      },
    },
  };
}

function clean(html: string): string {
  return html.replace(/<style[^>]*>[\s\S]*?<\/style>/g, "");
}

describe("activity status narration", () => {
  it("finished work reads past tense with no checkmarks or Complete rows", () => {
    const html = clean(
      renderToStaticMarkup(
        React.createElement(ActivityTimeline, { items: ITEMS, running: false }),
      ),
    );
    assert.ok(!html.includes("✓"), "checkmark row leaked");
    assert.ok(!html.includes("Complete"), "Complete row leaked");
    assert.ok(!html.includes("Status"), "status field leaked");
    assert.ok(html.includes("Used 1 tool"));
    const pairs = pairToolItems(ITEMS);
    assert.equal(pairs.length, 1);
    const view = describePair(pairs[0], false);
    assert.ok(view.label.startsWith("Found"));
    assert.ok(view.meta.includes("30 rows"));
    assert.ok(!view.fields.some(([k]) => k === "Status"));
  });

  it("legacy activity path has no checkmarks either", () => {
    const html = clean(
      renderToStaticMarkup(React.createElement(AgentActivity, { ai: doneAi() })),
    );
    assert.ok(!html.includes("✓"), "checkmark row leaked");
    assert.ok(!html.includes("Complete"), "Complete row leaked");
  });
});

describe("award failure notes", () => {
  const RAW = "warehouse table missing: silver_bbref_awards; no award result can be read";
  const FAIL_ITEMS = [
    rec({
      eventId: "e1",
      sequence: 1,
      kind: "tool_call",
      title: "Tool call",
      node: "tools",
      data: { name: "get_award_results" },
    }),
    rec({
      eventId: "e2",
      sequence: 2,
      kind: "tool_result",
      title: "Tool result",
      status: "fail",
      transition: "failed",
      node: "tools",
      data: { name: "get_award_results", reason: "table_missing", error: RAW },
    }),
  ];
  it("timeline rows show the plain note, never the raw backend error", () => {
    const html = clean(
      renderToStaticMarkup(
        React.createElement(ActivityTimeline, { items: FAIL_ITEMS, running: false }),
      ),
    );
    assert.ok(html.includes("Used 1 tool"));
    assert.ok(!html.includes("silver_bbref_awards"));
  });
  it("expanding a failed row shows the plain note as its error", () => {
    const pairs = pairToolItems(FAIL_ITEMS);
    assert.equal(pairs.length, 1);
    const view = describePair(pairs[0], false);
    assert.ok(view.label.includes("unavailable"));
    const error = view.fields.find(([k]) => k === "Error");
    assert.equal(error && error[1], "Award results aren't available right now.");
  });
});

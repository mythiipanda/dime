import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { StreamText } from "./components/StreamText";
import ActivityTimeline, { StepBody } from "./components/ActivityTimeline";
import { isImmediateEvent } from "./lib/chat";
import type { ActivityRecord } from "./lib/chat";

const FAILED_CALL: ActivityRecord[] = [
  {
    eventId: "e1",
    sequence: 1,
    kind: "tool_call",
    title: "Tool call",
    status: "fail",
    transition: "failed",
    node: "tools",
    data: { name: "get_leaders" },
  } as ActivityRecord,
];

describe("live streaming text", () => {
  it("paints the full text immediately with a caret while streaming", () => {
    const html = renderToStaticMarkup(
      React.createElement(StreamText, { text: "Hello world", streaming: true }),
    );
    assert.ok(html.includes("Hello world"));
    assert.ok(html.includes("stream-caret"));
  });

  it("drops the caret once done", () => {
    const html = renderToStaticMarkup(
      React.createElement(StreamText, { text: "Hello world", streaming: false }),
    );
    assert.ok(html.includes("Hello world"));
    assert.ok(!html.includes("stream-caret"));
  });

  it("routes text tokens around the batcher", () => {
    assert.equal(isImmediateEvent("token"), true);
    for (const type of ["node_update", "tool_call", "tool_result", "final_answer", "graph_end"]) {
      assert.equal(isImmediateEvent(type), false);
    }
  });
});

describe("never-blank activity", () => {
  it("hides the toggle when no rows survive filtering", () => {
    const html = renderToStaticMarkup(
      React.createElement(ActivityTimeline, { items: [], running: false }),
    );
    assert.equal(html, "");
  });

  it("still shows progress while running with no rows yet", () => {
    const html = renderToStaticMarkup(
      React.createElement(ActivityTimeline, { items: [], running: true }),
    );
    assert.ok(html.includes("Analyzing"));
  });

  it("empty detail bodies get a placeholder, never blank space", () => {
    const html = renderToStaticMarkup(
      React.createElement(StepBody, {
        v: { label: "Runtime stage", meta: "", fields: [] },
        item: FAILED_CALL[0],
      }),
    );
    assert.ok(html.includes("No details for this step."));
  });
});

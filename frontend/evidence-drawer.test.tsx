import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ActivityTimeline, { describePair } from "./components/ActivityTimeline";
import { pairToolItems } from "./lib/activity";
import type { ActivityRecord } from "./lib/chat";

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
    node: "tools",
    data: { name: "get_leaders", args: { stat_category: "AST", season: "2024-25" } },
  }),
  rec({
    eventId: "e2",
    sequence: 2,
    kind: "tool_result",
    title: "Tool result",
    status: "complete",
    transition: "succeeded",
    node: "tools",
    durationMs: 1200,
    data: { name: "get_leaders", rows: 30 },
  }),
  rec({
    eventId: "e3",
    sequence: 3,
    kind: "evidence_update",
    title: "Evidence",
    transition: "admitted",
    data: { capability: "leaders", rows: 30 },
  }),
];

function clean(html: string): string {
  return html.replace(/<style[^>]*>[\s\S]*?<\/style>/g, "");
}

describe("evidence drawer", () => {
  it("summary line names evidence with tool, source, and time totals", () => {
    const html = clean(
      renderToStaticMarkup(
        React.createElement(ActivityTimeline, { items: ITEMS, running: false }),
      ),
    );
    assert.ok(html.includes("Evidence"));
    assert.ok(html.includes("Used 1 tool"));
    assert.ok(html.includes("1 source"));
    assert.ok(html.includes("1.2s"));
  });

  it("live work keeps the running narration, not the totals", () => {
    const html = clean(
      renderToStaticMarkup(
        React.createElement(ActivityTimeline, { items: ITEMS, running: true }),
      ),
    );
    assert.ok(html.includes("Evidence"));
    assert.ok(!html.includes("Used 1 tool"));
  });

  it("tool rows carry a one-line params summary from call args", () => {
    const pairs = pairToolItems(ITEMS);
    assert.equal(pairs.length, 1);
    const view = describePair(pairs[0], false);
    const params = view.fields.find(([k]) => k === "Params");
    assert.ok(params, "params field missing");
    assert.ok(params[1].includes("stat category"));
    assert.ok(!params[1].includes("{"));
  });

  it("collapsed drawer shows no raw payloads", () => {
    const html = clean(
      renderToStaticMarkup(
        React.createElement(ActivityTimeline, { items: ITEMS, running: false }),
      ),
    );
    assert.ok(!html.includes("{\""));
    assert.ok(!html.includes("stat_category"));
  });
});

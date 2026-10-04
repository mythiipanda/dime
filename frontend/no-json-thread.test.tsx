import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import DataTable from "./components/DataTable";
import CompareView from "./components/CompareView";
import ActivityTimeline from "./components/ActivityTimeline";
import AgentActivity from "./components/AgentActivity";
import type { ActivityRecord, AiMessage } from "./lib/chat";

function stripStyle(html: string): string {
  return html.replace(/<style[^>]*>[\s\S]*?<\/style>/g, "");
}

function pairCall(): ActivityRecord[] {
  return [
    {
      eventId: "e1",
      sequence: 1,
      correlationId: "call-1",
      kind: "tool_call",
      title: "Tool call",
      data: {
        name: "get_leaders",
        argument_count: 2,
        args: { stat_category: "AST", season: "2024-25" },
      },
    },
    {
      eventId: "e2",
      sequence: 2,
      correlationId: "call-1",
      kind: "tool_result",
      title: "Tool result",
      data: { name: "get_leaders", rows: 30 },
    },
  ];
}

function leadersAi(): AiMessage {
  return {
    text: "done",
    done: true,
    nodes: {
      tools: {
        status: "complete",
        thoughts: [],
        toolCalls: [
          { name: "get_leaders", args: { stat_category: "AST" }, status: "ok", rows: 30 },
        ],
        toolResults: [],
        tables: [],
      },
    },
  };
}

const OBJECT_CELL_ROWS = [
  { PLAYER: "Nikola Jokic", TEAM: "DEN", AST: 697, META: { source: "warehouse", estimated: true }, TAGS: ["mvp", "allstar"] },
  { PLAYER: "Trae Young", TEAM: "ATL", AST: 690, META: { source: "warehouse", estimated: false }, TAGS: ["allstar"] },
];

const COMPARE_ROWS = {
  a: {
    name: "Trae Young",
    player_id: 1629027,
    gp: 76,
    ppg: 24.1,
    on_off: { net: 5.2, unit: "points" },
  },
  b: {
    name: "Shai Gilgeous-Alexander",
    player_id: 406478,
    gp: 76,
    ppg: 30.4,
    on_off: { net: 7.1, unit: "points" },
  },
};

describe("no JSON in the thread", () => {
  it("tool pair with args object shows no payload", () => {
    const html = stripStyle(
      renderToStaticMarkup(
        React.createElement(ActivityTimeline, { items: pairCall(), running: false }),
      ),
    );
    assert.ok(!html.includes("{\""), "JSON object leaked");
    assert.ok(!html.includes("stat_category"));
  });

  it("agent activity with args object shows no payload", () => {
    const html = stripStyle(
      renderToStaticMarkup(React.createElement(AgentActivity, { ai: leadersAi() })),
    );
    assert.ok(!html.includes("{\""));
    assert.ok(!html.includes("stat_category"));
  });

  it("object cells render a one-line summary, never JSON", () => {
    const html = stripStyle(
      renderToStaticMarkup(React.createElement(DataTable, { rows: OBJECT_CELL_ROWS })),
    );
    assert.ok(html.includes("Nikola Jokic"));
    assert.ok(html.includes("warehouse"));
    assert.ok(!html.includes("{\""));
    assert.ok(!html.includes("&quot;source&quot;"));
  });

  it("array cells render joined, never JSON", () => {
    const html = stripStyle(
      renderToStaticMarkup(React.createElement(DataTable, { rows: OBJECT_CELL_ROWS })),
    );
    assert.ok(!html.includes("[\""));
    assert.ok(html.includes("mvp"));
  });

  it("compare object metrics render flat, never JSON", () => {
    const html = stripStyle(
      renderToStaticMarkup(React.createElement(CompareView, { rows: COMPARE_ROWS })),
    );
    assert.ok(!html.includes("{\""));
    assert.ok(!html.includes("&quot;net&quot;"));
  });
});

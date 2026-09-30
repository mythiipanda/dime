import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import DataTable from "./components/DataTable";
import DataArtifacts from "./components/DataArtifacts";
import AgentActivity from "./components/AgentActivity";
import ActivityTimeline from "./components/ActivityTimeline";
import type { ActivityRecord, AiMessage } from "./lib/chat";

const NEW_LEADERS_ROWS = [
  { RANK: 1, PLAYER: "Nikola Jokic", TEAM: "DEN", AST: 697, GP: 65, MIN: 2265 },
  { RANK: 2, PLAYER: "Trae Young", TEAM: "ATL", AST: 690, GP: 66, MIN: 2210 },
];

const HIST_TABLE = {
  tool: "get_historical_leaders",
  rows: {
    seasons: [
      {
        season: 2015,
        leaders: [
          { player: "Chris Paul", team: "LAC", value: 10.2, display: "10.2", gp: 74, season_label: "2014-15" },
          { player: "Rajon Rondo", team: "SAC", value: 11.7, display: "11.7", gp: 72, season_label: "2015-16" },
        ],
      },
    ],
  },
  meta: { source: "warehouse", estimated: true, label: "AST" },
};

function histAi(): AiMessage {
  return {
    text: "answer",
    done: true,
    nodes: {
      analytics: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: [HIST_TABLE as never],
      },
    },
  };
}

function aiWithFailedCall(): AiMessage {
  return {
    text: "done",
    done: true,
    nodes: {
      tools: {
        status: "complete",
        thoughts: [],
        toolCalls: [
          { name: "get_leaders", args: { stat_category: "AST" }, status: "ok", rows: 30 },
          {
            name: "get_historical_leaders",
            args: { category: "ast" },
            status: "fail",
            error: "warehouse read failed: timeout",
          },
        ],
        toolResults: [],
        tables: [],
      },
    },
  };
}

function failedActivity(): ActivityRecord[] {
  return [
    {
      eventId: "e1",
      sequence: 1,
      correlationId: "call-9",
      kind: "tool_call",
      title: "Tool call",
      data: { name: "get_historical_leaders", argument_count: 2, unknown_argument_count: 0 },
    },
    {
      eventId: "e2",
      sequence: 2,
      correlationId: "call-9",
      kind: "tool_result",
      title: "Tool result",
      status: "fail",
      transition: "failed",
      data: { name: "get_historical_leaders", rows: 0 },
    },
    {
      eventId: "e3",
      sequence: 3,
      kind: "tool_call",
      title: "Tool call",
      data: { name: "get_leaders", argument_count: 1, unknown_argument_count: 0 },
    },
  ];
}

describe("aqbatch green-after", () => {
  it("A1 headers are human labels, no PERCENTILE", () => {
    const html = renderToStaticMarkup(React.createElement(DataTable, { rows: NEW_LEADERS_ROWS }));
    const heads = [...html.matchAll(/Sort by ([A-Za-z/#%][^"<]*)/g)].map((m) => m[1]);
    console.log("A1-HEADERS:" + JSON.stringify(heads));
    assert.ok(!heads.includes("PERCENTILE"));
    assert.ok(heads.includes("Assists") && heads.includes("Games") && heads.includes("Minutes"));
    assert.ok(!html.includes(">AST<") && !html.includes(">GP<") && !html.includes(">MIN<"));
  });

  it("A2 historical renders flat rows, no JSON blob", () => {
    const html = renderToStaticMarkup(React.createElement(DataArtifacts, { ai: histAi() }));
    console.log("A2-SNIP:" + html.slice(html.indexOf("<tbody"), html.indexOf("<tbody") + 1200));
    assert.ok(html.includes("Chris Paul"));
    assert.ok(!html.includes("[{&quot;player&quot;"));
    assert.ok(!html.includes("documented estimates"));
  });

  it("A3 estimated badge renders, source is plain", () => {
    const html = renderToStaticMarkup(React.createElement(DataArtifacts, { ai: histAi() }));
    assert.ok(html.includes("Estimated values"));
    assert.ok(html.includes("Source: warehouse"));
  });

  it("A5 failure rows hidden", () => {
    const agent = renderToStaticMarkup(
      React.createElement(AgentActivity, { ai: aiWithFailedCall() }),
    );
    assert.ok(!agent.includes("warehouse read failed"));
    assert.ok(agent.includes("1 tool call"));
    const timeline = renderToStaticMarkup(
      React.createElement(ActivityTimeline, { items: failedActivity(), running: false }),
    );
    assert.ok(!timeline.includes("unavailable"));
    assert.ok(!timeline.includes(">Failed<"));
    assert.ok(timeline.includes("get leaders") || timeline.includes("1 tool call"));
    console.log("A5-TIMELINE-BUTTON:" + timeline.slice(timeline.indexOf("1 tool call") - 200, timeline.indexOf("1 tool call") + 20));
  });
});

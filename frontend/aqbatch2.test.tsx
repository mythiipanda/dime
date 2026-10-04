import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import DataTable from "./components/DataTable";
import DataArtifacts from "./components/DataArtifacts";
import AnswerText from "./components/AnswerText";
import AgentActivity from "./components/AgentActivity";
import ActivityTimeline from "./components/ActivityTimeline";
import type { ActivityRecord, AiMessage } from "./lib/chat";

const LEADERS_WITH_PCT = [
  { RANK: 1, PLAYER: "Nikola Jokic", TEAM: "DEN", AST: 697, GP: 65, MIN: 2265, PERCENTILE: 100 },
  { RANK: 2, PLAYER: "Trae Young", TEAM: "ATL", AST: 690, GP: 66, MIN: 2210, PERCENTILE: 99.8 },
];

const SEASONS_PAYLOAD = {
  seasons: [
    {
      season: 2015,
      leaders: [
        { player: "Chris Paul", team: "LAC", value: 10.2, display: "10.2", gp: 74, season_label: "2014-15" },
        { player: "Rajon Rondo", team: "SAC", value: 11.7, display: "11.7", gp: 72, season_label: "2015-16" },
      ],
    },
  ],
};

function titleOnlyHistAi(): AiMessage {
  return {
    text: "answer",
    done: true,
    nodes: {
      analytics: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: [
          {
            title: "Historical leaders",
            rows: SEASONS_PAYLOAD,
            meta: { source: "warehouse", label: "AST" },
          } as never,
        ],
      },
    },
  };
}

function stringRowsHistAi(): AiMessage {
  return {
    text: "answer",
    done: true,
    nodes: {
      analytics: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: [
          {
            tool: "get_historical_leaders",
            rows: JSON.stringify(SEASONS_PAYLOAD),
            meta: { source: "warehouse", label: "AST" },
          } as never,
        ],
      },
    },
  };
}

const TAKEAWAY_BLOB =
  "**Takeaways**\n" +
  "1. 11.7 assists per game by Rajon Rondo and Russell Westbrook, 11.2 by James Harden, 10.9 by John Wall, 10.2 by Chris Paul, 9.8 by Deron Williams, 9.1 by Jeff Teague, 8.8 by Stephen Curry, 8.5 by Damian Lillard, 8.2 by Kyle Lowry, and 7.9 by Mike Conley across the full span with even more trailing words to bloat it.\n" +
  "2. Second pattern holds across eras.\n" +
  "3. Third pattern names the gap.\n" +
  "4. Fourth point that must not render.\n" +
  "5. Fifth point that must not render.\n" +
  "\n**Verdict**\nJokic leads qualified passers.";

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

describe("aqbatch2 answer quality", () => {
  it("A1 percentile column suppressed, every header human", () => {
    const html = renderToStaticMarkup(React.createElement(DataTable, { rows: LEADERS_WITH_PCT }));
    const heads = [...html.matchAll(/Sort by ([A-Za-z/#%][^"<]*)/g)].map((m) => m[1]);
    assert.ok(!heads.includes("PERCENTILE"));
    assert.ok(!heads.includes("Pct"));
    assert.ok(!/<th[^>]*>[^<]*PERCENTILE/.test(html));
    assert.ok(!/<th[^>]*>[^<]*Pct<\//.test(html));
    assert.ok(heads.includes("Assists") && heads.includes("Games") && heads.includes("Minutes"));
    assert.ok(html.includes("Nikola Jokic") && html.includes("697"));
  });

  it("A2 title-only historical table flattens to rows, no JSON blob", () => {
    const html = renderToStaticMarkup(React.createElement(DataArtifacts, { ai: titleOnlyHistAi() }));
    assert.ok(html.includes("Chris Paul"));
    assert.ok(html.includes("Rajon Rondo"));
    assert.ok(!html.includes("[{&quot;"));
    assert.ok(!html.includes("player&quot;"));
  });

  it("A2 string-encoded historical rows parse to rows", () => {
    const html = renderToStaticMarkup(React.createElement(DataArtifacts, { ai: stringRowsHistAi() }));
    assert.ok(html.includes("Chris Paul"));
    assert.ok(!html.includes("[{&quot;"));
  });

  it("A4 takeaways capped, verdict intact", () => {
    const html = renderToStaticMarkup(React.createElement(AnswerText, { text: TAKEAWAY_BLOB }));
    assert.ok(html.includes("Second pattern holds across eras."));
    assert.ok(html.includes("Third pattern names the gap."));
    assert.ok(!html.includes("Fourth point that must not render."));
    assert.ok(!html.includes("Fifth point that must not render."));
    assert.ok(!html.includes("8.5 by Damian Lillard"));
    assert.ok(html.includes("11.7 assists per game by Rajon Rondo"));
    assert.ok(html.includes("Jokic leads qualified passers."));
  });

  it("A5 failed steps hidden from activity surfaces", () => {
    const agent = renderToStaticMarkup(
      React.createElement(AgentActivity, { ai: aiWithFailedCall() }),
    );
    assert.ok(!agent.includes("warehouse read failed"));
    assert.ok(!agent.includes("✗"));
    assert.ok(agent.includes("Used 1 tool"));
    const timeline = renderToStaticMarkup(
      React.createElement(ActivityTimeline, { items: failedActivity(), running: false }),
    );
    assert.ok(!timeline.includes("unavailable"));
    assert.ok(!timeline.includes(">Failed<"));
    assert.ok(timeline.includes("Used 1 tool"));
  });
});

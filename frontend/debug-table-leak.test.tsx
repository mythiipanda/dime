import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import DataArtifacts from "./components/DataArtifacts";
import DataTable from "./components/DataTable";
import type { AiMessage } from "./lib/chat";

function twoTableAi(): AiMessage {
  return {
    text: "answer",
    done: true,
    nodes: {
      tools: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: [
          {
            tool: "get_leaders",
            rows: [{ PLAYER: "Marek Voss", TEAM: "DEN", PTS: 30 }],
            meta: { source: "warehouse" },
          },
          {
            tool: "get_hustle",
            rows: [{ PLAYER: "Tariq Bell", TEAM: "GSW", PTS: 8 }],
            meta: { source: "warehouse" },
          },
        ] as never,
      },
    },
  };
}

function runPythonAi(printed: string): AiMessage {
  return {
    text: "answer",
    done: true,
    nodes: {
      tools: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: [
          {
            tool: "run_python",
            rows: { printed },
            meta: { source: "warehouse" },
          },
        ] as never,
      },
    },
  };
}

describe("debug-table leak", () => {
  it("no Fetched datasets tab strip with 2 tables, page controls remain", () => {
    const html = renderToStaticMarkup(React.createElement(DataArtifacts, { ai: twoTableAi() }));
    assert.ok(!html.includes("Fetched datasets"), "tab strip heading leaked");
    assert.ok(!html.includes("get_leaders"), "raw tool name leaked");
    assert.ok(!html.includes("get_hustle"), "raw tool name leaked");
    assert.ok(!html.includes("dataset 1"), "dataset fallback leaked");
    assert.ok(!html.includes("dataset 2"), "dataset fallback leaked");
    assert.ok(html.includes("Prev"), "Prev page control missing");
    assert.ok(html.includes("Next"), "Next page control missing");
    assert.ok(html.includes("1/2"), "page indicator missing");
  });

  it("printed/out headers render human labels", () => {
    const printedHtml = renderToStaticMarkup(
      React.createElement(DataTable, { rows: [{ printed: "some output" }] })
    );
    assert.ok(!printedHtml.includes(">printed<"), "raw printed header leaked");
    const outHtml = renderToStaticMarkup(
      React.createElement(DataTable, { rows: [{ out: "some output" }] })
    );
    assert.ok(!outHtml.includes(">out<"), "raw out header leaked");
    assert.ok(
      printedHtml.includes(">Output<") || outHtml.includes(">Output<"),
      "human Output header missing"
    );
  });

  it("run_python stdout scrubs warehouse names and bare repr", () => {
    const html = renderToStaticMarkup(
      React.createElement(DataArtifacts, {
        ai: runPythonAi("[(\u0027silver_hist_standings\u0027,), (\u0027bronze_raw\u0027,)]"),
      })
    );
    assert.ok(!html.includes("silver_"), "silver_ warehouse name leaked");
    assert.ok(!html.includes("bronze_"), "bronze_ warehouse name leaked");
    assert.ok(!html.includes("ext_"), "ext_ warehouse name leaked");
    assert.ok(!html.includes("silver_hist_standings"), "full table name leaked");
  });

  it("run_python readable stdout still renders", () => {
    const html = renderToStaticMarkup(
      React.createElement(DataArtifacts, {
        ai: runPythonAi("Average points per game: 114.2, up 2.1 from last month."),
      })
    );
    assert.ok(html.includes("Average points per game"), "readable stdout missing");
  });
});

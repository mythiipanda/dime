import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import CitedAnswerText, {
  CiteTable,
  ContextPills,
describe("source table", () => {
  it("shows the actual numbers in plain words", () => {
    const sources = evidenceSources(aiWith(PASS_CARRY, TEAM_TABLES));
    const html = renderToStaticMarkup(React.createElement(CiteTable, { source: sources[0] }));
    assert.ok(html.includes("Boston"));
    assert.ok(html.includes("9.4"));
    assert.ok(html.includes("points per 100 possessions"));
    assert.ok(html.includes("Team ratings, 2024-25 season"));
    for (const token of BANNED) assert.ok(!html.includes(token), "leaked " + token);
  });
});

describe("unverified note", () => {
  it("states one quiet sentence for a partial check", () => {
    const ai = aiWith(
      {
        verification: "pass",
        verified_claims: 1,
        gaps: [{ kind: "missing_evidence" }],
        output_statuses: [
          { output_id: "apg", status: "incomplete" },
          { output_id: "rpg", status: "incomplete" },
        ],
      },
      TEAM_TABLES,
    );
    const html = renderToStaticMarkup(React.createElement(UnverifiedNote, { ai }));
    assert.equal(html.includes("2 numbers couldn&#x27;t be traced to source data."), true);
  });

  it("states one quiet sentence for total failure", () => {
    const ai = aiWith(
      { verification: "partial", verified_claims: 0, gaps: [{ kind: "run_timeout" }] },
      [],
    );
    const html = renderToStaticMarkup(React.createElement(UnverifiedNote, { ai }));
    assert.ok(html.includes("Dime couldn&#x27;t check this answer — the run ran out of time."));
    assert.ok(!html.includes("NOT VERIFIED"));
  });

  it("renders nothing without any signal", () => {
    const html = renderToStaticMarkup(
      React.createElement(UnverifiedNote, { ai: aiWith(undefined, []) }),
    );
    assert.equal(html, "");
  });
});

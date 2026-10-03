import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import CitedAnswerText, {
  CiteTable,
  EvidenceLedger,
  UnverifiedNote,
} from "./components/CitedAnswerText";
import { evidenceSources } from "./lib/evidence";
import type { AiMessage } from "./lib/chat";

function aiWith(carry: unknown, tables: unknown[]): AiMessage {
  return {
    text: "answer",
    done: true,
    carry: carry as AiMessage["carry"],
    nodes: {
      analytics: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: tables as never,
      },
    },
  };
}

const TEAM_TABLES = [
  {
    output_id: "NET_RATING",
    subject_type: "team",
    subject_id: "BOS",
    value: "9.4",
    unit: "points_per_100_possessions",
    provenance: { capability: "team_ratings", season: "2024-25" },
  },
  {
    output_id: "OFF_RATING",
    subject_type: "team",
    subject_id: "BOS",
    value: "118.2",
    unit: "points_per_100_possessions",
    provenance: { capability: "team_ratings", season: "2024-25" },
  },
];

const ANSWER_TEXT =
  "Boston finished the season with a 9.4 net rating and a 118.2 offensive rating.";

const PASS_CARRY = { verification: "pass", verified_claims: 2, gaps: [] };

const BANNED = [
  "VERIFIED ANSWER",
  "PARTIAL ANSWER",
  "UNVERIFIED ANSWER",
  "NOT VERIFIED",
  "findings",
  "verified_claims",
  "output_id",
  "Ppg",
  "Apg",
  "get_",
];

describe("cited answer", () => {
  it("renders backed numbers with quiet markers", () => {
    const html = renderToStaticMarkup(
      React.createElement(CitedAnswerText, { text: ANSWER_TEXT, ai: aiWith(PASS_CARRY, TEAM_TABLES) }),
    );
    assert.ok(html.includes("cite-marker"));
    assert.ok(html.includes("9.4"));
    assert.ok(html.includes("118.2"));
  });

  it("leaves unbacked numbers alone", () => {
    const html = renderToStaticMarkup(
      React.createElement(CitedAnswerText, { text: "Boston won 64 games.", ai: aiWith(PASS_CARRY, TEAM_TABLES) }),
    );
    assert.ok(!html.includes("cite-marker"));
  });

  it("never leaks machine ids or status language", () => {
    const html = renderToStaticMarkup(
      React.createElement(CitedAnswerText, { text: ANSWER_TEXT, ai: aiWith(PASS_CARRY, TEAM_TABLES) }),
    );
    for (const token of BANNED) assert.ok(!html.includes(token), "leaked " + token);
  });

  it("shows the quiet sentence under a partial answer", () => {
    const ai = aiWith(
      {
        verification: "pass",
        verified_claims: 1,
        gaps: [{ kind: "missing_evidence" }],
        output_statuses: [{ output_id: "apg", status: "incomplete" }],
      },
      TEAM_TABLES,
    );
    const html = renderToStaticMarkup(
      React.createElement(CitedAnswerText, { text: ANSWER_TEXT, ai }),
    );
    assert.ok(html.includes("1 number couldn&#x27;t be traced to source data."));
    assert.ok(!html.includes("NOT VERIFIED"));
  });
});

describe("claim anchors", () => {
  const tables = [
    {
      output_id: "PLAYER_NAME",
      subject_type: "player",
      subject_id: "1629027",
      subject_display_name: "Trae Young",
      value: "Trae Young",
      unit: "unitless",
      provenance: { capability: "qualified_leaders", season: "2024-25" },
    },
    {
      output_id: "AST",
      subject_type: "player",
      subject_id: "1629027",
      subject_display_name: "Trae Young",
      value: "880",
      unit: "count",
      provenance: { capability: "qualified_leaders", season: "2024-25" },
    },
  ];
  const text = "Trae Young led the league with 880 assists. He also won 64 games.";
  const ai = aiWith(PASS_CARRY, tables);

  it("anchors admitted claims and skips unbound prose", () => {
    const html = renderToStaticMarkup(React.createElement(CitedAnswerText, { text, ai }));
    const markers = html.match(/cite-marker/g) || [];
    assert.equal(markers.length, 1);
    assert.ok(html.includes("880"));
  });

  it("every anchor lands on a matching ledger row", () => {
    const html = renderToStaticMarkup(React.createElement(CitedAnswerText, { text, ai }));
    for (const index of ["0", "1"]) {
      assert.ok(html.includes(`id="cite-${index}"`), "missing row " + index);
    }
    assert.ok(html.includes("Trae Young"));
    assert.ok(html.includes("880"));
  });

  it("anchor labels carry claim detail", () => {
    const html = renderToStaticMarkup(React.createElement(CitedAnswerText, { text, ai }));
    assert.ok(html.includes("Show source: Trae Young"));
    assert.ok(html.includes("League leaders, 2024-25 season"));
  });

  it("ledger lists every source even without markers", () => {
    const sources = evidenceSources(ai);
    const html = renderToStaticMarkup(
      React.createElement(EvidenceLedger, { sources, openIndex: null }),
    );
    assert.ok(html.includes("Trae Young"));
    assert.ok(html.includes("880"));
  });
});

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

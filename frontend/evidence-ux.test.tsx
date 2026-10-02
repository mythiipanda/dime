import { describe, it } from "node:test";
import * as assert from "node:assert";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import VerificationBadge from "./components/VerificationBadge";
import EvidenceSection from "./components/EvidenceSection";
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

const CLAIM = {
  output_id: "ppg",
  subject_type: "player",
  subject_id: "LeBron James",
  value: "27.1",
  unit: "points per game",
  provenance: { capability: "get_leaders", season: "2024-25", as_of: "2025-04-14" },
};

const PASS_CARRY = { verification: "pass", verified_claims: 2, gaps: [] };

describe("VerificationBadge", () => {
  it("renders nothing without a verdict", () => {
    assert.equal(VerificationBadge({ ai: aiWith(undefined, []) }), null);
  });

  it("shows verified with counts", () => {
    const html = renderToStaticMarkup(
      React.createElement(VerificationBadge, { ai: aiWith(PASS_CARRY, [CLAIM, CLAIM]) }),
    );
    assert.ok(html.includes("Verified"));
    assert.ok(html.includes("2 of 2"));
    assert.ok(!html.includes("verified_claims"));
    assert.ok(!html.includes("verification"));
  });

  it("shows partial progress", () => {
    const html = renderToStaticMarkup(
      React.createElement(VerificationBadge, {
        ai: aiWith(
          {
            verification: "partial",
            verified_claims: 1,
            gaps: [{ kind: "missing_evidence" }],
            output_statuses: [
              { output_id: "ppg", status: "complete" },
              { output_id: "apg", status: "incomplete" },
            ],
          },
          [CLAIM],
        ),
      }),
    );
    assert.ok(html.includes("Some verified"));
    assert.ok(html.includes("1 of 2"));
  });

  it("says it could not verify when nothing was backed", () => {
    const html = renderToStaticMarkup(
      React.createElement(VerificationBadge, {
        ai: aiWith({ verification: "partial", verified_claims: 0, gaps: [{ kind: "missing_evidence" }] }, []),
      }),
    );
    assert.ok(html.includes("Could not verify"));
  });

  it("never implies verification happened when it did not", () => {
    const html = renderToStaticMarkup(
      React.createElement(VerificationBadge, {
        ai: aiWith({ verification: "partial", verified_claims: 0, gaps: [{ kind: "missing_evidence" }] }, []),
      }),
    );
    assert.ok(!html.includes("Verified ·"));
    assert.ok(!html.includes("Some verified"));
  });
});

describe("EvidenceSection", () => {
  it("renders nothing without rows", () => {
    const html = renderToStaticMarkup(
      React.createElement(EvidenceSection, { ai: aiWith(PASS_CARRY, []) }),
    );
    assert.equal(html, "");
  });

  it("shows the claim, value, and source when open", () => {
    const html = renderToStaticMarkup(
      React.createElement(EvidenceSection, { ai: aiWith(PASS_CARRY, [CLAIM]), defaultOpen: true }),
    );
    assert.ok(html.includes("LeBron James"));
    assert.ok(html.includes("27.1"));
    assert.ok(html.includes("Leaders"));
    assert.ok(html.includes("2024-25"));
    assert.ok(html.includes("Sources"));
  });

  it("hides rows when closed but keeps the toggle", () => {
    const html = renderToStaticMarkup(
      React.createElement(EvidenceSection, { ai: aiWith(PASS_CARRY, [CLAIM]), defaultOpen: false }),
    );
    assert.ok(html.includes("Sources"));
    assert.ok(!html.includes("LeBron James"));
  });

  it("opens by default when something failed verification", () => {
    const html = renderToStaticMarkup(
      React.createElement(EvidenceSection, {
        ai: aiWith(
          {
            verification: "partial",
            verified_claims: 1,
            gaps: [{ kind: "missing_evidence" }],
            output_statuses: [
              { output_id: "ppg", status: "complete" },
              { output_id: "apg", status: "incomplete" },
            ],
          },
          [CLAIM],
        ),
      }),
    );
    assert.ok(html.includes("No data covered this."));
  });

  it("stays closed by default when everything was backed", () => {
    const html = renderToStaticMarkup(
      React.createElement(EvidenceSection, { ai: aiWith(PASS_CARRY, [CLAIM]) }),
    );
    assert.ok(html.includes("Sources"));
    assert.ok(!html.includes("LeBron James"));
  });

  it("never leaks field names into copy", () => {
    const html = renderToStaticMarkup(
      React.createElement(EvidenceSection, { ai: aiWith(PASS_CARRY, [CLAIM]), defaultOpen: true }),
    );
    assert.ok(!html.includes("verified_claims"));
    assert.ok(!html.includes("output_id"));
    assert.ok(!html.includes("unitless"));
  });
});

import assert from "node:assert/strict";
import test from "node:test";
import {
  badgeText,
  badgeState,
  evidenceRows,
  gapMessage,
  humanize,
  summarizeEvidence,
} from "./evidence";
import type { AiMessage } from "./chat";

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

const CLAIM_TABLE = {
  output_id: "ppg",
  subject_type: "player",
  subject_id: "LeBron James",
  value: "27.1",
  unit: "points per game",
  provenance: { capability: "get_leaders", season: "2024-25", as_of: "2025-04-14" },
};

const CALC_TABLE = {
  output_id: "net_rating",
  input_value: "5.3",
  provenance: { capability: "get_team_stats", season: "2024-25", as_of: "2025-04-14" },
};

const PASS_TWO = { verification: "pass", verified_claims: 2, gaps: [] };

test("pass with all claims backed is verified", () => {
  assert.equal(
    badgeState({ verification: "pass", verified_claims: 2, gaps: [] }),
    "verified",
  );
});

test("pass with gaps is partial", () => {
  assert.equal(
    badgeState({
      verification: "pass",
      verified_claims: 2,
      gaps: [{ kind: "missing_evidence" }],
    }),
    "partial",
  );
});

test("zero backed claims is unverified", () => {
  assert.equal(
    badgeState({ verification: "partial", verified_claims: 0, gaps: [{ kind: "missing_evidence" }] }),
    "unverified",
  );
});

test("missing carry is unknown", () => {
  assert.equal(badgeState(undefined), "unknown");
  assert.equal(badgeState(null), "unknown");
});

test("carry without any signal is unknown", () => {
  assert.equal(badgeState({}), "unknown");
});

test("backed claims without a pass verdict are partial", () => {
  assert.equal(
    badgeState({ verification: "partial", verified_claims: 1, gaps: [] }),
    "partial",
  );
});

test("humanize turns snake case into plain words", () => {
  assert.equal(humanize("get_leaders"), "Leaders");
  assert.equal(humanize("ppg_leaders"), "Ppg leaders");
  assert.equal(humanize("fetch_historical-stats"), "Historical stats");
  assert.equal(humanize(""), "");
});

test("gap messages use plain words", () => {
  assert.equal(gapMessage("missing_evidence"), "No data covered this.");
  assert.equal(gapMessage("source_conflict"), "Sources disagreed on this.");
  assert.equal(gapMessage("run_timeout"), "The run ran out of time.");
  assert.equal(gapMessage("something_new"), "Something new.");
  assert.equal(gapMessage(""), "No reason given.");
});

test("gap messages never leak field names", () => {
  for (const kind of ["missing_evidence", "unsupported_claim", "execution_failure", "synthesis_incomplete", "judge_unavailable"]) {
    assert.ok(!gapMessage(kind).includes("verified_claims"));
  }
});

test("claim tables become one row per claim", () => {
  const rows = evidenceRows(aiWith({ verification: "pass", verified_claims: 1, gaps: [] }, [CLAIM_TABLE]));
  assert.equal(rows.length, 1);
  assert.equal(rows[0].ok, true);
  assert.equal(rows[0].finding, "LeBron James");
  assert.ok(rows[0].detail.includes("Ppg"));
  assert.equal(rows[0].value, "27.1 points per game");
  assert.ok(rows[0].source.includes("Leaders"));
  assert.ok(rows[0].source.includes("2024-25"));
  assert.ok(rows[0].source.includes("2025-04-14"));
});

test("unitless values render without a unit", () => {
  const rows = evidenceRows(
    aiWith({}, [{ ...CLAIM_TABLE, unit: "unitless" }]),
  );
  assert.equal(rows[0].value, "27.1");
});

test("calculation input tables render their input value", () => {
  const rows = evidenceRows(aiWith({}, [CALC_TABLE]));
  assert.equal(rows.length, 1);
  assert.equal(rows[0].value, "5.3");
  assert.ok(rows[0].source.includes("2024-25"));
});

test("incomplete outputs become not-verified rows with reasons", () => {
  const ai = aiWith(
    {
      verification: "partial",
      verified_claims: 1,
      gaps: [{ kind: "missing_evidence" }],
      output_statuses: [
        { output_id: "ppg", status: "complete" },
        { output_id: "apg", status: "incomplete" },
      ],
    },
    [CLAIM_TABLE],
  );
  const rows = evidenceRows(ai);
  assert.equal(rows.length, 2);
  const missing = rows.find((r) => r.finding === "Apg");
  assert.ok(missing);
  assert.equal(missing.ok, false);
  assert.equal(missing.detail, "No data covered this.");
});

test("legacy tool tables render a source row", () => {
  const rows = evidenceRows(
    aiWith({}, [
      { tool: "get_leaders", meta: { source: "warehouse", season: "2024-25" } },
    ]),
  );
  assert.equal(rows.length, 1);
  assert.equal(rows[0].ok, true);
  assert.ok(rows[0].source.includes("2024-25"));
});

test("non-evidence tables are ignored", () => {
  assert.deepEqual(evidenceRows(aiWith({}, [{ nonsense: true }])), []);
  assert.deepEqual(evidenceRows(aiWith({}, [])), []);
});

test("summary counts backed against total", () => {
  const summary = summarizeEvidence(
    aiWith(
      {
        verification: "partial",
        verified_claims: 1,
        gaps: [{ kind: "missing_evidence" }],
        output_statuses: [
          { output_id: "ppg", status: "complete" },
          { output_id: "apg", status: "incomplete" },
        ],
      },
      [CLAIM_TABLE],
    ),
  );
  assert.equal(summary.state, "partial");
  assert.equal(summary.backed, 1);
  assert.equal(summary.total, 2);
});

test("badge text uses plain words and counts", () => {
  assert.equal(badgeText({ state: "verified", backed: 3, total: 3, gaps: [], rows: [] }), "Verified · 3 of 3 findings");
  assert.equal(badgeText({ state: "partial", backed: 2, total: 3, gaps: [], rows: [] }), "Some verified · 2 of 3 findings");
  assert.equal(badgeText({ state: "unverified", backed: 0, total: 2, gaps: [], rows: [] }), "Could not verify");
  assert.equal(badgeText({ state: "unknown", backed: 0, total: 0, gaps: [], rows: [] }), "");
});

test("badge text never leaks field names", () => {
  for (const state of ["verified", "partial", "unverified"] as const) {
    const text = badgeText({ state, backed: 1, total: 2, gaps: [], rows: [] });
    assert.ok(!text.includes("verified_claims"));
    assert.ok(!text.includes("verification"));
    assert.ok(!text.includes("claim"));
  }
});

test("tables without carry stay unknown, rows still listed", () => {
  const summary = summarizeEvidence(aiWith(undefined, [CLAIM_TABLE]));
  assert.equal(summary.state, "unknown");
  assert.equal(summary.backed, 1);
  assert.equal(evidenceRows(aiWith(undefined, [CLAIM_TABLE])).length, 1);
});

test("gaps without outputs become one row per gap", () => {
  const ai = aiWith(
    { verification: "partial", verified_claims: 0, gaps: [{ kind: "run_timeout" }] },
    [],
  );
  const rows = evidenceRows(ai);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].ok, false);
  assert.equal(rows[0].finding, "This answer");
  assert.equal(rows[0].detail, "The run ran out of time.");
  assert.equal(summarizeEvidence(ai).state, "unverified");
});

test("claim rows name the subject type", () => {
  const rows = evidenceRows(aiWith({ verification: "pass", verified_claims: 1, gaps: [] }, [CLAIM_TABLE]));
  assert.equal(rows[0].detail, "Player · Ppg");
});

test("carry counts set the badge numbers", () => {
  const summary = summarizeEvidence(aiWith(PASS_TWO, [CLAIM_TABLE]));
  assert.equal(summary.backed, 2);
  assert.equal(summary.total, 2);
});

test("empty answer with no signal is unknown", () => {
  const summary = summarizeEvidence(aiWith(undefined, []));
  assert.equal(summary.state, "unknown");
});

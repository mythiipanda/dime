import assert from "node:assert/strict";
import { test } from "node:test";
import { auditAnswerNumbers, createVerifyAnswerNumbersTool } from "./dist/verify-answer.js";

function makeSourceRecord(ref, { rows = [], isError = false, error } = {}) {
  const result = error !== undefined ? { rows, error } : { rows };
  return {
    ref,
    callId: "call-" + ref,
    tool: "sql_exec",
    response: {
      content: [{ type: "text", text: JSON.stringify(result) }],
      structuredContent: result,
      isError,
    },
  };
}

test("auditAnswerNumbers matches supported literals across units and flags unsupported claims", () => {
  const sources = [
    makeSourceRecord("src-1", {
      rows: [{ player: "Luka Doncic", pts: 33.9, ts_pct: 0.637, salary: 19512195, gp: 76 }],
    }),
    makeSourceRecord("failed", { rows: [{ pts: 9999 }], isError: true, error: "bad query" }),
  ];
  const audit = auditAnswerNumbers(
    {
      blocks: [
        {
          text: "Luka Doncic averaged 33.9 points on 63.7% true shooting in 2025-26. Salary was $19.51M over 76 games, with 9999 rebounds.",
        },
      ],
      artifacts: [
        {
          kind: "compare",
          title: "Compare",
          aName: "Luka Doncic",
          bName: "Other Player",
          rows: [{ label: "Points", a: 33.9, b: 41.2 }],
        },
      ],
    },
    sources
  );
  const unsupported = audit.unsupported.map((claim) => claim.raw);
  assert.ok(audit.checked > 0);
  assert.ok(audit.supported > 0);
  assert.ok(unsupported.includes("9999"));
  assert.ok(unsupported.includes("41.2"));
  assert.equal(unsupported.includes("33.9"), false);
  assert.equal(unsupported.includes("63.7%"), false);
  assert.equal(unsupported.includes("$19.51M"), false);
  assert.equal(unsupported.includes("76"), false);
  assert.equal(audit.evidence_count > 0, true);
});

test("createVerifyAnswerNumbersTool returns a JSON audit without submitting", async () => {
  const source = makeSourceRecord("src-1", { rows: [{ pts: 30.5 }] });
  const tool = createVerifyAnswerNumbersTool(() => [source]);
  const result = await tool.execute("call-1", {
    blocks: [{ text: "The player scored 30.5 points and 12.3 assists." }],
  });
  const audit = JSON.parse(result.content[0].text);
  assert.equal(audit.checked > 0, true);
  assert.deepEqual(audit.unsupported.map((claim) => claim.raw), ["12.3"]);
  assert.equal(result.details.unsupported.length, 1);
});

test("auditAnswerNumbers does not flag question-echoed thresholds as missing_in_artifacts", () => {
  const sources = [
    makeSourceRecord("src-1", {
      rows: [
        { player: "Jimmy Butler III", ftm: 359, fta: 416, minutes: 1744.63, points: 1116 },
        { player: "Bam Adebayo", ftm: 283, fta: 354, minutes: 2142.58, points: 1197 },
      ],
    }),
  ];
  const audit = auditAnswerNumbers(
    {
      blocks: [
        {
          text: "Qualifying thresholds: >=500 minutes and >=50 FTA. Ranked by FTA descending: Jimmy Butler III 416 FTA, Bam Adebayo 354 FTA.",
        },
      ],
      artifacts: [
        {
          kind: "table",
          title: "MIA Foul-Line Workload Shortlist",
          columns: [{ key: "player" }, { key: "fta" }],
          rows: [
            { player: "Jimmy Butler III", fta: 416 },
            { player: "Bam Adebayo", fta: 354 },
          ],
        },
      ],
    },
    sources,
    "Retain >=500 minutes and >=50 FTA; return the top five by FTA."
  );
  assert.equal(audit.missing_in_artifacts.length, 0);
});

test("auditAnswerNumbers still flags supported prose figures absent from artifacts", () => {
  const sources = [
    makeSourceRecord("src-1", {
      rows: [{ player: "Jimmy Butler III", ftm: 359, fta: 416 }],
    }),
  ];
  const audit = auditAnswerNumbers(
    {
      blocks: [{ text: "Jimmy Butler III attempted 416 free throws and made 359." }],
      artifacts: [
        {
          kind: "table",
          title: "FTA leaders",
          columns: [{ key: "player" }, { key: "fta" }],
          rows: [{ player: "Jimmy Butler III", fta: 416 }],
        },
      ],
    },
    sources,
    "Who led the team in free throws?"
  );
  assert.equal(audit.missing_in_artifacts.length, 1);
  assert.equal(audit.missing_in_artifacts[0].raw, "359");
});

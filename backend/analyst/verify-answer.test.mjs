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

test("auditAnswerNumbers covers derived aggregates from artifact rows", () => {
  const sources = [
    makeSourceRecord("src-1", {
      rows: [
        { unit: "A", min: 337, poss: 310, net_rating: 19.4 },
        { unit: "B", min: 120, poss: 105, net_rating: -13.4 },
        { unit: "C", min: 98, poss: 90, net_rating: 8.2 },
        { unit: "D", min: 40, poss: 36, net_rating: 2.1 },
        { unit: "E", min: 20, poss: 18, net_rating: -1.0 },
        { unit: "F", min: 15, poss: 14, net_rating: 4.0 },
      ],
    }),
  ];
  const audit = auditAnswerNumbers(
    {
      blocks: [
        {
          text: "6 qualifying units combined for 630 minutes. The possession-weighted average net rating across them is 3.16. The top unit's 337 minutes set the pace.",
        },
      ],
      artifacts: [
        {
          kind: "table",
          title: "MIL top units",
          columns: [{ key: "unit" }, { key: "min" }, { key: "poss" }, { key: "net_rating" }],
          rows: [
            { unit: "A", min: 337, poss: 310, net_rating: 19.4 },
            { unit: "B", min: 120, poss: 105, net_rating: -13.4 },
            { unit: "C", min: 98, poss: 90, net_rating: 8.2 },
            { unit: "D", min: 40, poss: 36, net_rating: 2.1 },
            { unit: "E", min: 20, poss: 18, net_rating: -1.0 },
            { unit: "F", min: 15, poss: 14, net_rating: 4.0 },
          ],
        },
      ],
    },
    sources,
    "How many units qualify, what are their combined minutes, and the possession-weighted net?"
  );
  assert.equal(audit.missing_in_artifacts.length, 0, JSON.stringify(audit.missing_in_artifacts.map(c => c.raw)));
});

test("auditAnswerNumbers still flags headline figures not derivable from artifacts", () => {
  const sources = [
    makeSourceRecord("src-1", {
      rows: [{ pool_size: 104 }, { unit: "A", min: 337 }, { unit: "B", min: 120 }, { unit: "C", min: 98 }],
    }),
  ];
  const audit = auditAnswerNumbers(
    {
      blocks: [{ text: "104 lineups qualified for the pool; the top unit logged 337 minutes." }],
      artifacts: [
        {
          kind: "table",
          title: "Top units",
          columns: [{ key: "unit" }, { key: "min" }],
          rows: [
            { unit: "A", min: 337 },
            { unit: "B", min: 120 },
            { unit: "C", min: 98 },
          ],
        },
      ],
    },
    sources,
    "How many lineups qualify and which played most?"
  );
  assert.equal(audit.missing_in_artifacts.length, 1);
  assert.equal(audit.missing_in_artifacts[0].raw, "104");
});

test("bounded and approximate claims count as supported when evidence satisfies the bound", () => {
  const sources = [
    makeSourceRecord("src-1", {
      rows: [{ player: "Nikola Jokic", on_poss: 9195, off_poss: 5026, net: 10.7 }],
    }),
  ];
  const audit = auditAnswerNumbers(
    {
      blocks: [
        {
          text: "The sample is robust with over 5,000 possessions in the off state and more than 9,000 on. Net rating was about 10.7 per 100, under 12 overall. Fabricated claim: over 10,000 off possessions.",
        },
      ],
      artifacts: [],
    },
    sources
  );
  const raws = audit.unsupported_claims.map(flag => flag.split(" (near")[0]);
  assert.equal(raws.includes("5,000"), false, raws.join("|"));
  assert.equal(raws.includes("9,000"), false, raws.join("|"));
  assert.equal(raws.includes("10.7"), false, raws.join("|"));
  assert.equal(raws.includes("12"), false, raws.join("|"));
  assert.equal(raws.includes("100"), false, "per-100 rate unit must not flag: " + raws.join("|"));
  assert.ok(raws.includes("10,000"), "false bounded claim must still flag: " + raws.join("|"));
});

test("formatting-instruction clauses are not unevidenced asks", () => {
  const sources = [
    makeSourceRecord("src-1", {
      rows: [{ player: "Nikola Jokic", on_net: 6.1, off_net: -4.6 }],
    }),
  ];
  const audit = auditAnswerNumbers(
    {
      blocks: [{ text: "On net rating 6.1 per 100, off -4.6 per 100." }],
      artifacts: [],
    },
    sources,
    "How does Denver perform with Jokic on vs off? Report per-100 numbers to one decimal."
  );
  const flags = audit.unevidenced_asks.join(" | ");
  assert.equal(flags.includes("decimal"), false, flags);
});

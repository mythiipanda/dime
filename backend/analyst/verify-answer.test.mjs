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
      rows: [{ pool_size: 104 }, { unit: "A", min: 337, pts: 52.3 }, { unit: "B", min: 120 }, { unit: "C", min: 98 }],
    }),
  ];
  const audit = auditAnswerNumbers(
    {
      blocks: [{ text: "104 lineups qualified for the pool; the top unit averaged 52.3 points." }],
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
  assert.equal(audit.missing_in_artifacts[0].raw, "52.3");
});

test("auditAnswerNumbers does not flag qualifying-cohort counts as missing_in_artifacts", () => {
  const sources = [
    makeSourceRecord("src-1", {
      rows: [
        { lineup: "A", min: 200, def_rating: 93.2 },
        { lineup: "B", min: 190, def_rating: 93.6 },
        { lineup: "C", min: 180, def_rating: 94.9 },
        { lineup: "D", min: 170, def_rating: 99.6 },
        { lineup: "E", min: 160, def_rating: 100.0 },
        { qualifying_rows: 71 },
      ],
    }),
  ];
  const audit = auditAnswerNumbers(
    {
      blocks: [
        {
          text: "**71 lineups** met the 120-minute floor. The best defensive unit posted a 93.2 defensive rating, ahead of 93.6 and 94.9.",
        },
      ],
      artifacts: [
        {
          kind: "table",
          title: "Top-5 defensive lineups",
          columns: [{ key: "lineup" }, { key: "min" }, { key: "def_rating" }],
          rows: [
            { lineup: "A", min: 200, def_rating: 93.2 },
            { lineup: "B", min: 190, def_rating: 93.6 },
            { lineup: "C", min: 180, def_rating: 94.9 },
            { lineup: "D", min: 170, def_rating: 99.6 },
            { lineup: "E", min: 160, def_rating: 100.0 },
          ],
        },
      ],
    },
    sources,
    "Top five defensive lineups at the 120-minute floor; how many lineups qualified?"
  );
  const raws = audit.missing_in_artifacts.map(c => c.raw);
  assert.equal(raws.includes("71"), false, JSON.stringify(raws));
});

test("provenance ref UUID digits do not become numeric claims", () => {
    const sources = [
        makeSourceRecord("src-1", { rows: [{ player: "A", possessions: 4592, off_rtg: 110.2 }] }),
    ];
    const audit = auditAnswerNumbers(
        {
            blocks: [
                {
                    text: "Lineup A posted a 110.2 offensive rating over 4,592 possessions. *Source: silver_stints (ref: f95f94db-4a14-4592-90a9-219a75ce9d3)*",
                },
            ],
            artifacts: [],
        },
        sources,
    );
    const unsupported = audit.unsupported_claims ?? [];
    assert(!unsupported.some(c => c.startsWith("4592") || c.includes("90a9")),
        `ref-uuid digits leaked into claims: ${unsupported.join(" | ")}`);
});

test("derived column totals over evidence rows are supported, wrong totals still flagged", () => {
    const sources = [
        makeSourceRecord("src-1", {
            rows: [
                { player: "A", possessions: 4800, points: 5100 },
                { player: "B", possessions: 5121, points: 5300 },
                { player: "C", possessions: 4300, points: 4900 },
            ],
        }),
    ];
    const audit = auditAnswerNumbers(
        {
            blocks: [
                {
                    text: "The trio shared 14,221 total possessions, averaging 4,740.3 each, with a spread of 821 between the highest and lowest workload. They combined for 15,999 points.",
                },
            ],
            artifacts: [],
        },
        sources,
    );
    const unsupported = audit.unsupported.map((claim) => claim.raw);
    assert.equal(unsupported.includes("14,221"), false, JSON.stringify(unsupported));
    assert.equal(unsupported.includes("821"), false, JSON.stringify(unsupported));
    assert.ok(unsupported.includes("15,999"), JSON.stringify(unsupported));
});

test("tiebreak instruction clauses are not uncovered asks", () => {
    const sources = [
        makeSourceRecord("src-1", {
            rows: [
                { lineup: "A", min: 940, net_rating: 3.3 },
                { lineup: "B", min: 714, net_rating: 3.2 },
            ],
        }),
    ];
    const audit = auditAnswerNumbers(
        {
            blocks: [
                {
                    text: "The most-used five-man unit was the Knicks group at 940 minutes with a +3.3 net rating, ahead of the Timberwolves unit at 714 minutes and +3.2.",
                },
            ],
            artifacts: [],
        },
        sources,
        "Which five-man units did coaches lean on hardest in 2024-25? Rank the league's five-man lineups by total minutes in the regular season and give me the top 5 — the five names, team, minutes, and net rating for each. Ties go to the higher net rating."
    );
    assert(!audit.uncovered_asks.some(c => /ties go/i.test(c)), JSON.stringify(audit.uncovered_asks));
});

test("content clauses sharing a sentence prefix with tiebreak phrasing still audit", () => {
    const sources = [makeSourceRecord("src-1", { rows: [{ pts: 30.5 }] })];
    const audit = auditAnswerNumbers(
        {
            blocks: [{ text: "Nothing relevant here." }],
            artifacts: [],
        },
        sources,
        "Rank the league's five-man lineups by total minutes and give the top 5 with names, team, minutes, and net rating. Ties go to the higher net rating."
    );
    assert.equal(audit.uncovered_asks.length, 1, JSON.stringify(audit.uncovered_asks));
});

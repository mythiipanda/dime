import assert from "node:assert/strict";
import test from "node:test";
import {
  capabilityLabel,
  statLabel,
  subjectName,
  contextPills,
  evidenceSources,
  unverifiedSummary,
  unverifiedValues,
  withCitationMarkers,
  withUnverifiedMarkers,
  gapMessage,
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
  output_id: "NET_RATING",
  subject_type: "team",
  subject_id: "BOS",
  value: "9.4",
  unit: "points_per_100_possessions",
  provenance: { capability: "team_ratings", season: "2024-25", as_of: "2025-04-14" },
};

const NAME_TABLE = {
  output_id: "PLAYER_NAME",
  subject_type: "player",
  subject_id: "1629027",
  value: "Trae Young",
  unit: "unitless",
  provenance: { capability: "qualified_leaders", season: "2024-25" },
};

test("capability labels use plain words", () => {
  assert.equal(capabilityLabel("get_leaders"), "League leaders");
  assert.equal(capabilityLabel("team_ratings"), "Team ratings");
  assert.equal(capabilityLabel("qualified_leaders"), "League leaders");
  assert.equal(capabilityLabel("get_win_prob"), "Win probability");
});

test("capability fallback strips get_ and title-cases", () => {
  assert.equal(capabilityLabel("get_foo_bar"), "Foo bar");
  assert.equal(capabilityLabel(""), "Data");
});

test("stat labels use plain words", () => {
  assert.equal(statLabel("NET_RATING"), "net rating");
  assert.equal(statLabel("ppg"), "points per game");
  assert.equal(statLabel("AST"), "assists");
  assert.equal(statLabel("PLAYER_NAME"), "");
});

test("stat fallback title-cases unknown ids", () => {
  assert.equal(statLabel("some_new_stat"), "Some new stat");
});

test("subject names resolve team abbreviations", () => {
  assert.equal(subjectName("team", "BOS"), "Boston");
  assert.equal(subjectName("team", "lal"), "LA Lakers");
  assert.equal(subjectName("team", "XYZ"), "XYZ");
});

test("subject names never show numeric entity ids", () => {
  assert.equal(subjectName("player", "1629027"), "");
  assert.equal(subjectName("player", "Trae Young"), "Trae Young");
  assert.equal(subjectName("player", null), "");
});

test("claim tables become plain-word sources", () => {
  const sources = evidenceSources(aiWith({}, [CLAIM_TABLE]));
  assert.equal(sources.length, 1);
  assert.equal(sources[0].subject, "Boston");
  assert.equal(sources[0].stat, "points per 100 possessions");
  assert.equal(sources[0].value, "9.4");
  assert.equal(sources[0].origin, "Team ratings, 2024-25 season");
});

test("name claims keep the name and skip the stat", () => {
  const sources = evidenceSources(aiWith({}, [NAME_TABLE]));
  assert.equal(sources.length, 1);
  assert.equal(sources[0].subject, "1629027");
  assert.equal(sources[0].value, "Trae Young");
  assert.equal(sources[0].stat, "");
  assert.equal(sources[0].origin, "League leaders, 2024-25 season");
});

test("tables prefer backend subject display names", () => {
  const table = { ...NAME_TABLE, subject_display_name: "Trae Young" };
  const sources = evidenceSources(aiWith({}, [table]));
  assert.equal(sources.length, 1);
  assert.equal(sources[0].subject, "Trae Young");
});

test("blank subject display names fall back to local labels", () => {
  const blank = { ...CLAIM_TABLE, subject_display_name: "" };
  const sources = evidenceSources(aiWith({}, [blank]));
  assert.equal(sources[0].subject, "Boston");
});

test("unknown subjects fall back to the raw id", () => {
  const table = { ...NAME_TABLE, subject_id: "9999999" };
  const sources = evidenceSources(aiWith({}, [table]));
  assert.equal(sources.length, 1);
  assert.equal(sources[0].subject, "9999999");
});

test("tables prefer backend display names", () => {
  const table = { ...CLAIM_TABLE, display_name: "Net rating" };
  const sources = evidenceSources(aiWith({}, [table]));
  assert.equal(sources.length, 1);
  assert.equal(sources[0].stat, "Net rating");
});

test("blank display names fall back to local labels", () => {
  const blank = { ...CLAIM_TABLE, display_name: "" };
  const numeric = { ...CLAIM_TABLE, display_name: 42 };
  const sources = evidenceSources(aiWith({}, [blank, numeric]));
  assert.equal(sources.length, 2);
  assert.equal(sources[0].stat, "points per 100 possessions");
  assert.equal(sources[1].stat, "points per 100 possessions");
});

test("context pills lead with the modal season then capabilities", () => {
  const tables = [
    CLAIM_TABLE,
    { ...CLAIM_TABLE, output_id: "OFF_RATING" },
    { ...CLAIM_TABLE, provenance: { capability: "get_leaders", season: "2023-24" } },
  ];
  assert.deepEqual(evidenceSources(aiWith({}, tables)).length, 3);
  assert.deepEqual(contextPills(aiWith({}, tables)), [
    "2024-25",
    "Team ratings",
    "League leaders",
  ]);
});

test("context pills cap capabilities and skip empties", () => {
  assert.deepEqual(contextPills(aiWith({}, [])), []);
  const tables = [{ ...CLAIM_TABLE, provenance: {} }];
  assert.deepEqual(contextPills(aiWith({}, tables)), []);
});

test("unverified values come from incomplete typed statuses only", () => {
  const carry = {
    output_statuses: [
      { output_id: "AST", status: "incomplete", value: "64" },
      { output_id: "OFF_RATING", status: "complete", value: "118.2" },
      { output_id: "PLAYER_NAME", status: "missing", value: "Trae Young" },
      { output_id: "APG", status: "incomplete" },
    ],
  };
  assert.deepEqual(unverifiedValues(aiWith(carry, []), []), ["64"]);
});

test("admitted values never count as unverified", () => {
  const carry = {
    output_statuses: [{ output_id: "AST", status: "incomplete", value: "880" }],
  };
  assert.deepEqual(unverifiedValues(aiWith(carry, []), ["880"]), []);
});

test("unverified markers land on literal occurrences with clean boundaries", () => {
  assert.equal(
    withUnverifiedMarkers("64 wins and 64 losses.", ["64"]),
    "64[?](#unverified) wins and 64[?](#unverified) losses.",
  );
  assert.equal(
    withUnverifiedMarkers("In the 2024-25 season, top 3.", ["24", "25", "3"]),
    "In the 2024-25 season, top 3.",
  );
  assert.equal(withUnverifiedMarkers("64 wins.", []), "64 wins.");
});

test("sources never leak machine ids", () => {
  const sources = evidenceSources(aiWith({}, [CLAIM_TABLE, NAME_TABLE]));
  const joined = JSON.stringify(sources);
  for (const token of ["output_id", "subject_id", "Ppg", "Apg", "Leaders", "verified_claims", "ppg", "NET_RATING", "points_per_100"]) {
    assert.ok(!joined.includes(token), "leaked " + token);
  }
});

test("markers attach to a number that appears exactly once", () => {
  const sources = evidenceSources(aiWith({}, [CLAIM_TABLE]));
  const out = withCitationMarkers("Boston finished with a 9.4 net rating.", sources);
  assert.equal(out, "Boston finished with a 9.4[¹](#cite-0) net rating.");
});

test("markers skip numbers that appear more than once", () => {
  const sources = evidenceSources(aiWith({}, [CLAIM_TABLE]));
  const out = withCitationMarkers("9.4 is the number, and 9.4 appears twice.", sources);
  assert.equal(out, "9.4 is the number, and 9.4 appears twice.");
});

test("markers skip values claimed by more than one source", () => {
  const other = { ...CLAIM_TABLE, output_id: "OFF_RATING", value: "9.4" };
  const sources = evidenceSources(aiWith({}, [CLAIM_TABLE, other]));
  const out = withCitationMarkers("Boston finished with a 9.4 net rating.", sources);
  assert.ok(!out.includes("#cite-"));
});

test("markers skip single digits and non-numeric values", () => {
  const sources = evidenceSources(aiWith({}, [CLAIM_TABLE, NAME_TABLE]));
  const out = withCitationMarkers("Trae Young is 1 of 1. Boston scored 9.4.", sources);
  assert.ok(out.includes("Trae Young is 1 of 1."));
  assert.ok(out.includes("[¹](#cite-0)"));
});

test("markers skip values absent from the text", () => {
  const sources = evidenceSources(aiWith({}, [CLAIM_TABLE]));
  const out = withCitationMarkers("Boston had a great season.", sources);
  assert.equal(out, "Boston had a great season.");
});

test("markers match numbers inside signed tokens", () => {
  const sources = evidenceSources(aiWith({}, [CLAIM_TABLE]));
  const out = withCitationMarkers("Boston finished +9.4 per 100.", sources);
  assert.equal(out, "Boston finished +9.4[¹](#cite-0) per 100.");
});

test("markers cap at nine sources", () => {
  const tables = Array.from({ length: 12 }, (_, i) => ({ ...CLAIM_TABLE, value: String(90 + i) + ".4" }));
  const sources = evidenceSources(aiWith({}, tables));
  const text = tables.map((t) => t.value).join(" ");
  const out = withCitationMarkers(text, sources);
  assert.ok(out.includes("#cite-8"));
  assert.ok(!out.includes("#cite-9"));
});

test("gap messages use plain words", () => {
  assert.equal(gapMessage("missing_evidence"), "No data covered this.");
  assert.equal(gapMessage("source_conflict"), "Sources disagreed on this.");
  assert.equal(gapMessage("run_timeout"), "The run ran out of time.");
  assert.equal(gapMessage("something_new"), "Something new.");
  assert.equal(gapMessage(""), "No reason given.");
});

test("partial check states one plain sentence", () => {
  const ai = aiWith(
    {
      verification: "pass",
      verified_claims: 1,
      gaps: [{ kind: "missing_evidence" }],
      output_statuses: [
        { output_id: "NET_RATING", status: "complete" },
        { output_id: "apg", status: "incomplete", subject_type: "player", subject_id: "1629027" },
      ],
    },
    [CLAIM_TABLE],
  );
  assert.equal(unverifiedSummary(ai), "1 number couldn't be traced to source data.");
});

test("total failure states one plain sentence", () => {
  const ai = aiWith(
    { verification: "partial", verified_claims: 0, gaps: [{ kind: "run_timeout" }] },
    [],
  );
  assert.equal(unverifiedSummary(ai), "Dime couldn't check this answer — the run ran out of time.");
});

test("multiple unchecked stats are counted, not listed", () => {
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
    [CLAIM_TABLE],
  );
  assert.equal(unverifiedSummary(ai), "2 numbers couldn't be traced to source data.");
});

test("no signal means no summary", () => {
  assert.equal(unverifiedSummary(aiWith({}, [])), null);
  assert.equal(unverifiedSummary(aiWith({ verification: "pass", verified_claims: 2, gaps: [] }, [CLAIM_TABLE])), null);
});

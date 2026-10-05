import assert from "node:assert/strict";
import test from "node:test";
import { gradeClaim, gradeLimits, type Grade, type GradeInput } from "./grades";

const GRADES: Grade[] = ["G1", "G2", "G3", "G4"];

test("totality: every input grades to exactly one grade", () => {
  const inputs: GradeInput[] = [
    {},
    { season: "2024-25" },
    { method: "Monte Carlo, 10,000 sims" },
    { method: "  " },
    { windowN: 12 },
    { windowN: 1 },
    { windowN: 5, windowKind: "meetings" },
    { windowN: 0 },
    { windowN: -3 },
    { lineage: "live", season: "2024-25" },
    { lineage: "warehouse", season: "2024-25" },
    { lineage: "warehouse" },
    { lineage: "mixed", season: "2024-25" },
    { method: "Box-score-estimated possessions", windowN: 12, lineage: "live" },
  ];
  for (const input of inputs) {
    const graded = gradeClaim(input);
    assert.ok(GRADES.includes(graded.grade), JSON.stringify(input));
  }
});

test("method always wins: estimated possessions over a slice grade G4", () => {
  const graded = gradeClaim({
    method: "Box-score-estimated possessions",
    windowN: 12,
    season: "2024-25",
  });
  assert.equal(graded.grade, "G4");
  assert.equal(graded.tag, "Model estimate");
  assert.equal(graded.method, "Box-score-estimated possessions");
});

test("live lineage never grades G1", () => {
  const graded = gradeClaim({ lineage: "live", season: "2024-25" });
  assert.notEqual(graded.grade, "G1");
});

test("windows grade G2, single games and meetings grade G3", () => {
  assert.equal(gradeClaim({ windowN: 12 }).grade, "G2");
  assert.equal(gradeClaim({ windowN: 12 }).tag, "Last 12 games");
  assert.equal(gradeClaim({ windowN: 1 }).grade, "G3");
  assert.equal(gradeClaim({ windowN: 5, windowKind: "meetings" }).tag, "5 meetings");
});

test("warehouse season grades quiet G1", () => {
  const graded = gradeClaim({ lineage: "warehouse", season: "2024-25" });
  assert.equal(graded.grade, "G1");
  assert.equal(graded.tag, "Full season");
  assert.equal(graded.scope, "Full season · 2024-25");
});

test("honest unknown grades G4 with the disclosure, never silence", () => {
  for (const input of [{}, { season: "2024-25" }, { lineage: "mixed" }]) {
    const graded = gradeClaim(input);
    assert.equal(graded.grade, "G4");
    assert.equal(graded.gap, "couldn't confirm the scope");
    assert.equal(graded.unknownScope, true);
  }
});

test("limits describe what each grade does not cover", () => {
  assert.equal(gradeLimits("G1", false), "Season totals hide recent form");
  assert.equal(gradeLimits("G2", false), "Window only, not the full season");
  assert.equal(gradeLimits("G3", false), "Small sample, treat as a hint");
  assert.equal(gradeLimits("G4", false), "Not observed results");
  assert.equal(gradeLimits("G4", true), "");
});

test("estimators grade G4 with their method line", () => {
  const methods = [
    "NBA box-score estimated possessions",
    "Pre-game estimate from 10,000 seeded simulations",
    "z-score title odds",
    "box prior shrinkage",
  ];
  for (const method of methods) {
    const graded = gradeClaim({ method, season: "2024-25" });
    assert.equal(graded.grade, "G4");
    assert.equal(graded.method, method);
  }
});

import assert from "node:assert/strict";
import test from "node:test";
import { isFailureFinal } from "./chat";










test("genuine answer with verified claims is not a failure", () => {
  assert.equal(
    isFailureFinal("LeBron James leads with 27.1 PPG.", {
      verification: "pass",
      verified_claims: 3,
      gaps: [],
    }),
    false,
  );
});

test("partial answer with some verified claims is not a failure", () => {
  assert.equal(
    isFailureFinal("Some numbers below.", {
      verification: "partial",
      verified_claims: 2,
      gaps: [{ kind: "missing_evidence" }],
    }),
    false,
  );
});

test("verification=failed is a failure even with non-empty text", () => {
  assert.equal(
    isFailureFinal("Some text.", { verification: "failed", verified_claims: 0 }),
    true,
  );
});

test("verification=verified is not a failure", () => {
  assert.equal(
    isFailureFinal("Answer.", { verification: "verified", verified_claims: 1 }),
    false,
  );
});

test("verification=pass wins over missing claims count", () => {
  assert.equal(isFailureFinal("Answer.", { verification: "pass" }), false);
});

test("partial without claims count falls back to prose matching", () => {
  assert.equal(
    isFailureFinal("I could not verify a publishable answer.", {
      verification: "partial",
    }),
    true,
  );
  assert.equal(
    isFailureFinal("A real answer.", { verification: "partial" }),
    false,
  );
});

test("non-empty text with no carry counts as recovered (older backends)", () => {
  assert.equal(isFailureFinal("An answer.", undefined), false);
  assert.equal(isFailureFinal("An answer.", null), false);
});



test("v2 exception fallback (verified_claims=0, execution_failure gap) is a failure", () => {
  assert.equal(
    isFailureFinal("I could not verify a publishable answer from the available data.", {
      verification: "partial",
      verified_claims: 0,
      structural_flags: [],
      gaps: [{ kind: "execution_failure" }],
    }),
    true,
  );
});

test("v2 fallback copy is a failure even without carry", () => {
  assert.equal(
    isFailureFinal("I could not verify a publishable answer from the available data."),
    true,
  );
});

test("v1 gap copy is a failure", () => {
  assert.equal(
    isFailureFinal(
      "I pulled the relevant data but could not verify the figures in the summary. The evidence panel below has the sourced results.",
      { verification: "partial", verified_claims: 0 },
    ),
    true,
  );
});

test("zero verified claims is a failure even with other text", () => {
  assert.equal(
    isFailureFinal("Something that looks like an answer.", {
      verification: "partial",
      verified_claims: 0,
      gaps: [{ kind: "synthesis_incomplete" }],
    }),
    true,
  );
});

test("empty final is a failure", () => {
  assert.equal(isFailureFinal("", undefined), true);
  assert.equal(isFailureFinal("   ", { verified_claims: 5 }), true);
});

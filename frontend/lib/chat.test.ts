import assert from "node:assert/strict";
import test from "node:test";
import { createStreamBatcher, isFailureFinal } from "./chat";










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

function manualScheduler() {
  const pending: (() => void)[] = [];
  return {
    pending,
    schedule: (flush: () => void) => {
      pending.push(flush);
    },
    run: () => {
      while (pending.length) pending.shift()!();
    },
  };
}

test("stream batcher coalesces rapid pushes into one ordered flush", () => {
  const sched = manualScheduler();
  const flushed: { type: string; data: unknown }[][] = [];
  const batcher = createStreamBatcher(
    (events) => flushed.push(events),
    sched.schedule,
  );
  batcher.push("node_update", { node: "tools" });
  batcher.push("tool_call", { name: "tool" });
  batcher.push("tool_result", { status: "ok" });
  assert.equal(flushed.length, 0);
  sched.run();
  assert.equal(flushed.length, 1);
  assert.deepEqual(
    flushed[0].map((e) => e.type),
    ["node_update", "tool_call", "tool_result"],
  );
  assert.deepEqual(flushed[0][1], { type: "tool_call", data: { name: "tool" } });
});

test("stream batcher flushes synchronously on terminal events", () => {
  const sched = manualScheduler();
  const flushed: string[][] = [];
  const batcher = createStreamBatcher(
    (events) => flushed.push(events.map((e) => e.type)),
    sched.schedule,
  );
  batcher.push("node_update", {});
  batcher.push("final_answer", { text: "done" });
  assert.deepEqual(flushed, [["node_update", "final_answer"]]);
  assert.equal(sched.pending.length, 1);
  sched.run();
  assert.equal(flushed.length, 1);
});

test("stream batcher manual flush drains and scheduled flush becomes a no-op", () => {
  const sched = manualScheduler();
  let calls = 0;
  const batcher = createStreamBatcher(
    () => calls++,
    sched.schedule,
  );
  batcher.push("node_update", {});
  batcher.flush();
  assert.equal(calls, 1);
  assert.equal(batcher.size(), 0);
  sched.run();
  assert.equal(calls, 1);
  batcher.flush();
  assert.equal(calls, 1);
});

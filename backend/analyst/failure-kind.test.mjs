import test from "node:test";
import assert from "node:assert/strict";
import { classifyFailureKind, isRateLimitEvidence } from "./dist/pi-execution.js";

test("429 and token-quota evidence classify as quota", () => {
  const session = { messages: [{ role: "assistant", errorMessage: "429 Tokens per minute limit exceeded" }] };
  assert.equal(classifyFailureKind("model", new Error("Model returned no answer"), session), "quota");
});

test("rate limit text in thrown error classifies as quota without session evidence", () => {
  assert.equal(classifyFailureKind("model", new Error("rate limit exceeded"), null), "quota");
});

test("generic model failures stay model kind", () => {
  const session = { messages: [{ role: "assistant", errorMessage: "connection reset" }] };
  assert.equal(classifyFailureKind("model", new Error("Model returned no answer"), session), "model");
});

test("non-model kinds are never reclassified", () => {
  assert.equal(classifyFailureKind("timeout", new Error("429 quota"), null), "timeout");
});

test("evidence regex matches observed cerebras copy", () => {
  assert.ok(isRateLimitEvidence("Tokens per minute limit exceeded - too many tokens processed."));
  assert.ok(isRateLimitEvidence("token_quota_exceeded"));
  assert.ok(!isRateLimitEvidence("Model returned no answer"));
});

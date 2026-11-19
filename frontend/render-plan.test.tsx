import test from "node:test";
import assert from "node:assert/strict";
import { callKey, groupKey } from "./lib/renderPlan";

test("phase identity keys stay stable per call object", () => {
  const a = { name: "get_x", args: {}, status: "ok" } as never;
  const b = { name: "get_x", args: {}, status: "ok" } as never;
  assert.equal(callKey(a as never), callKey(a as never));
  assert.notEqual(callKey(a as never), callKey(b as never));
  assert.equal(groupKey("get_x", undefined, a as never), groupKey("get_x", undefined, a as never));
  const withId = { id: "corr-1", name: "get_x", args: {} } as never;
  assert.equal(callKey(withId as never), "corr-1");
});
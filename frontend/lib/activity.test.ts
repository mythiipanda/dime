import assert from "node:assert/strict";
import test from "node:test";
import {
  ACTIVITY_CONTRACT_FIXTURE,
  activityRecordFromEvent,
  mergeActivityRecord,
} from "./activity";

const record = (raw: Record<string, unknown>) => {
  const value = activityRecordFromEvent(String(raw.type), raw, 0);
  assert.ok(value);
  return value;
};

test("orders sequenced events and ignores repeated event identity", () => {
  const first = record(ACTIVITY_CONTRACT_FIXTURE[0]);
  const second = record(ACTIVITY_CONTRACT_FIXTURE[1]);
  let items = mergeActivityRecord([], second);
  items = mergeActivityRecord(items, first);
  items = mergeActivityRecord(items, second);
  assert.deepEqual(items.map((item) => item.sequence), [1, 2]);
  assert.equal(items.length, 2);
});

test("keeps a live call and failed result correlated", () => {
  const call = record(ACTIVITY_CONTRACT_FIXTURE[0]);
  const failed = record({
    ...ACTIVITY_CONTRACT_FIXTURE[1],
    event_id: "run-a:2",
    status: "fail",
    transition: "failed",
    title: "Tool failed",
    correlation_id: call.correlationId,
  });
  const items = mergeActivityRecord(mergeActivityRecord([], call), failed);
  assert.equal(items[0].status, "running");
  assert.equal(items[1].status, "fail");
  assert.equal(items[0].correlationId, items[1].correlationId);
});

test("preserves the exact normalized wire data", () => {
  for (const raw of ACTIVITY_CONTRACT_FIXTURE) {
    const item = record(raw);
    assert.deepEqual(item.data, raw);
  }
});

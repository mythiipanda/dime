import assert from "node:assert/strict";
import test from "node:test";
import {
  ACTIVITY_CONTRACT_FIXTURE,
  activityRecordFromEvent,
  isNoiseRecord,
  mergeActivityRecord,
  pairToolItems,
  planSteps,
  recordKey,
  recordLabel,
} from "./activity";
import { describePair } from "../components/ActivityTimeline";

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

const items = () => ACTIVITY_CONTRACT_FIXTURE.map((raw) => record(raw));

test("pairs a call with its result by correlation id", () => {
  const pairs = pairToolItems(items());
  assert.equal(pairs.length, 1);
  assert.equal(pairs[0].call?.eventId, "run-a:1");
  assert.equal(pairs[0].result?.eventId, "run-a:2");
});

test("pairs by name when correlation ids are missing", () => {
  const call = record({
    type: "tool_call", event_id: "run-b:1", sequence: 1,
    emitted_at: "2026-09-18T20:00:00Z", phase: "execute", status: "running",
    title: "Tool running", transition: "started", data: { name: "team_ratings" },
  });
  const result = record({
    type: "tool_result", event_id: "run-b:2", sequence: 2,
    emitted_at: "2026-09-18T20:00:01Z", phase: "execute", status: "complete",
    title: "Tool complete", transition: "succeeded", data: { name: "team_ratings", rows: 5 },
  });
  const pairs = pairToolItems([call, result]);
  assert.equal(pairs.length, 1);
  assert.equal(pairs[0].result?.eventId, "run-b:2");
});

test("keeps a failed result paired and visible", () => {
  const call = record(ACTIVITY_CONTRACT_FIXTURE[0]);
  const failed = record({
    ...ACTIVITY_CONTRACT_FIXTURE[1],
    event_id: "run-a:9",
    status: "fail",
    transition: "failed",
    title: "Tool failed",
  });
  const pairs = pairToolItems([call, failed]);
  assert.equal(pairs.length, 1);
  assert.equal(pairs[0].call?.eventId, "run-a:1");
  assert.equal(pairs[0].result?.status, "fail");
});

test("keeps an orphan call and an orphan result as separate rows", () => {
  const call = record(ACTIVITY_CONTRACT_FIXTURE[0]);
  const orphan = record({
    ...ACTIVITY_CONTRACT_FIXTURE[1],
    event_id: "run-a:9",
    correlation_id: "call-9",
  });
  const pairs = pairToolItems([call, orphan]);
  assert.equal(pairs.length, 2);
  assert.equal(pairs[0].result, undefined);
  assert.equal(pairs[1].call, undefined);
});

test("pairs interleaved same-name calls in order", () => {
  const mk = (kind: string, id: string, seq: number) =>
    record({
      type: kind, event_id: id, sequence: seq,
      emitted_at: "2026-09-18T20:00:00Z", phase: "execute",
      status: kind === "tool_call" ? "running" : "complete",
      title: kind === "tool_call" ? "Tool running" : "Tool complete",
      transition: kind === "tool_call" ? "started" : "succeeded",
      node: "tools", name: "get_leaders",
      data: { name: "get_leaders" },
    });
  const pairs = pairToolItems([mk("tool_call", "run-d:1", 1), mk("tool_call", "run-d:2", 2), mk("tool_result", "run-d:3", 3)]);
  assert.equal(pairs.length, 2);
  assert.equal(pairs[0].call?.eventId, "run-d:1");
  assert.equal(pairs[0].result?.eventId, "run-d:3");
  assert.equal(pairs[1].call?.eventId, "run-d:2");
  assert.equal(pairs[1].result, undefined);
});

test("derives plan step states from tool lifecycle", () => {
  const steps = planSteps(items());
  assert.deepEqual(steps, [{ capability: "team_ratings", state: "done" }]);
});

test("marks a capability running while its call is open", () => {
  const only = items().filter((i) => i.kind === "tool_call" || i.kind === "plan_update");
  const steps = planSteps(only);
  assert.deepEqual(steps, [{ capability: "team_ratings", state: "running" }]);
});

test("marks unplanned capabilities pending and ignores unknown plans", () => {
  assert.deepEqual(planSteps([]), []);
  const plan = record({
    ...ACTIVITY_CONTRACT_FIXTURE[3],
    data: { node_count: 2, capabilities: ["team_ratings", "lineups"], unknown_capability_count: 0 },
  });
  const steps = planSteps([plan, ...items().filter((i) => i.kind === "tool_call")]);
  assert.deepEqual(steps, [
    { capability: "team_ratings", state: "running" },
    { capability: "lineups", state: "pending" },
  ]);
});

test("flags chatter and entry updates as noise", () => {
  const stream = record({
    type: "thought_stream", node: "tools", text: "Comparing players",
  });
  const token = record({
    type: "thought_token", node: "tools", text: "reasoning",
  });
  const entry = record({ type: "node_update", node: "entry", status: "running" });
  const tools = record({ type: "node_update", node: "tools", status: "running" });
  assert.equal(isNoiseRecord(stream), true);
  assert.equal(isNoiseRecord(token), true);
  assert.equal(isNoiseRecord(entry), true);
  assert.equal(isNoiseRecord(tools), false);
  assert.equal(isNoiseRecord(record(ACTIVITY_CONTRACT_FIXTURE[0])), false);
});

test("reads v1 top-level tool fields for keys and labels", () => {
  const call = record({
    type: "tool_call", node: "tools", name: "get_leaders",
    label: "Get Leaders", summary: "stat_category=AST",
  });
  const result = record({
    type: "tool_result", node: "tools", name: "get_leaders",
    status: "ok", rows: 30, ms: 938,
  });
  assert.equal(recordKey(call), "get_leaders");
  assert.equal(recordLabel(call), "Get Leaders");
  assert.equal(recordKey(result), "get_leaders");
  const pairs = pairToolItems([call, result]);
  assert.equal(pairs.length, 1);
  assert.equal(pairs[0].result?.eventId, result.eventId);
});

test("matches v1 plan capabilities against top-level tool names", () => {
  const plan = record({
    type: "plan_update", title: "Plan accepted",
    data: { node_count: 2, capabilities: ["get_leaders", "lineups"], unknown_capability_count: 0 },
  });
  const call = record({ type: "tool_call", node: "tools", name: "get_leaders", label: "Get Leaders" });
  const steps = planSteps([plan, call]);
  assert.deepEqual(steps, [
    { capability: "get_leaders", state: "running" },
    { capability: "lineups", state: "pending" },
  ]);
});

test("describePair renders the tool lifecycle without raw protocol", () => {
  const call = record({
    type: "tool_call", event_id: "run-c:1", sequence: 1,
    emitted_at: "2026-09-30T17:00:00Z", phase: "execute", status: "running",
    title: "Tool running", transition: "started", correlation_id: "call-9",
    node: "tools", name: "get_leaders", label: "Get Leaders",
    data: { name: "get_leaders", argument_count: 1, unknown_argument_count: 0 },
  });
  const live = describePair({ call }, true);
  assert.equal(live.label, "Searching Get Leaders");
  assert.equal(live.meta, "Running");
  const failed = record({
    type: "tool_result", event_id: "run-c:2", sequence: 2,
    emitted_at: "2026-09-30T17:00:02Z", phase: "execute", status: "fail",
    title: "Tool failed", transition: "failed", correlation_id: "call-9",
    node: "tools", name: "get_leaders", error: "warehouse timeout after 30s",
    data: { name: "get_leaders" },
  });
  const settled = describePair({ call, result: failed }, false);
  assert.equal(settled.label, "Get Leaders unavailable");
  assert.equal(settled.meta, "Failed");
  assert.ok(settled.fields.some(([k, v]) => k === "Error" && v === "warehouse timeout after 30s"));
  assert.ok(!JSON.stringify(settled).includes("argument_count"));
  const ok = record({
    type: "tool_result", event_id: "run-c:3", sequence: 3,
    emitted_at: "2026-09-30T17:00:01Z", phase: "execute", status: "complete",
    title: "Tool complete", transition: "succeeded", correlation_id: "call-9",
    node: "tools", name: "get_leaders", rows: 30, ms: 938,
    data: { name: "get_leaders", rows: 30 },
  });
  const done = describePair({ call, result: ok }, false);
  assert.equal(done.label, "Found Get Leaders");
  assert.equal(done.meta, "30 rows · 938ms");
});

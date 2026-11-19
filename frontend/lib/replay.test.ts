import { it } from "node:test";
import assert from "node:assert/strict";
import { replayName, replayStream } from "./replay";
import { applyEvent } from "./stream-event";
import type { AiMessage } from "./chat";
import { pairToolItems, planSteps } from "./activity";
import { evidenceSources, withCitationMarkers } from "./evidence";

it("only enables the named fixture explicitly in development", () => {
  assert.equal(replayName("?replay=scouting", "development"), "scouting");
  for (const env of ["production", "test"] as const) assert.equal(replayName("?replay=scouting", env), null);
  assert.equal(replayName("", "development"), null);
  assert.equal(replayName("?replay=unknown", "development"), null);
});

it("replays activity, citation evidence, a grid and a terminal answer through live handlers", async () => {
  let ai: AiMessage = { text: "", nodes: {}, done: false };
  let done = 0;
  await replayStream("scouting", { onEvent: (type, data) => { ai = applyEvent(ai, type, data); }, onDone: () => done++, onError: (error) => assert.fail(error) });
  assert.equal(done, 1);
  assert.equal(ai.done, true);
  assert.equal(pairToolItems(ai.activity || []).length, 1);
  assert.equal(planSteps(ai.activity || [])[0].state, "done");
  assert.ok(ai.nodes.analytics!.tables.some((t) => Array.isArray(t.rows)));
  assert.match(ai.text, /synthetic/);
  assert.match(withCitationMarkers(ai.text, evidenceSources(ai)), /#cite-/);
});

it("rejects unknown fixtures and stops an aborted replay without completing", async () => {
  let error = "";
  await replayStream("unknown", { onEvent: () => assert.fail(), onDone: () => assert.fail(), onError: (e) => { error = e; } });
  assert.equal(error, "Replay is unavailable.");
  const controller = new AbortController();
  controller.abort();
  await replayStream("scouting", { onEvent: () => assert.fail(), onDone: () => assert.fail(), onError: () => assert.fail() }, controller.signal);
});

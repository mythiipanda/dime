import test from "node:test";
import assert from "node:assert/strict";
import { replayName, replayStream } from "./replay";
import { DimeStream } from "./dime-stream";
import { loadChatRuns } from "./chat-persistence";

test("saved runs without snapshots restore follow-up suggestions through DimeStream", async () => {
  const previous = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ runs: [{ question: "Question", answer: "Saved answer", tables: [], suggestions: ["Next question", "", 42, "Another question"] }] });
  try {
    const runs = await loadChatRuns("restored-followups");
    assert.equal(runs[0].snapshot.text, "Saved answer");
    assert.deepEqual(runs[0].snapshot.suggestions, ["Next question", "Another question"]);
    globalThis.fetch = async () => Response.json({ runs: [{ question: "Question", answer: "No follow-ups", tables: [] }] });
    assert.deepEqual((await loadChatRuns("restored-no-followups"))[0].snapshot.suggestions, []);
  } finally { globalThis.fetch = previous; }
});

test("replay URL is development-only and ignores invalid names", () => {
  assert.equal(replayName("?replay=scouting", "development"), "scouting");
  for (const environment of ["production", "test"]) assert.equal(replayName("?replay=scouting", environment), null);
  for (const search of ["", "?replay=unknown"]) assert.equal(replayName(search, "development"), null);
});

test("development replay passes Pi sources, row/column anchors, and tables through dev's reducer", async () => {
  const previous = process.env.NODE_ENV;
  Object.assign(process.env, { NODE_ENV: "development" });
  try {
    const stream = new DimeStream();
    let done = false;
    await replayStream("scouting", { onEvent: (type, data) => stream.handle(type, data), onDone: () => { stream.finish(); done = true; }, onError: message => assert.fail(message) });
    const snapshot = stream.snapshot();
    assert.equal(done, true);
    assert.equal(snapshot.done, true);
    assert.match(snapshot.text, /32.7/);
    assert.equal(snapshot.carry?.sources?.[0].units.PPG, "points/game");
    assert.deepEqual(snapshot.carry?.submission?.blocks[0].anchors[0], { ref: "replay-player", row: 0, columns: ["PPG", "TS_PCT"] });
    assert.ok(snapshot.artifacts.some(artifact => artifact.kind === "table"));
    assert.ok(snapshot.tools.length);
  } finally { Object.assign(process.env, { NODE_ENV: previous }); }
});

test("replay rejects production and invalid names and honors cancellation", async () => {
  const previous = process.env.NODE_ENV;
  let error = "", events = 0, done = 0;
  const handlers = { onEvent: () => events++, onDone: () => { done++; }, onError: (message: string) => { error = message; } };
  try {
    Object.assign(process.env, { NODE_ENV: "production" });
    await replayStream("scouting", handlers);
    assert.equal(error, "Replay is unavailable.");
    Object.assign(process.env, { NODE_ENV: "development" });
    await replayStream("invalid", handlers);
    assert.equal(events, 0);
    const controller = new AbortController(); controller.abort();
    await replayStream("scouting", handlers, controller.signal);
    assert.equal(events, 0); assert.equal(done, 0);
  } finally { Object.assign(process.env, { NODE_ENV: previous }); }
});

test("generative replay sequences turn-aware fixture compositions", async () => {
  const previous = process.env.NODE_ENV;
  Object.assign(process.env, { NODE_ENV: "development" });
  try {
    const seen: string[] = [];
    for (const turn of [0, 1, 2, 3, 4, 5]) {
      let text = "";
      await replayStream("generative", {
        onEvent: (type, data) => { if (type === "final_answer") text = (data as { text: string }).text; },
        onDone: () => {}, onError: message => assert.fail(message),
      }, undefined, turn);
      seen.push(text);
    }
    assert.match(seen[0], /Generative answer fixture/);
    assert.match(seen[1], /Recovery fixture/);
    assert.match(seen[2], /Comparison fixture/);
    assert.match(seen[3], /Same-kind stacking fixture/);
    assert.match(seen[4], /Workbench handoff fixture/);
    assert.equal(seen[5], seen[0]);
  } finally { Object.assign(process.env, { NODE_ENV: previous }); }
});

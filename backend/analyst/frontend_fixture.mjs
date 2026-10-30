import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import api from "../../frontend/lib/api.ts";
import dimeStream from "../../frontend/lib/dime-stream.ts";
const { postChatStream } = api;
const { parseCarry } = dimeStream;

const root = process.argv[2];
assert(root, "Captured fixture directory required");
globalThis.localStorage = { getItem: () => "fixture", setItem() {} };
const chunks = JSON.parse(readFileSync(join(root, "normal-sse.json"), "utf8"));
for (const terminal of [true, false]) {
  const observed = [], errors = [];
  let done = 0;
  globalThis.fetch = async () => new Response(new ReadableStream({ start(controller) {
    for (const chunk of chunks) {
      if (!terminal && chunk.startsWith("event: graph_end")) continue;
      // Split frames to exercise the consumer's buffering too.
      const bytes = new TextEncoder().encode(chunk);
      controller.enqueue(bytes.slice(0, 9));
      controller.enqueue(bytes.slice(9));
    }
    controller.close();
  } }), { headers: { "content-type": "text/event-stream" } });
  await postChatStream("fixture", null, {
    onEvent: (name, data) => observed.push([name, data]),
    onDone: () => done++, onError: error => errors.push(error),
  });
  assert.equal(done, terminal ? 1 : 0);
  assert.equal(errors.length, terminal ? 0 : 1);
  const final = observed.find(([name]) => name === "final_answer")[1];
  const carry = parseCarry(final.carry);
  assert.equal(carry.verification, "unknown");
  assert.equal(carry.verifiedClaims, null);
}
console.log("Actual frontend consumer: terminal done, EOF error, unassessed carry passed");

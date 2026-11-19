import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import api from "../../frontend/lib/api.ts";
import dimeStream from "../../frontend/lib/dime-stream.ts";
const { postChatStream } = api;
const { parseCarry } = dimeStream;
import { createElement } from "../../frontend/node_modules/react/index.js";
import { renderToStaticMarkup } from "../../frontend/node_modules/react-dom/server.node.js";
import harness from "../../frontend/components/site/DimeHarness.tsx";
const { AnswerVerification } = harness;

const root = process.argv[2];
assert(root, "Captured fixture directory required");
globalThis.localStorage = { getItem: () => "fixture", setItem() {} };
globalThis.window = { localStorage: globalThis.localStorage };
const chunks = JSON.parse(readFileSync(join(root, "normal-sse.json"), "utf8"));
for (const terminal of [true, false]) {
  const observed = [], errors = [];
  let done = 0;
  globalThis.fetch = async url => String(url).includes("/sources?")
    ? Response.json(JSON.parse(readFileSync(join(root, "route-artifact.json"), "utf8")))
    : new Response(new ReadableStream({ start(controller) {
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
  }, undefined, "thread");
  assert.equal(done, terminal ? 1 : 0);
  assert.equal(errors.length, terminal ? 0 : 1);
  const final = observed.find(([name]) => name === "final_answer")[1];
  const carry = parseCarry(final.carry);
  assert.equal(carry.verification, "unknown");
  assert.equal(carry.verifiedClaims, null);
  assert.equal(carry.sourceRefs.length, 2);
  assert.equal(carry.sources.length, 2);
  assert.deepEqual(carry.sources[1].data.rows, [{PTS:71}]);
  const html = renderToStaticMarkup(createElement(AnswerVerification, { carry, artifacts: [] }));
  for (const text of ["Sources &amp; provenance", "PTS", "71", "total_points", "silver_leaders_pts"]) assert(html.includes(text), text);
  assert(!html.includes("verified claims"));
}
console.log("Actual frontend consumer: terminal done, EOF error, unassessed carry passed");

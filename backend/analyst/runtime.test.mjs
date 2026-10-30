import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";
import { createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import { createAnalystSession } from "./runtime.mjs";

const root = process.env.DIME_PI_TEST_ROOT;
assert(root, "DIME_PI_TEST_ROOT must identify an isolated proof directory");

async function fixture(name, code, tools) {
  const cwd = join(root, name);
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });
  await writeFile(join(cwd, "AGENTS.md"), "PROFILE_CONTEXT_MUST_NOT_LOAD");
  for (const base of [join(cwd, ".pi"), agentDir]) {
    await mkdir(join(base, "extensions"), { recursive: true });
    await writeFile(join(base, "extensions", "poison.mjs"), 'throw new Error("PROFILE_EXTENSION_MUST_NOT_LOAD")');
  }
  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"), modelsPath: null,
    allowModelNetwork: false, refreshOnCreate: false,
  });
  const requests = [];
  runtime.registerProvider("fixture", {
    api: "openai-completions", apiKey: "fixture-only", baseUrl: "http://invalid.test",
    models: [{ id: "fixture", name: "Fixture", input: ["text"], reasoning: false,
      contextWindow: 100000, maxTokens: 4000,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } }],
    streamSimple(model, context) {
      requests.push(structuredClone(context));
      const first = requests.length === 1;
      const message = {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: first ? [{ type: "toolCall", id: name, name: "codemode", arguments: { code } }]
          : [{ type: "text", text: "Fixture completed" }],
        stopReason: first ? "toolUse" : "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: message.stopReason, message });
      stream.end();
      return stream;
    },
  });
  const session = await createAnalystSession({ cwd, agentDir, model: runtime.getModel("fixture", "fixture"), modelRuntime: runtime, tools,
    settings: { retry: { enabled: false }, compaction: { enabled: false } } });
  assert.deepEqual(session.getActiveToolNames(), ["codemode"]);
  assert.deepEqual(new Set(session.getCallableToolNames()), new Set(tools.map(t => t.name)));
  assert(!session.systemPrompt.includes("PROFILE_CONTEXT_MUST_NOT_LOAD"));
  return { session, requests };
}

function tool(name, execute) {
  return { name, label: name, description: name,
    parameters: { type: "object", properties: {}, additionalProperties: false }, execute };
}
const textResult = value => ({ content: [{ type: "text", text: JSON.stringify(value) }] });

test("real SDK codemode calls two tools concurrently, filters model input and retains raw references", async () => {
  const raw = new Map();
  let running = 0;
  let peak = 0;
  let release;
  const bothStarted = new Promise(resolve => { release = resolve; });
  const tools = ["season_stats", "career_stats"].map((name, index) => tool(name, async () => {
    running++;
    peak = Math.max(peak, running);
    if (running === 2) release();
    await bothStarted;
    const result = { ref: "result-" + index, source: name, unit: index ? "cumulative" : "per_game", season: "202526",
      rows: [{ label: "keep", value: index + 3 }, { label: "RAW_SECRET_ROW", value: 999 }] };
    raw.set(result.ref, result);
    running--;
    return textResult(result);
  }));
  const { session, requests } = await fixture("parallel", `
    const results = await Promise.all([tools.season_stats({}), tools.career_stats({})]);
    return results.map(value => {
      const result = JSON.parse(value);
      return {ref: result.ref, unit: result.unit, season: result.season, rows: result.rows.filter(row => row.label === "keep")};
    });
  `, tools);
  try {
    await session.prompt("Run the fixture");
    assert.equal(peak, 2);
    assert.equal(raw.size, 2);
    assert.equal(requests.length, 2);
    assert.deepEqual(requests[0].messages.flatMap(m => m.toolsAdded ?? []).map(t => t.name), ["codemode"]);
    const seen = JSON.stringify(requests[1]);
    assert(!seen.includes("RAW_SECRET_ROW"));
    for (const ref of raw.keys()) assert(seen.includes(ref));
    assert(seen.includes("per_game") && seen.includes("cumulative") && seen.includes("202526"));
    assert.equal(raw.get("result-0").rows[1].value, 999);
    console.log(JSON.stringify({ proof: "parallel-filter-retain", peak, refs: [...raw.keys()] }));
  } finally { session.dispose(); }
});

test("actual tool exception survives codemode and another tool remains usable", async () => {
  const failure = new Error("fixture warehouse unavailable E547");
  let observed;
  const { session, requests } = await fixture("error", `
    const results = await Promise.allSettled([tools.unavailable({}), tools.available({})]);
    return results.map(r => r.status === "rejected" ? {error: r.reason.message} : {value: r.value});
  `, [tool("unavailable", async () => { observed = failure; throw failure; }),
    tool("available", async () => textResult({ ref: "successful-result" }))]);
  try {
    await session.prompt("Run error fixture");
    assert.equal(observed, failure);
    const seen = JSON.stringify(requests[1]);
    assert(seen.includes(failure.message));
    assert(seen.includes("successful-result"));
  } finally { session.dispose(); }
});


test("session abort cancels a running nested analysis tool", async () => {
  let started;
  const entered = new Promise(resolve => { started = resolve; });
  let cancelled = false;
  const { session } = await fixture("cancel", "return await tools.wait_for_cancel({});", [
    tool("wait_for_cancel", async (_id, _args, signal) => {
      started();
      await new Promise((resolve, reject) => {
        const abort = () => { cancelled = true; reject(new Error("fixture tool cancelled")); };
        if (signal.aborted) abort();
        else signal.addEventListener("abort", abort, { once: true });
      });
    }),
  ]);
  try {
    const pending = session.prompt("Run cancellation fixture");
    await entered;
    await session.abort();
    await pending;
    assert(cancelled);
    assert(session.isIdle);
  } finally { session.dispose(); }
});

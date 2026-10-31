import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";
import { createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import { createAnalystSession } from "./dist/runtime.js";
import { priorSourceTool } from "./dist/pi-context.js";
import { connectPythonTools } from "./dist/python-tools.js";

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

test("real Python sql_exec and schema cross MCP into Pi with source semantics and independent results", async () => {
  const baseline = JSON.parse(await readFile(join(root, "python-baseline.json"), "utf8"));
  const bridge = await connectPythonTools({ python: process.env.DIME_PI_PYTHON, cwd: root,
    env: { ...process.env } });
  const pid = bridge.pid;
  let session;
  let running = 0;
  let peak = 0;
  const tools = bridge.tools.map(tool => ({ ...tool, async execute(...args) {
    running++;
    peak = Math.max(peak, running);
    try { return await tool.execute(...args); }
    finally { running--; }
  } }));
  const value = record => JSON.parse(record.response.content[0].text);
  const stable = result => {
    const copy = structuredClone(result);
    if (copy.meta) delete copy.meta.ms;
    return copy;
  };
  try {
    assert.deepEqual(bridge.tools.map(t => t.name), ["sql_exec", "warehouse_schema"]);
    assert.deepEqual(bridge.tools[0].parameters.required, ["sql"]);
    const setup = await fixture("python", `
      const args = ${JSON.stringify(baseline.args)};
      const calls = await Promise.all(args.map(arg => tools.sql_exec(arg)));
      calls.push(await tools.sql_exec(args[1]));
      const invalid = await tools.sql_exec(args[3]);
      if (!invalid.isError || invalid.result.ok !== false) throw new Error("Missing domain failure");
      const recovered = await tools.sql_exec(args[1]);
      if (recovered.isError || !recovered.result.rows.length) throw new Error("Same-script recovery failed");
      const schema = await tools.warehouse_schema({});
      if (typeof schema !== "object" || !schema.result.tables) throw new Error("Expected native schema.result.tables");
      return {schema: {ref: schema.ref, tables: Object.fromEntries(Object.entries(schema.result.tables)
        .filter(([name]) => name === "silver_hist_player_seasons"))}, invalid, recovered: {ref: recovered.ref, units: recovered.result.declared_column_semantics}, calls: calls.map(record => {
        const result = record.result;
        if (Array.isArray(result.rows)) result.rows = result.rows.filter(row => row.total_points !== 999);
        return {ref: record.ref, result};
      })};
    `, tools);
    session = setup.session;
    await session.prompt("Run real Python fixture");
    assert(peak >= 2, "real Python requests must overlap");
    assert.equal(running, 0);
    const records = [...bridge.results.values()];
    const queries = records.filter(r => r.tool === "sql_exec" && !r.response.isError);
    assert.equal(queries.length, baseline.args.length + 3);
    assert.equal(new Set(records.map(r => r.ref)).size, records.length);
    assert.equal(new Set(queries.map(r => r.callId)).size, queries.length);
    for (const record of queries) {
      const result = value(record);
      const index = baseline.args.findIndex(a => a.sql === (result.sql ?? result.meta.sql));
      assert(index >= 0);
      assert.deepEqual(stable(result), stable(baseline.direct[index]));
    }
    assert.deepEqual(value(records.find(r => r.tool === "warehouse_schema")), baseline.schema);
    assert(JSON.stringify(baseline.schema).length > 100000);
    assert(baseline.schema.tables.silver_leaders_pts.RAW_SECRET_ROW);
    const perGame = value(queries.find(r => value(r).sql === baseline.args[0].sql));
    assert.equal(perGame.declared_column_semantics.total_points.unit, "points_per_game");
    assert.equal(perGame.rows[0].total_points, 11.8);
    assert.equal(perGame.rows[1].total_points, 999);
    assert(perGame.season_semantics.resolved_labels.some(r => r.season_label === "2090-91"));
    assert.equal(baseline.direct[1].declared_column_semantics.PTS.unit, "total_points");
    for (const failed of baseline.direct.slice(2)) assert.equal(failed.ok, false);
    const seen = JSON.stringify(setup.requests[1]);
    assert(seen.includes("tables"));
    assert(!seen.includes("RAW_SECRET_ROW"));
    for (const record of queries) assert(seen.includes(record.ref));

    // Domain failure and input-validation errors do not close the process or erase evidence.
    const sql = bridge.tools.find(t => t.name === "sql_exec");
    const invalid = (await sql.execute("invalid", {}, undefined)).structuredContent;
    assert.equal(invalid.isError, true);
    assert(invalid.result.includes("ValidationError"));
    const recovery = (await sql.execute("recovery", baseline.args[1], undefined)).structuredContent;
    assert.deepEqual(stable(recovery.result), stable(baseline.direct[1]));
    assert.equal(bridge.results.size, baseline.args.length + 6);
    await writeFile(join(root, "python-host-records.json"), JSON.stringify([...bridge.results.values()]));
    await writeFile(join(root, "python-provider-requests.json"), JSON.stringify(setup.requests));
    console.log(JSON.stringify({ proof: "python-mcp-pi-equivalence", queries: queries.length,
      refs: queries.map(r => r.ref), peak, units: ["points_per_game", "total_points"], pid }));
  } finally {
    session?.dispose();
    await bridge.close();
  }
  assert.throws(() => process.kill(pid, 0), /ESRCH/);
});

// Observe the installed Pi/QuickJS contract before adapting the Python bridge.
test("installed SDK distinguishes opaque text from native structured results", async () => {
  const record = {ref: "shape-ref", callId: "shape-call", tool: "schema", response: {
    content: [{type: "text", text: JSON.stringify({tables: {observed: ["PTS"]}})}]}};
  const native = {...tool("native", async () => ({content: [], structuredContent: {tables: {observed: ["PTS"]}}})),
    outputSchema: {type: "object"}};
  const {session, requests} = await fixture("sdk-shape", `
    const opaque = await tools.opaque({});
    const native = await tools.native({});
    return {opaqueType: typeof opaque, outerKeys: Object.keys(JSON.parse(opaque)),
      nestedType: typeof JSON.parse(opaque).response.content[0].text,
      nativeType: typeof native, tables: native.tables};
  `, [tool("opaque", async () => textResult(record)), native]);
  try {
    await session.prompt("Observe installed SDK shape");
    const seen = JSON.stringify(requests[1]);
    for (const text of ["opaqueType", "string", "nestedType", "nativeType", "object", "observed"]) assert(seen.includes(text));
    console.log(JSON.stringify({proof: "installed-sdk-shape", messages: requests[1].messages.filter(m => m.role === "toolResult")}));
  } finally {session.dispose();}
});

test("prior sources expose native data, filter a large schema and recover after MCP text errors", async () => {
  const tables = Object.fromEntries(Array.from({length: 1500}, (_, i) => ["table_" + i,
    [{name: "PTS", type: "DOUBLE", unit: "points_per_game", source: "RAW_SECRET_ROW"}]]));
  const records = [
    {ref: "large-schema", callId: "s", tool: "warehouse_schema", response: {content: [{type: "text", text: JSON.stringify({tables})}]}},
    {ref: "prior-sql", callId: "q", tool: "sql_exec", response: {content: [{type: "text", text: JSON.stringify({ok: true,
      rows: [{PTS: 11.8}, {PTS: 999, secret: "RAW_SECRET_ROW"}], declared_column_semantics: {PTS: {unit: "points_per_game"}},
      season_semantics: {encoding: "end_year"}, meta: {source: "owned-synthetic"}})}]}},
    ...["WarehouseError: exact E580", '{"error":broken'].map((text, i) => ({ref: "error-" + i,
      callId: "e" + i, tool: "sql_exec", response: {isError: true, content: [{type: "text", text}]}})),
    {ref: "domain-failure", callId: "d", tool: "sql_exec", response: {content: [{type: "text", text: '{"ok":false,"error":"SQL exact E581"}'}]}},
  ];
  const before = JSON.stringify(records);
  assert(before.length > 100000);
  const {session, requests} = await fixture("prior-native", `
    const errors = await Promise.all(["error-0", "error-1", "domain-failure"].map(ref => tools.read_source({ref})));
    if (errors.some(value => !value.isError)) throw new Error("Error status lost");
    const schema = await tools.read_source({ref: "large-schema"});
    const sql = await tools.read_source({ref: "prior-sql"});
    return {errors, schema: {ref: schema.ref, tables: Object.entries(schema.result.tables)
      .filter(([name]) => name === "table_17").map(([name, columns]) => ({name, columns: columns.map(c => ({name: c.name, type: c.type, unit: c.unit}))}))},
      sql: {ref: sql.ref, rows: sql.result.rows.filter(r => r.PTS !== 999), units: sql.result.declared_column_semantics,
      season: sql.result.season_semantics, provenance: sql.result.meta}};
  `, [priorSourceTool(records)]);
  try {
    await session.prompt("Read filtered prior data and errors");
    const seen = JSON.stringify(requests[1]);
    for (const text of ["large-schema", "prior-sql", "table_17", "DOUBLE", "points_per_game", "end_year", "owned-synthetic", "WarehouseError: exact E580", "broken", "SQL exact E581"]) assert(seen.includes(text), text);
    assert(!seen.includes("RAW_SECRET_ROW"));
    assert(!seen.includes("table_1499"));
    const calls = session.messages.find(m => m.role === "toolResult").details.calls;
    assert.deepEqual(calls.slice(0,3).map(c => c.status), ["error", "error", "error"]);
    assert(calls[0].error.includes("WarehouseError: exact E580"));
    assert(calls[1].error.includes('{"error":broken'));
    assert(calls[2].error.includes("SQL exact E581"));
    assert.equal(calls.at(-1).status, "ok");
    assert.equal(JSON.stringify(records), before);
    await writeFile(join(root, "prior-host-records.json"), before);
    await writeFile(join(root, "prior-provider-requests.json"), JSON.stringify(requests));
    console.log(JSON.stringify({proof: "prior-native-large-filter-errors", rawBytes: before.length, tables: Object.keys(tables).length}));
  } finally {session.dispose();}
});

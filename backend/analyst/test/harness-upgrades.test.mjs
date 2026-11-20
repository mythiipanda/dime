import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Type } from "typebox";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";
import { createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import { reportBootstrapFailure } from "../dist/host.js";
import {
  canonicalArgsKey,
  createPiExecution,
  listWorkspaceArtifacts,
} from "../dist/pi-execution.js";
import {
  createSubmitAnswerTool,
  validateAnswerSubmission,
} from "../dist/submit-tool.js";
import { ANALYST_TOOL_NAMES } from "../dist/python-tools.js";
import { TOOL_PROMPT_GUIDELINES } from "../dist/tool-contract-metadata.js";
import { sourceResult } from "../dist/python-tools.js";
import { countToolCall, createRunStatusTool } from "../dist/run-status.js";

function makeSourceRecord(ref, { rows = [], isError = false, error } = {}) {
  const result = error !== undefined ? { rows, error } : { rows };
  return makePayloadSourceRecord(ref, result, { isError });
}

function makePayloadSourceRecord(ref, payload, { tool = "sql_exec", args, isError = false } = {}) {
  return {
    ref,
    callId: "call-" + ref,
    tool,
    ...(args ? { args } : {}),
    response: {
      content: [{ type: "text", text: JSON.stringify(payload) }],
      structuredContent: payload,
      isError,
    },
  };
}

function messageText(value) {
  if (typeof value === "string")
    return value;
  if (Array.isArray(value))
    return value.map(messageText).join("\n");
  if (value && typeof value === "object")
    return Object.values(value).map(messageText).join("\n");
  return "";
}

function makeFixtureRuntime(agentDir, streamHandler, compat) {
  return ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  }).then((runtime) => {
    runtime.registerProvider("fixture", {
      api: "openai-completions",
      apiKey: "synthetic",
      baseUrl: "http://invalid.test",
      models: [
        {
          id: "fixture",
          name: "Fixture",
          input: ["text"],
          reasoning: false,
          contextWindow: 100000,
          maxTokens: 4000,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
          compat,
        },
      ],
      streamSimple: streamHandler,
    });
    return runtime;
  });
}

test("tool contract metadata covers high-risk analyst tools", () => {
  const covered = [
    "sql_exec",
    "warehouse_schema",
    "run_python",
    "get_cap_ledger",
    "get_contract_value",
    "get_trade_check",
    "get_trade_value",
    "get_lineup_stats",
    "get_lineup_leaders",
    "get_lineups",
    "get_wowy",
    "get_lineup_matchup_matrix",
    "get_shot_zones",
    "get_shot_compare",
    "get_zone_deltas",
    "search_shots",
    "get_team_shot_zones",
    "get_tracking_profile",
    "get_playtype_profile",
    "get_rapm",
    "get_rapm_prior",
    "get_on_off",
    "get_comps",
    "get_game_prediction",
    "get_win_prob",
    "get_playoff_sim",
    "get_regression_check",
    "get_scout_pack",
    "get_rotation_check",
    "get_injury_impact",
  ];
  for (const name of covered) {
    const guidelines = TOOL_PROMPT_GUIDELINES[name];
    assert.ok(Array.isArray(guidelines) && guidelines.length === 1, name);
    assert.match(guidelines[0], /Use /, name);
    assert.match(guidelines[0], /Do not /, name);
    assert.ok(guidelines[0].length <= 500, name);
  }
  for (const [name, guidelines] of Object.entries(TOOL_PROMPT_GUIDELINES)) {
    assert.ok(ANALYST_TOOL_NAMES.includes(name), name);
    assert.ok(guidelines.every((guideline) => guideline.trim().length > 0), name);
  }
});

test("listWorkspaceArtifacts respects depth, extensions, ignores, sorting, and cap", async () => {
  const dir = await mkdtemp(join(tmpdir(), "dime-ws-artifacts-"));
  try {
    await writeFile(join(dir, "top.csv"), "a,b\n1,2\n");
    await writeFile(join(dir, "ignore.py"), "print(1)\n");
    await writeFile(join(dir, ".hidden.json"), "{}");
    await mkdir(join(dir, "node_modules", "pkg"), { recursive: true });
    await writeFile(join(dir, "node_modules", "pkg", "mod.json"), "{}");
    await mkdir(join(dir, "__pycache__"), { recursive: true });
    await writeFile(join(dir, "__pycache__", "cache.txt"), "x");
    await mkdir(join(dir, ".git"), { recursive: true });
    await writeFile(join(dir, ".git", "info.md"), "#");
    await mkdir(join(dir, "sub1", "sub2", "sub3"), { recursive: true });
    await writeFile(join(dir, "sub1", "chart.png"), "png");
    await writeFile(join(dir, "sub1", "sub2", "data.parquet"), "pq");
    await writeFile(join(dir, "sub1", "sub2", "sub3", "too_deep.txt"), "deep");

    const found = listWorkspaceArtifacts(dir);
    assert.deepEqual(
      found.map((f) => f.path),
      ["sub1/chart.png", "sub1/sub2/data.parquet", "top.csv"]
    );
    assert.equal(found[2].bytes, 8);

    const missing = listWorkspaceArtifacts(join(dir, "does-not-exist"));
    assert.deepEqual(missing, []);

    const capDir = join(dir, "capped");
    await mkdir(capDir, { recursive: true });
    for (let i = 0; i < 45; i++) {
      await writeFile(
        join(capDir, `file-${String(i).padStart(2, "0")}.tsv`),
        "x\n"
      );
    }
    const capped = listWorkspaceArtifacts(capDir);
    assert.equal(capped.length, 40);
    assert.equal(capped[0].path, "file-00.tsv");
    assert.equal(capped[39].path, "file-39.tsv");
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("sourceResult returns a compact evidence card for SQL-like source records", () => {
  const sql = "SELECT PLAYER, PTS FROM silver_leaders_pts WHERE _season = '2025-26'";
  const payload = {
    tool: "sql_exec",
    ok: true,
    rows: [
      { PLAYER: "Alpha", PTS: 31.2, SECRET: "RAW_SECRET_ROW" },
      { PLAYER: "Beta", PTS: 28.4, SECRET: "RAW_SECRET_ROW" },
    ],
    columns: ["PLAYER", "PTS", "SECRET"],
    row_count: 2,
    sql,
    meta: {
      source: "warehouse",
      season: "2025-26",
      tables: ["silver_leaders_pts"],
      empty_observation: false,
      profile: { returned_rows: 2 },
    },
    declared_column_semantics: { PTS: { unit: "total_points" } },
    season_semantics: {
      tables: ["silver_leaders_pts"],
      season_columns: [{ table: "silver_leaders_pts", column: "_season", encoding: "label", row_grain: "season" }],
      resolved_labels: [{ season: "2025-26", season_label: "2025-26" }],
      ambiguities: [{ table: "silver_leaders_pts", column: "_season" }],
    },
  };
  const record = makePayloadSourceRecord("sql-card", payload, { args: { sql } });
  const output = sourceResult(record);
  assert.equal(output.isError, false);
  const evidence = output.structuredContent.evidence;
  assert.equal(evidence.ref, "sql-card");
  assert.equal(evidence.tool, "sql_exec");
  assert.equal(evidence.ok, true);
  assert.equal(evidence.is_error, false);
  assert.equal(evidence.row_count, 2);
  assert.deepEqual(evidence.columns, ["PLAYER", "PTS", "SECRET"]);
  assert.equal(evidence.query.sql, sql);
  assert.deepEqual(evidence.query.tables, ["silver_leaders_pts"]);
  assert.equal(evidence.season.season, "2025-26");
  assert.equal(evidence.season.semantics.season_columns[0].encoding, "label");
  assert.equal(evidence.units.PTS, "total_points");
  assert.equal(evidence.provenance.source, "warehouse");
  assert.ok(evidence.caveats.some((item) => item.includes("ambiguities")));
  assert.equal(evidence.rows, undefined);
  assert.equal(JSON.stringify(evidence).includes("RAW_SECRET_ROW"), false);
  assert.equal(output.structuredContent.result.rows[0].SECRET, "RAW_SECRET_ROW");
});

test("sourceResult returns a compact evidence card for domain-tool source records", () => {
  const payload = {
    tool: "get_rapm",
    ok: true,
    rows: [{ player: "Beta", rapm: 4.1 }],
    columns: ["player", "rapm"],
    season: "2024-25",
    season_label: "2024-25",
    meta: { source: "warehouse:silver_rapm", season: 2025, season_label: "2024-25", limit: 1, estimated: false },
  };
  const record = makePayloadSourceRecord("domain-card", payload, {
    tool: "get_rapm",
    args: { player: "Beta", season: "2024-25" },
  });
  const evidence = sourceResult(record).structuredContent.evidence;
  assert.equal(evidence.row_count, 1);
  assert.deepEqual(evidence.columns, ["player", "rapm"]);
  assert.deepEqual(evidence.query.filters, { player: "Beta", season: "2024-25" });
  assert.equal(evidence.season.season_label, "2024-25");
  assert.equal(evidence.provenance.source, "warehouse:silver_rapm");
  assert.equal(evidence.rows, undefined);
  assert.equal(JSON.stringify(evidence).includes("rapm\":4.1"), false);
});

test("createPiExecution injects prior source evidence cards without full rows", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-prior-cards-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const seenContexts = [];
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    seenContexts.push(structuredClone(context));
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content: [{ type: "text", text: "Done." }],
      stopReason: "stop",
      timestamp: Date.now(),
      usage: {
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        totalTokens: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
      },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: "stop", message: msg });
    stream.end();
    return stream;
  });

  const source = makePayloadSourceRecord("prior-card", {
    tool: "get_rapm",
    ok: true,
    rows: [{ player: "Gamma", rapm: 3.8, SECRET: "RAW_SECRET_ROW" }],
    columns: ["player", "rapm", "SECRET"],
    meta: { source: "warehouse:silver_rapm", season: 2025, season_label: "2024-25" },
  }, {
    tool: "get_rapm",
    args: { player: "Gamma", season: "2024-25" },
  });
  const pi = createPiExecution({
    resolveRuntime: async () => ({
      runtime,
      model: runtime.getModel("fixture", "fixture"),
    }),
    connectTools: async () => ({
      tools: [],
      results: new Map(),
      pid: 1003,
      close: async () => {},
    }),
  });

  try {
    for await (const _event of pi.stream({
      q: "Follow up",
      history: [],
      model: "fixture:fixture",
      sources: [source],
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
    }
    const userTexts = seenContexts[0].messages
      .filter((m) => m.role === "user")
      .map((m) => (typeof m.content === "string" ? m.content : JSON.stringify(m.content)));
    const injected = userTexts.find((t) => t.startsWith("Prior source evidence cards."));
    assert.ok(injected, "Prior source evidence card message should be injected");
    const cards = JSON.parse(injected.slice("Prior source evidence cards. Use tools.read_source({ref}) inside codemode and return only filtered results; cards omit full rows:\n".length));
    assert.equal(cards.length, 1);
    assert.equal(cards[0].ref, "prior-card");
    assert.equal(cards[0].row_count, 1);
    assert.deepEqual(cards[0].query.filters, { player: "Gamma", season: "2024-25" });
    assert.equal(cards[0].season.season_label, "2024-25");
    assert.equal(cards[0].rows, undefined);
    assert.equal(injected.includes("RAW_SECRET_ROW"), false);
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("createPiExecution injects thread workspace files into initial model messages", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-ws-inject-"));
  const agentDir = join(cwd, "agent");
  const bridgeCwd = join(cwd, "bridge-ws");
  await mkdir(agentDir, { recursive: true });
  await mkdir(bridgeCwd, { recursive: true });
  await writeFile(join(bridgeCwd, "summary.md"), "# Summary\n");
  await writeFile(join(bridgeCwd, "metrics.json"), '{"pts":30}');

  const seenContexts = [];
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    seenContexts.push(structuredClone(context));
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content: [{ type: "text", text: "Done." }],
      stopReason: "stop",
      timestamp: Date.now(),
      usage: {
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        totalTokens: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
      },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: "stop", message: msg });
    stream.end();
    return stream;
  });

  const pi = createPiExecution({
    resolveRuntime: async () => ({
      runtime,
      model: runtime.getModel("fixture", "fixture"),
    }),
    connectTools: async () => ({
      tools: [],
      results: new Map(),
      pid: 1001,
      close: async () => {},
    }),
  });

  try {
    const events = [];
    for await (const event of pi.stream({
      q: "Inspect workspace",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd: bridgeCwd, env: {} },
    })) {
      events.push(event);
    }
    assert.equal(events.find((e) => e.type === "answer")?.text, "Done.");
    const userTexts = seenContexts[0].messages
      .filter((m) => m.role === "user")
      .map((m) => (typeof m.content === "string" ? m.content : JSON.stringify(m.content)));
    const injected = userTexts.find((t) =>
      t.startsWith("Thread workspace files available in run_python cwd:\n")
    );
    assert.ok(injected, "Workspace file index message should be injected");
    const parsed = JSON.parse(
      injected.slice("Thread workspace files available in run_python cwd:\n".length)
    );
    assert.deepEqual(
      parsed.map((item) => item.path),
      ["metrics.json", "summary.md"]
    );
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("canonicalArgsKey normalizes nested key order and wrapBridgeTools short-circuits 3rd identical call", async () => {
  assert.equal(
    canonicalArgsKey({ b: 2, a: { z: true, y: [1, { d: 4, c: 3 }] } }),
    canonicalArgsKey({ a: { y: [1, { c: 3, d: 4 }], z: true }, b: 2 })
  );

  const cwd = await mkdtemp(join(tmpdir(), "dime-loop-detect-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let execCount = 0;
  let turn = 0;
  const seenToolResults = [];
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    turn++;
    if (turn === 1) {
      const code = `
        const r1 = await tools.sql_exec({ sql: "SELECT 1", params: { a: 1, b: 2 } });
        const r2 = await tools.sql_exec({ params: { b: 2, a: 1 }, sql: "SELECT 1" });
        const r3 = await tools.sql_exec({ sql: "SELECT 1", params: { a: 1, b: 2 } });
        return { r1, r2, r3 };
      `;
      const msg = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        content: [
          { type: "toolCall", id: "call-loop", name: "codemode", arguments: { code } },
        ],
        stopReason: "toolUse",
        timestamp: Date.now(),
        usage: {
          input: 0,
          output: 0,
          cacheRead: 0,
          cacheWrite: 0,
          totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: "toolUse", message: msg });
      stream.end();
      return stream;
    }
    seenToolResults.push(
      ...context.messages.filter((m) => m.role === "toolResult")
    );
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content: [{ type: "text", text: "Recovered after loop warning." }],
      stopReason: "stop",
      timestamp: Date.now(),
      usage: {
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        totalTokens: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
      },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  const mockBridge = {
    tools: [
      {
        name: "sql_exec",
        label: "sql_exec",
        description: "Run SQL",
        parameters: Type.Object({
          sql: Type.String(),
          params: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
        }),
        async execute(callId) {
          execCount++;
          const ref = `src-exec-${execCount}`;
          const payload = { rows: [{ val: 1 }] };
          const record = {
            ref,
            callId,
            tool: "sql_exec",
            response: {
              content: [{ type: "text", text: JSON.stringify(payload) }],
              structuredContent: payload,
              isError: false,
            },
          };
          resultsMap.set(ref, record);
          return {
            content: [],
            details: undefined,
            structuredContent: {
              ref,
              tool: "sql_exec",
              result: payload,
              isError: false,
            },
            isError: false,
          };
        },
      },
    ],
    results: resultsMap,
    pid: 1002,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({
      runtime,
      model: runtime.getModel("fixture", "fixture"),
    }),
    connectTools: async () => mockBridge,
  });

  try {
    const events = [];
    for await (const event of pi.stream({
      q: "Test loop detection",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    assert.equal(execCount, 2);
    const toolResults = events.filter((e) => e.type === "tool_result");
    assert.equal(toolResults.length, 3);
    assert.equal(toolResults[0].status, "ok");
    assert.equal(toolResults[1].status, "ok");
    assert.equal(toolResults[2].status, "fail");
    assert.equal(
      toolResults[2].error,
      "Identical tool call repeated 3 times in this run"
    );

    const loopSource = events.find(
      (e) => e.type === "source" && e.record.ref === "loop_3_sql_exec"
    );
    assert.ok(loopSource, "Synthetic loop source record should be emitted");
    assert.ok(resultsMap.has("loop_3_sql_exec"));
    const loopPayload = loopSource.record.response.structuredContent;
    assert.equal(loopPayload.ok, false);
    assert.equal(loopPayload.loop_detected, true);
    assert.match(loopPayload.recovery_hint, /Reuse prior ref src-exec-2 via tools\.read_source/);
    assert.deepEqual(loopPayload.next_actions, [
      "Inspect prior source ref",
      "Modify query/parameters",
      "Call submit_answer",
    ]);
    assert.equal(
      events.find((e) => e.type === "answer")?.text,
      "Recovered after loop warning."
    );
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("run_status reports elapsed budget and counters", async () => {
  const tracker = {
    startedAt: Date.now() - 1000,
    budgetMs: 5000,
    toolCalls: 7,
    sourceCount: () => 3,
    submitted: true,
  };
  const tool = createRunStatusTool(tracker);
  const result = await tool.execute("call-status", {}, undefined, undefined, undefined);
  const status = result.structuredContent;
  assert.equal(status.ok, true);
  assert.equal(status.tool_calls, 7);
  assert.equal(status.source_count, 3);
  assert.equal(status.submitted, true);
  assert.equal(status.budget_ms, 5000);
  assert.ok(status.elapsed_ms >= 1000);
  assert.equal(status.elapsed_ms + status.budget_remaining_ms, status.budget_ms);

  const unbudgeted = createRunStatusTool({ startedAt: Date.now(), toolCalls: 0, sourceCount: () => 0, submitted: false });
  const unbudgetedResult = await unbudgeted.execute("call-status-2", {}, undefined, undefined, undefined);
  assert.equal(unbudgetedResult.structuredContent.budget_ms, undefined);
  assert.equal(unbudgetedResult.structuredContent.budget_remaining_ms, undefined);

  const counted = countToolCall(createRunStatusTool(tracker), tracker);
  await counted.execute("call-status-3", {}, undefined, undefined, undefined);
  assert.equal(tracker.toolCalls, 8);
});

test("run_status is exposed to codemode with host budget and checkpointed submission", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-run-status-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let turn = 0;
  const seenContexts = [];
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    turn++;
    seenContexts.push(structuredClone(context));
    const content = turn === 1
      ? [{ type: "toolCall", id: "call-run-status", name: "codemode", arguments: { code: `
          await tools.submit_answer({ blocks: [{ text: "Checkpoint partial." }] });
          const source = await tools.sql_exec({ sql: "SELECT 1" });
          const prior = await tools.read_source({ ref: "prior-1" });
          const status = await tools.run_status({});
          return { sourceRef: source.ref, priorRef: prior.ref, status };
        ` } }]
      : [{ type: "text", text: "Done." }];
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content,
      stopReason: turn === 1 ? "toolUse" : "stop",
      timestamp: Date.now(),
      usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: turn === 1 ? "toolUse" : "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  const mockBridge = {
    tools: [{
      name: "sql_exec",
      label: "sql_exec",
      description: "Run SQL",
      parameters: Type.Object({ sql: Type.String(), params: Type.Optional(Type.Record(Type.String(), Type.Unknown())) }),
      async execute(callId) {
        const ref = "src-run-status";
        const payload = { rows: [{ val: 1 }] };
        const record = { ref, callId, tool: "sql_exec", response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: false } };
        resultsMap.set(ref, record);
        return { content: [], details: undefined, structuredContent: { ref, tool: "sql_exec", result: payload, isError: false }, isError: false };
      },
    }],
    results: resultsMap,
    pid: 1003,
    close: async () => {},
  };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  try {
    const events = [];
    for await (const event of pi.stream({
      q: "Checkpoint a large analysis",
      history: [],
      model: "fixture:fixture",
      runTimeoutMs: 12345,
      sources: [makeSourceRecord("prior-1", { rows: [{ player: "Jokic", pts: 29.6 }] })],
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    }))
      events.push(event);
    assert.equal(events.find((event) => event.type === "answer")?.text, "Checkpoint partial.");
    const transcript = seenContexts.map((context) => context.messages.map((message) => messageText(message.content)).join("\n")).join("\n");
    assert.match(transcript, /"?ok"?\s*:\s*true/);
    assert.match(transcript, /tool_calls"?\s*:\s*4/);
    assert.match(transcript, /source_count"?\s*:\s*2/);
    assert.match(transcript, /submitted"?\s*:\s*true/);
    assert.match(transcript, /budget_ms"?\s*:\s*12345/);
    assert.match(transcript, /budget_remaining_ms"?\s*:\s*\d+/);
    assert.match(
      seenContexts[0].messages.map((message) => messageText(message.content)).join("\n"),
      /Host run budget: 12s \(12345ms total\)/
    );
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("no host budget context is injected when runTimeoutMs is unset", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-no-budget-ctx-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const seenContexts = [];
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    seenContexts.push(structuredClone(context));
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content: [{ type: "text", text: "Done." }],
      stopReason: "stop",
      timestamp: Date.now(),
      usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: "stop", message: msg });
    stream.end();
    return stream;
  });
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => ({ tools: [], results: new Map(), pid: 1006, close: async () => {} }),
  });

  try {
    for await (const event of pi.stream({
      q: "Quick question",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) void event;
    const transcript = seenContexts[0].messages.map((message) => messageText(message.content)).join("\n");
    assert(!transcript.includes("Host run budget:"));
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("repeated identical tool errors carry a data-limitation hint", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-repeat-error-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let turn = 0;
  const seenContexts = [];
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    turn++;
    seenContexts.push(structuredClone(context));
    const content = turn <= 2
      ? [{ type: "toolCall", id: `call-repeat-error-${turn}`, name: "codemode", arguments: { code: turn === 1
          ? `return await tools.get_trade_check({ give: ["Brown"], get: ["George"] });`
          : `return await tools.get_trade_check({ give: ["Brown"], get: ["George", "pick"] });` } }]
      : [{ type: "text", text: "Done." }];
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content,
      stopReason: turn <= 2 ? "toolUse" : "stop",
      timestamp: Date.now(),
      usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason, message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  let execCount = 0;
  const mockBridge = {
    tools: [{
      name: "get_trade_check",
      label: "get_trade_check",
      description: "Check a trade",
      parameters: Type.Object({ give: Type.Array(Type.String()), get: Type.Array(Type.String()) }),
      async execute(callId) {
        execCount++;
        const ref = `src-trade-${execCount}`;
        const payload = { ok: false, error: "salary data lists Jaylen Brown with PHI, not BOS; trade math was not calculated" };
        const record = { ref, callId, tool: "get_trade_check", response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: true } };
        resultsMap.set(ref, record);
        return { content: [{ type: "text", text: JSON.stringify(payload) }], details: undefined, structuredContent: { ref, tool: "get_trade_check", result: payload, isError: true }, isError: true };
      },
    }],
    results: resultsMap,
    pid: 1005,
    close: async () => {},
  };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  try {
    for await (const event of pi.stream({
      q: "Retry a failing trade check",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) void event;
    assert.equal(execCount, 2);
    const transcript = seenContexts.map((context) => context.messages.map((message) => messageText(message.content)).join("\n")).join("\n");
    assert.match(transcript, /repeated_error"?\s*:\s*"Same error as 1 earlier get_trade_check call/);
    assert.match(transcript, /recovery_hint"?\s*:\s*"Treat as a data limitation/);
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("consecutive tool failures trip a per-run circuit breaker", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-breaker-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let turn = 0;
  const seenContexts = [];
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    turn++;
    seenContexts.push(structuredClone(context));
    const content = turn === 1
      ? [{ type: "toolCall", id: "call-storm", name: "codemode", arguments: { code: `
          const out = [];
          for (let i = 0; i < 8; i++) { try { out.push(await tools.web_fetch({ url: "https://example.com/" + i })); } catch (e) { out.push(String(e)); } }
          return out;` } }]
      : [{ type: "text", text: "Done." }];
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content,
      stopReason: turn === 1 ? "toolUse" : "stop",
      timestamp: Date.now(),
      usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason, message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  let execCount = 0;
  const mockBridge = {
    tools: [{
      name: "web_fetch",
      label: "web_fetch",
      description: "Fetch a URL",
      parameters: Type.Object({ url: Type.String() }),
      async execute(callId) {
        execCount++;
        const ref = `src-fetch-${execCount}`;
        const payload = { ok: false, error: "404 Not Found" };
        const record = { ref, callId, tool: "web_fetch", response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: true } };
        resultsMap.set(ref, record);
        return { content: [{ type: "text", text: JSON.stringify(payload) }], details: undefined, structuredContent: { ref, tool: "web_fetch", result: payload, isError: true }, isError: true };
      },
    }],
    results: resultsMap,
    pid: 1006,
    close: async () => {},
  };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  try {
    const events = [];
    for await (const event of pi.stream({
      q: "Storm a failing fetch",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) events.push(event);
    assert.equal(execCount, 5);
    const transcript = seenContexts.map((context) => context.messages.map((message) => messageText(message.content)).join("\n")).join("\n");
    assert.match(transcript, /circuit_open/);
    assert.match(transcript, /blocked for the rest of this run/);
    assert.ok(resultsMap.has("breaker_5_web_fetch"));
    const breakerSources = events.filter((e) => e.type === "source" && String(e.record.ref).startsWith("breaker_"));
    assert.ok(breakerSources.length >= 1);
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("submit_answer accepts and reports omitted parts", async () => {
  const accepted = [];
  const tool = createSubmitAnswerTool(() => [], (submission) => accepted.push(submission));
  const result = await tool.execute("call-omit", {
    blocks: [{ text: "Partial verified answer." }],
    omitted: ["Trade candidates for Jaylen Brown", "Playoff shooting struggles"],
  });
  assert.equal(accepted.length, 1);
  assert.deepEqual(accepted[0].omitted, ["Trade candidates for Jaylen Brown", "Playoff shooting struggles"]);
  assert.match(result.content[0].text, /2 omitted part\(s\) recorded/);

  const full = validateAnswerSubmission({ blocks: [{ text: "Complete." }] }, () => undefined);
  assert.equal(full.omitted, undefined);
});

test("submit_answer and validateAnswerSubmission provide available columns and available refs hints", async () => {
  const src1 = makeSourceRecord("src-1", {
    rows: [{ player: "Jokic", pts: 29.6, trb: 12.7 }],
  });
  const src2 = makeSourceRecord("src-2", {
    rows: [{ team: "DEN" }],
  });
  const map = new Map([
    ["src-1", src1],
    ["src-2", src2],
  ]);

  assert.throws(
    () =>
      validateAnswerSubmission(
        {
          blocks: [
            {
              text: "Claim",
              anchors: [{ ref: "src-1", row: 0, columns: ["points"] }],
            },
          ],
        },
        (ref) => map.get(ref)
      ),
    (err) => {
      assert.equal(
        err.message,
        "Column 'points' does not exist on row 0 for ref: src-1. Available columns: [player, pts, trb]. Fix the column name or omit anchors for derived values."
      );
      return true;
    }
  );

  const tool = createSubmitAnswerTool(
    () => [src1, src2],
    () => {}
  );
  await assert.rejects(
    () =>
      tool.execute("call-1", {
        blocks: [
          {
            text: "Claim",
            anchors: [{ ref: "missing-ref", row: 0, columns: ["player"] }],
          },
        ],
      }),
    (err) => {
      assert.equal(
        err.message,
        "Unknown source ref: missing-ref. Available refs: [src-1, src-2]"
      );
      return true;
    }
  );
});

test("accepted submit_answer is emitted when the run aborts before prompt returns", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-submit-abort-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });
  let markEntered;
  const entered = new Promise((resolve) => { markEntered = resolve; });
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    const content = turn === 1
      ? [{ type: "toolCall", id: "call-submit-abort", name: "codemode", arguments: { code: `
          await tools.submit_answer({ blocks: [{ text: "Checkpoint answer." }] });
          return await tools.wait_for_cancel({});
        ` } }]
      : [{ type: "text", text: "Done." }];
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content,
      stopReason: turn === 1 ? "toolUse" : "stop",
      timestamp: Date.now(),
      usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason, message: msg });
    stream.end();
    return stream;
  });
  const mockBridge = {
    tools: [{
      name: "wait_for_cancel",
      label: "wait_for_cancel",
      description: "Wait until cancelled",
      parameters: Type.Object({}, { additionalProperties: false }),
      async execute(_callId, _args, signal) {
        markEntered();
        await new Promise((resolve, reject) => {
          const fail = () => reject(new Error("fixture cancelled"));
          if (signal?.aborted) fail();
          else signal?.addEventListener("abort", fail, { once: true });
        });
      },
    }],
    results: new Map(),
    pid: 1004,
    close: async () => {},
  };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
    abortGraceMs: 20,
  });
  const abort = new AbortController();
  const events = [];
  try {
    const consuming = (async () => {
      for await (const event of pi.stream({
        q: "Submit then hang",
        history: [],
        model: "fixture:fixture",
        cwd,
        agentDir,
        bridge: { python: "fake", cwd, env: {} },
      }, abort.signal)) events.push(event);
    })();
    await entered;
    abort.abort();
    await consuming;
    const answer = events.find((event) => event.type === "answer");
    assert.equal(answer?.text, "Checkpoint answer.");
    assert.equal(answer?.submission?.blocks?.[0]?.text, "Checkpoint answer.");
    assert(!events.some((event) => event.type === "failure"));
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("host bootstrap failure names the missing manifest variable on stderr", () => {
  const printed = [];
  reportBootstrapFailure(
    new Error("DIME_EXPECTED_ASSET_MANIFEST is required"),
    (text) => printed.push(text)
  );
  const stderr = printed.join("");
  assert.match(stderr, /^Dime host failed: DIME_EXPECTED_ASSET_MANIFEST is required\n/);
  assert.match(stderr, /Error: DIME_EXPECTED_ASSET_MANIFEST is required/);
  assert.match(stderr, /\n\s+at /);
});

const defaultHistory = [
  { role: "user", content: "Who led the league in points?" },
  { role: "assistant", content: "Luka Doncic at 33.5 PPG.", reasoning: "Checked league scoring leaders." },
];

async function contextsForHistory(compat, history = defaultHistory) {
  const cwd = await mkdtemp(join(tmpdir(), "dime-history-"));
  const agentDir = join(cwd, "agent");
  const bridgeCwd = join(cwd, "bridge-ws");
  await mkdir(agentDir, { recursive: true });
  await mkdir(bridgeCwd, { recursive: true });
  const seenContexts = [];
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    seenContexts.push(structuredClone(context));
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: "stop", message: { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "text", text: "Done." }], stopReason: "stop", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } } });
    stream.end();
    return stream;
  }, compat);
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => ({ tools: [], results: new Map(), pid: 1001, close: async () => {} }),
  });
  try {
    for await (const event of pi.stream({
      q: "And their defensive rating?",
      history,
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd: bridgeCwd, env: {} },
    })) void event;
    return seenContexts[0].messages;
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
}

test("history replays as assistant turns by default", async () => {
  const messages = await contextsForHistory(undefined);
  const assistant = messages.find((m) => m.role === "assistant");
  assert.ok(assistant);
  assert.equal(assistant.content.some((block) => block.type === "thinking"), false);
});

test("history replays stored reasoning for models requiring it", async () => {
  const messages = await contextsForHistory({ requiresReasoningContentOnAssistantMessages: true });
  const assistant = messages.find((m) => m.role === "assistant");
  assert.ok(assistant);
  const thinking = assistant.content.find((block) => block.type === "thinking");
  assert.ok(thinking);
  assert.equal(thinking.thinking, "Checked league scoring leaders.");
  assert.equal(thinking.thinkingSignature, "reasoning_content");
  assert.ok(assistant.content.some((block) => block.type === "text" && block.text === "Luka Doncic at 33.5 PPG."));
});

test("history supplies non-empty reasoning when a prior turn has none", async () => {
  const messages = await contextsForHistory(
    { requiresReasoningContentOnAssistantMessages: true },
    [{ role: "user", content: "Who led the league in points?" }, { role: "assistant", content: "Luka Doncic at 33.5 PPG." }],
  );
  const assistant = messages.find((m) => m.role === "assistant");
  assert.ok(assistant);
  const thinking = assistant.content.find((block) => block.type === "thinking");
  assert.ok(thinking);
  assert.ok(thinking.thinking.trim().length > 0);
  assert.equal(thinking.thinkingSignature, "reasoning_content");
});

test("answer events carry assistant reasoning", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-reasoning-"));
  const agentDir = join(cwd, "agent");
  const bridgeCwd = join(cwd, "bridge-ws");
  await mkdir(agentDir, { recursive: true });
  await mkdir(bridgeCwd, { recursive: true });
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: "stop", message: { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "thinking", thinking: "Reasoning about the answer.", thinkingSignature: "reasoning_content" }, { type: "text", text: "Done." }], stopReason: "stop", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } } });
    stream.end();
    return stream;
  });
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => ({ tools: [], results: new Map(), pid: 1001, close: async () => {} }),
  });
  const events = [];
  try {
    for await (const event of pi.stream({ q: "Explain the answer.", history: [], model: "fixture:fixture", cwd, agentDir, bridge: { python: "fake", cwd: bridgeCwd, env: {} } }))
      events.push(event);
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
  assert.equal(events.find((event) => event.type === "answer")?.reasoning, "Reasoning about the answer.");
});

test("pi execution stream ends after abort even when the run never settles", async () => {
  const pi = createPiExecution({
    resolveRuntime: () => new Promise(() => {}),
    connectTools: async () => ({ tools: [], results: new Map(), pid: 1, close: async () => {} }),
    abortGraceMs: 50,
  });
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20);
  const keepAlive = setInterval(() => {}, 1000);
  const events = [];
  try {
    for await (const event of pi.stream({ q: "hang", history: [], model: "fixture:fixture", cwd: tmpdir(), agentDir: tmpdir(), bridge: { python: "fake", cwd: tmpdir(), env: {} } }, controller.signal))
      events.push(event);
  } finally {
    clearTimeout(timer);
    clearInterval(keepAlive);
  }
  assert.equal(events.some((e) => e.type === "answer"), false);
});

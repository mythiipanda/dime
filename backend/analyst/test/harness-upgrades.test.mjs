import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Type } from "typebox";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";
import { createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import { reportBootstrapFailure } from "../dist/host.js";
import {
  canonicalArgsKey,
  createPiExecution,
  createProviderRetryStormGuard,
  flagAcknowledgedByOmissions,
  listWorkspaceArtifacts,
  normalizeLoopArgs,
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

test("normalizeLoopArgs folds empty, case, and team id/abbrev variants into one key", () => {
  const keyOf = (args) => canonicalArgsKey(normalizeLoopArgs(args));
  assert.equal(
    keyOf({ team: "", season: "2025-26" }),
    keyOf({ season: "2025-26" })
  );
  assert.equal(
    keyOf({ team: "BOS", season: "2025-26" }),
    keyOf({ team_id: 1610612738, season: "2025-26" })
  );
  assert.equal(
    keyOf({ team: "bos", season: "2025-26" }),
    keyOf({ team: "BOS", season: "2025-26" })
  );
  assert.equal(
    keyOf({ teams: "BOS, MIL" }),
    keyOf({ teams: "mil, bos" })
  );
  assert.notEqual(
    keyOf({ team: "BOS" }),
    keyOf({ team: "MIL" })
  );
});

test("normalizeLoopArgs canonicalizes season years to YYYY-YY", () => {
  const keyOf = (args) => canonicalArgsKey(normalizeLoopArgs(args));
  assert.equal(
    keyOf({ player: "Shake Milton", season: 2021 }),
    keyOf({ player: "Shake Milton", season: "2021-22" })
  );
  assert.equal(
    keyOf({ season: "2021" }),
    keyOf({ season: "2021-22" })
  );
  assert.equal(
    keyOf({ start_season: "2021-2022" }),
    keyOf({ start_season: "2021-22" })
  );
  assert.equal(
    keyOf({ seasons: [2021, "2022"] }),
    keyOf({ seasons: ["2021-22", "2022-23"] })
  );
});

test("canonicalArgsKey normalizes nested key order and wrapBridgeTools short-circuits repeated identical calls", async () => {
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
    assert.equal(execCount, 1);
    const toolResults = events.filter((e) => e.type === "tool_result");
    assert.equal(toolResults.length, 3);
    assert.equal(toolResults[0].status, "ok");
    assert.equal(toolResults[1].status, "ok");
    assert.equal(toolResults[2].status, "fail");
    assert.match(toolResults[1].result, /reused result of src-exec-1/);
    assert.match(toolResults[2].error, /STOP re-issuing this query/);
    assert.match(toolResults[2].error, /src-exec-1/);

    const loopSource = events.find(
      (e) => e.type === "source" && /^loop_\d+_sql_exec$/.test(e.record.ref)
    );
    assert.equal(
      loopSource,
      undefined,
      "Successful repeats replay the cached result instead of emitting a loop record"
    );
    assert.equal(
      events.find((e) => e.type === "answer")?.text,
      "Recovered after loop warning."
    );
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("sql_exec cosmetic rewrites share one loop key and six interceptions fire the storm steer", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-dupe-storm-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let execCount = 0;
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    if (turn === 1) {
      const pairs = [
        ["SELECT 1", "  select   1 ;\n"],
        ["SELECT 2", "SELECT  2-- trailing\n"],
        ["SELECT 3", "\n\nselect 3  "],
        ["SELECT 4", "SELECT 4;"],
        ["SELECT 5", "select      5"],
        ["SELECT 6", "SELECT 6 /* c */"],
      ];
      const calls = pairs
        .flatMap((pair, i) => pair.map((sql, j) => `await tools.sql_exec({ sql: ${JSON.stringify(sql)} })`))
        .join(";\n");
      const code = `${calls}; return { done: true };`;
      const msg = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        content: [{ type: "toolCall", id: "call-storm", name: "codemode", arguments: { code } }],
        stopReason: "toolUse",
        timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheWrite: 0, total: 0 } },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: "toolUse", message: msg });
      stream.end();
      return stream;
    }
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content: [{ type: "text", text: "done" }],
      stopReason: "stop",
      timestamp: Date.now(),
      usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheWrite: 0, total: 0 } },
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
        parameters: Type.Object({ sql: Type.String() }),
        async execute(callId) {
          execCount++;
          const ref = `src-exec-${execCount}`;
          const payload = { rows: [{ val: 1 }] };
          const record = {
            ref,
            callId,
            tool: "sql_exec",
            response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: false },
          };
          resultsMap.set(ref, record);
          return { content: [], details: undefined, structuredContent: { ref, tool: "sql_exec", result: payload, isError: false }, isError: false };
        },
      },
    ],
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
      q: "storm test",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    assert.equal(execCount, 6, "cosmetic rewrites must not execute — only the first of each pair runs");
    const storm = events.find((e) => e.type === "tool_result" && e.name === "dupe_storm_steer");
    assert.ok(storm, "dupe_storm_steer emitted once the run crosses six interceptions");
    const stormCalls = events.filter((e) => e.type === "tool_call" && e.name === "dupe_storm_steer");
    assert.equal(stormCalls.length, 1, "storm steer is one-shot");
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("provider retry storm guard stops the run on the first exhausted call", () => {
  const emitted = [];
  let stoppedWith = null;
  const guard = createProviderRetryStormGuard(
    (event) => emitted.push(event),
    (reason) => { stoppedWith = reason; }
  );
  for (let i = 0; i < 20; i++)
    guard({ type: "auto_retry_start", attempt: i + 1, maxAttempts: 6, delayMs: 5000, errorMessage: "429" });
  guard({ type: "auto_retry_end", success: true, attempt: 6 });
  guard({ type: "auto_retry_end", success: true, attempt: 6 });
  assert.equal(emitted.length, 0);
  assert.equal(stoppedWith, null);
  guard({ type: "auto_retry_end", success: false, attempt: 6, finalError: "429 rate limited" });
  assert.match(stoppedWith, /exhausted all retries against a saturated lane/);
  assert.match(stoppedWith, /429 rate limited/);
});

test("provider retry storm guard fires the retry-time budget once on cumulative delay", () => {
  const emitted = [];
  let stoppedWith = null;
  let burned = 0;
  const guard = createProviderRetryStormGuard(
    (event) => emitted.push(event),
    (reason) => { stoppedWith = reason; },
    (ms) => { burned = ms; },
    30_000
  );
  for (let i = 0; i < 5; i++)
    guard({ type: "auto_retry_start", attempt: i + 1, maxAttempts: 6, delayMs: 5000, errorMessage: "429" });
  assert.equal(burned, 0);
  guard({ type: "auto_retry_start", attempt: 6, maxAttempts: 6, delayMs: 5000, errorMessage: "429" });
  assert.equal(burned, 30_000);
  guard({ type: "auto_retry_start", attempt: 7, maxAttempts: 6, delayMs: 5000, errorMessage: "429" });
  assert.equal(burned, 30_000);
  assert.equal(stoppedWith, null);
});

test("wrapBridgeTools terminates the run on the 4th blocked repeat of a failing call", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-loop-stop-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let execCount = 0;
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    if (turn <= 7) {
      const code = `return await tools.sql_exec({ sql: "SELECT 1", params: { a: 1 } });`;
      const msg = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        content: [
          { type: "toolCall", id: `call-loop-stop-${turn}`, name: "codemode", arguments: { code } },
        ],
        stopReason: "toolUse",
        timestamp: Date.now(),
        usage: {
          input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: "toolUse", message: msg });
      stream.end();
      return stream;
    }
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content: [{ type: "text", text: "should not reach" }],
      stopReason: "stop",
      timestamp: Date.now(),
      usage: {
        input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
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
        parameters: Type.Object({}),
        async execute(callId) {
          execCount++;
          const ref = `src-stop-${execCount}`;
          const payload = { ok: false, error: "warehouse unavailable" };
          const record = {
            ref,
            callId,
            tool: "sql_exec",
            response: {
              content: [{ type: "text", text: JSON.stringify(payload) }],
              structuredContent: payload,
              isError: true,
            },
          };
          resultsMap.set(ref, record);
          return {
            content: [],
            details: undefined,
            structuredContent: { ref, tool: "sql_exec", result: payload, isError: true },
            isError: true,
          };
        },
      },
    ],
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
      q: "Test loop stop",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    assert.equal(execCount, 1);
    const toolResults = events.filter((e) => e.type === "tool_result" && e.name === "sql_exec");
    assert.equal(toolResults.length, 5);
    for (const result of toolResults)
      assert.equal(result.status, "fail");
    assert.match(toolResults[4].error, /Run stopped: sql_exec called 5 times/);
    const pivotSource = events.find(
      (e) => e.type === "source" && e.record.ref === "loop_2_sql_exec"
    );
    assert.ok(pivotSource, "failing repeats should emit a pivot source record");
    const pivotPayload = pivotSource.record.response.structuredContent;
    assert.equal(pivotPayload.repeated_failure, true);
    assert.equal(pivotPayload.last_error, "warehouse unavailable");
    assert.match(pivotPayload.error, /keeps failing.*do not retry/);
    const stopSource = events.find(
      (e) => e.type === "source" && e.record.ref === "loop_stop_5_sql_exec"
    );
    assert.ok(stopSource, "loop-stop source record should be emitted");
    assert.equal(stopSource.record.response.structuredContent.loop_terminated, true);
    assert.equal(stopSource.record.response.structuredContent.stop_reason, "tool_call_loop");
    const failure = events.find((e) => e.type === "failure");
    assert.ok(failure, "run should terminate with a failure event");
    assert.equal(failure.kind, "loop_stop");
    assert.match(failure.message, /Run stopped: sql_exec called 5 times/);
    assert.equal(turn, 5, "model should not get another turn after the loop stop");
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

test("near-budget steer nudges submit_answer before the host abort", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-budget-nudge-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });
  const seenContexts = [];
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    turn++;
    seenContexts.push(structuredClone(context));
    const content = turn === 1
      ? [{ type: "toolCall", id: "call-nudge", name: "codemode", arguments: { code: "await tools.hold({});" } }]
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
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => ({
      tools: [{
        name: "hold",
        label: "hold",
        description: "Hold briefly",
        parameters: Type.Object({}, { additionalProperties: false }),
        async execute() {
          await new Promise((resolve) => setTimeout(resolve, 120));
          return sourceResult(makeSourceRecord("hold", { rows: [] }));
        },
      }],
      results: new Map([["hold", makeSourceRecord("hold")]]),
      pid: 1005,
      close: async () => {},
    }),
    budgetNudgeDelayMs: 5,
  });
  try {
    for await (const _event of pi.stream({
      q: "Pace a long analysis",
      history: [],
      model: "fixture:fixture",
      runTimeoutMs: 60000,
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
    }
    const secondTurn = seenContexts[1].messages.map((message) => messageText(message.content)).join("\n");
    assert.match(secondTurn, /Host run budget nearly exhausted/);
    assert.match(secondTurn, /submit_answer/);
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
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

test("tool_result events carry traced payloads only when DIME_TRACE_TOOL_RESULTS is set", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-trace-results-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const payload = { rows: [{ val: 7 }], columns: ["val"] };
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
          const ref = `src-trace-${callId}`;
          resultsMap.set(ref, {
            ref,
            callId,
            tool: "sql_exec",
            response: {
              content: [{ type: "text", text: JSON.stringify(payload) }],
              structuredContent: payload,
              isError: false,
            },
          });
          return {
            content: [],
            details: undefined,
            structuredContent: { ref, tool: "sql_exec", result: payload, isError: false },
            isError: false,
          };
        },
      },
    ],
    results: resultsMap,
    pid: 1007,
    close: async () => {},
  };

  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    const content =
      turn === 1
        ? [
            {
              type: "toolCall",
              id: "call-trace",
              name: "codemode",
              arguments: { code: `return await tools.sql_exec({ sql: "SELECT 7" });` },
            },
          ]
        : [{ type: "text", text: "Done." }];
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content,
      stopReason: turn === 1 ? "toolUse" : "stop",
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
    stream.push({ type: "done", reason: msg.stopReason, message: msg });
    stream.end();
    return stream;
  });

  const pi = createPiExecution({
    resolveRuntime: async () => ({
      runtime,
      model: runtime.getModel("fixture", "fixture"),
    }),
    connectTools: async () => mockBridge,
  });

  const runOnce = async () => {
    const events = [];
    for await (const event of pi.stream({
      q: "Run one query",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    return events.find((e) => e.type === "tool_result" && e.name === "sql_exec");
  };

  try {
    delete process.env.DIME_TRACE_TOOL_RESULTS;
    turn = 0;
    const untraced = await runOnce();
    assert.equal(untraced.result, undefined);
    assert.equal(untraced.result_sha256, undefined);

    process.env.DIME_TRACE_TOOL_RESULTS = "1";
    turn = 0;
    const traced = await runOnce();
    const serialized = JSON.stringify(payload);
    assert.equal(traced.result, serialized);
    assert.equal(traced.result_bytes, serialized.length);
    assert.match(traced.result_sha256, /^[0-9a-f]{64}$/);
    assert.equal(traced.result_truncated, undefined);
  } finally {
    delete process.env.DIME_TRACE_TOOL_RESULTS;
    await rm(cwd, { recursive: true, force: true });
  }
});

test("history replays stored reasoning for thinking-as-text models", async () => {
  const messages = await contextsForHistory({ requiresThinkingAsText: true });
  const assistant = messages.find((m) => m.role === "assistant");
  assert.ok(assistant);
  const thinking = assistant.content.find((block) => block.type === "thinking");
  assert.ok(thinking);
  assert.equal(thinking.thinking, "Checked league scoring leaders.");
});

test("cerebras thinking-as-text models resolve with compat, not reasoning_content replay", async () => {
  const { providerPolicy } = await import("../dist/providers.js");
  const policy = providerPolicy({ CEREBRAS_API_KEY: "test-key" });
  const resolved = policy.resolve("cerebras:gpt-oss-120b");
  assert.equal(resolved.compat.requiresThinkingAsText, true);
  assert.equal(resolved.compat.requiresReasoningContentOnAssistantMessages, undefined);
});

test("wrapBridgeTools warns at the call ceiling then stops the run at the churn cap", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-call-ceiling-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let execCount = 0;
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    if (turn <= 6) {
      const code = `return await tools.sql_exec({ sql: "SELECT 1", params: { a: ${turn} } });`;
      const msg = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        content: [
          { type: "toolCall", id: `call-ceiling-${turn}`, name: "codemode", arguments: { code } },
        ],
        stopReason: "toolUse",
        timestamp: Date.now(),
        usage: {
          input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: "toolUse", message: msg });
      stream.end();
      return stream;
    }
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content: [{ type: "text", text: "should not reach" }],
      stopReason: "stop",
      timestamp: Date.now(),
      usage: {
        input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
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
        parameters: Type.Object({}),
        async execute(callId) {
          execCount++;
          const ref = `src-ceiling-${execCount}`;
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
            structuredContent: { ref, tool: "sql_exec", result: payload, isError: false },
            isError: false,
          };
        },
      },
    ],
    results: resultsMap,
    pid: 1004,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  process.env.DIME_CALL_CEILING_WARN = "3";
  process.env.DIME_CALL_CEILING_STOP = "5";
  try {
    const events = [];
    for await (const event of pi.stream({
      q: "Test call ceiling",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    assert.equal(execCount, 3);
    const toolResults = events.filter((e) => e.type === "tool_result" && e.name === "sql_exec");
    assert.equal(toolResults.length, 5);
    assert.equal(toolResults[0].status, "ok");
    assert.equal(toolResults[1].status, "ok");
    assert.equal(toolResults[3].status, "ok");
    assert.match(toolResults[2].error, /High tool-call count/);
    assert.match(toolResults[4].error, /Run stopped: 5 tool calls.*churn ceiling/);
    const warnSource = events.find(
      (e) => e.type === "source" && e.record.ref === "call_ceiling_3_sql_exec"
    );
    assert.ok(warnSource, "ceiling-warn source record should be emitted");
    assert.equal(warnSource.record.response.structuredContent.call_ceiling, true);
    const stopSource = events.find(
      (e) => e.type === "source" && e.record.ref === "churn_stop_5_sql_exec"
    );
    assert.ok(stopSource, "churn-stop source record should be emitted");
    assert.equal(stopSource.record.response.structuredContent.stop_reason, "tool_call_churn");
    const failure = events.find((e) => e.type === "failure");
    assert.ok(failure, "run should terminate with a failure event");
    assert.match(failure.message, /churn ceiling/);
    assert.equal(turn, 5, "model should not get another turn after the churn stop");
  } finally {
    delete process.env.DIME_CALL_CEILING_WARN;
    delete process.env.DIME_CALL_CEILING_STOP;
    await rm(cwd, { recursive: true, force: true });
  }
});

test("verify_answer_numbers flags prose figures missing from artifact payloads", async () => {
  const { auditAnswerNumbers } = await import("../dist/verify-answer.js");
  const sources = [
    makePayloadSourceRecord("src-1", { rows: [{ ortg: 118.4, drtg: 112.1 }] }),
  ];
  const artifactsOnlyProse = auditAnswerNumbers(
    {
      blocks: [{ text: "OKC's offensive rating is 118.4 and defensive rating 112.1." }],
      artifacts: [{ kind: "table", title: "Ratings", columns: [{ key: "team", label: "Team" }], rows: [{ team: "OKC" }] }],
    },
    sources,
  );
  assert.ok(artifactsOnlyProse.missing_in_artifacts.length >= 2);
  assert.ok(artifactsOnlyProse.missing_in_artifacts.some((claim) => claim.values.includes(118.4)));

  const covered = auditAnswerNumbers(
    {
      blocks: [{ text: "OKC's offensive rating is 118.4." }],
      artifacts: [{ kind: "table", title: "Ratings", columns: [{ key: "ortg", label: "ORTG", numeric: true }], rows: [{ team: "OKC", ortg: 118.4 }] }],
    },
    sources,
  );
  assert.equal(covered.missing_in_artifacts.length, 0);

  const noArtifacts = auditAnswerNumbers(
    { blocks: [{ text: "OKC's offensive rating is 118.4." }] },
    sources,
  );
  assert.equal(noArtifacts.missing_in_artifacts.length, 0);
});

test("verify_answer_numbers flags question clauses with no matching terms in the answer", async () => {
  const { auditAnswerNumbers } = await import("../dist/verify-answer.js");
  const sources = [makePayloadSourceRecord("src-1", { rows: [{ wins: 56 }] })];
  const question = "Compare MEM's 2021-22 early-season and late-season win splits. Compute the HHI of the top-8 rotation minutes share.";
  const partial = auditAnswerNumbers(
    { blocks: [{ text: "MEM went 56-26 in 2021-22 with a strong late-season stretch." }] },
    sources,
    question,
  );
  assert.equal(partial.uncovered_asks.length, 1);
  assert.ok(partial.uncovered_asks[0].includes("HHI"));

  const full = auditAnswerNumbers(
    { blocks: [{ text: "MEM went 56-26 in 2021-22. The top-8 minutes HHI is 0.097." }] },
    sources,
    question,
  );
  assert.equal(full.uncovered_asks.length, 0);

  const noQuestion = auditAnswerNumbers(
    { blocks: [{ text: "Anything at all." }] },
    sources,
  );
  assert.equal(noQuestion.uncovered_asks.length, 0);
});

test("verify_answer_numbers flags narrated facets absent from all tool evidence", async () => {
  const { auditAnswerNumbers } = await import("../dist/verify-answer.js");
  const question = "Measure lineup continuity for CHI 2022-23 versus the preceding season in `silver_hist_lineups`. Report the eligible unit count and possession-weighted mean net rating.";
  const planNotAnswer = auditAnswerNumbers(
    {
      blocks: [{ text: "Summary of what would be needed: pull CHI 2022-23 five-man lineups, filter to poss>=25 and non-null net rating, canonicalize the five IDs, then report the eligible unit count and possession-weighted mean net rating." }],
    },
    [],
    question,
  );
  assert.ok(planNotAnswer.unevidenced_asks.length >= 1);

  const evidenced = auditAnswerNumbers(
    {
      blocks: [{ text: "CHI carried 14 eligible lineup units in 2022-23 with a possession-weighted mean net rating of -1.8." }],
    },
    [
      makePayloadSourceRecord("src-1", { rows: [{ team: "CHI", units: 14, poss: 612, net_rating: -1.8 }] }),
    ],
    question,
  );
  assert.equal(evidenced.unevidenced_asks.length, 0);

  const derivedMath = auditAnswerNumbers(
    {
      blocks: [{ text: "The possession-weighted mean net rating for CHI 2022-23 lineups is -1.8." }],
    },
    [
      makePayloadSourceRecord("rp-1", { stdout: "chi 2022-23 net_rating weighted mean -1.8" }, { tool: "run_python" }),
    ],
    question,
    "{\"code\":\"df['net_rating'] * df['poss']\"}",
  );
  assert.equal(derivedMath.unevidenced_asks.length, 0);
});

test("submit_answer vetoes once on pre-audit gaps then accepts the retry", async () => {
  const { createSubmitAnswerTool } = await import("../dist/submit-tool.js");
  const accepted = [];
  let audits = 0;
  const tool = createSubmitAnswerTool(
    () => [],
    (submission) => accepted.push(submission),
    () => {
      audits++;
      return audits === 1 ? "Not submitted — the honesty audit found gaps" : null;
    }
  );
  const args = { blocks: [{ text: "MEM went 56-26." }] };
  const rejected = await tool.execute("call-a1", args);
  assert.equal(accepted.length, 0);
  assert.match(rejected.content[0].text, /Not submitted/);
  const ok = await tool.execute("call-a2", args);
  assert.equal(accepted.length, 1);
  assert.match(ok.content[0].text, /Answer submitted with 1 block/);
});

test("verify_answer_numbers flags artifact asks answered with zero artifacts", async () => {
  const { auditAnswerNumbers } = await import("../dist/verify-answer.js");
  const sources = [makePayloadSourceRecord("src-1", { rows: [{ wins: 56, losses: 26 }] })];
  const question = "Compare MEM's 2021-22 and 2022-23 win splits and return a table artifact.";
  const emptyArtifacts = auditAnswerNumbers(
    { blocks: [{ text: "MEM went 56-26 in 2021-22." }] },
    sources,
    question,
  );
  assert.deepEqual([...emptyArtifacts.no_artifacts_on_artifact_ask].sort(), ["compare", "table"]);

  const withArtifacts = auditAnswerNumbers(
    {
      blocks: [{ text: "MEM went 56-26 in 2021-22." }],
      artifacts: [{ kind: "table", title: "Splits", columns: [{ key: "wins", label: "W", numeric: true }], rows: [{ wins: 56 }] }],
    },
    sources,
    question,
  );
  assert.equal(withArtifacts.no_artifacts_on_artifact_ask.length, 0);

  const noArtifactAsk = auditAnswerNumbers(
    { blocks: [{ text: "MEM went 56-26 in 2021-22." }] },
    sources,
    "Who led MEM in scoring in 2021-22?",
  );
  assert.equal(noArtifactAsk.no_artifacts_on_artifact_ask.length, 0);
});

test("verify_answer_numbers skips stipulated echoes but flags coincidental hallucinations", async () => {
  const { auditAnswerNumbers } = await import("../dist/verify-answer.js");
  const sources = [makePayloadSourceRecord("src-1", { rows: [{ player: "Example Player", salary: 5000000 }] })];
  const question = "Using the stipulated apron of $207800000 and matching band outgoing <= $7250000 permitting the 200% rule, evaluate the trade.";
  const restated = auditAnswerNumbers(
    {
      blocks: [{ text: "The stipulated apron is $207,800,000 and the matching band for outgoing <= $7,250,000 permits the 200% rule as the question stipulated." }],
      artifacts: [{ kind: "table", title: "T", columns: [{ key: "salary", label: "S", numeric: true }], rows: [{ salary: 5000000 }] }],
    },
    sources,
    question,
  );
  const restatedFlags = JSON.stringify(restated.unsupported_claims) + JSON.stringify(restated.missing_in_artifacts);
  assert.ok(!restatedFlags.includes("207,800,000") && !restatedFlags.includes("7,250,000"), "stipulated restatement should pass unaudited");

  const hallucinated = auditAnswerNumbers(
    {
      blocks: [{ text: "His extension salary reaches $207,800,000 over the lifetime of the deal." }],
      artifacts: [{ kind: "table", title: "T", columns: [{ key: "salary", label: "S", numeric: true }], rows: [{ salary: 5000000 }] }],
    },
    sources,
    question,
  );
  assert.ok(JSON.stringify(hallucinated.unsupported_claims).includes("207,800,000"), "coincidental hallucination without rule context must still flag");
});

test("verify_answer_numbers accepts inline JSON chart specs as artifact coverage", async () => {
  const { auditAnswerNumbers } = await import("../dist/verify-answer.js");
  const sources = [makePayloadSourceRecord("src-1", { rows: [{ season: "2024-25", net_rating: 3.8 }] })];
  const question = 'Produce a structured multi-line trend-chart payload (JSON spec or tool artifact with "kind": "line") plotting ratings per season.';
  const inlineLine = auditAnswerNumbers(
    {
      blocks: [{
        text: 'Denver peaked in 2023-24.\n```json\n{"kind": "line", "title": "Nuggets ratings", "xLabels": ["2023-24", "2024-25"], "series": [{"name": "net rating", "values": [3.8, 3.8]}]}\n```',
      }],
    },
    sources,
    question,
  );
  assert.equal(inlineLine.no_artifacts_on_artifact_ask.length, 0);

  const barQuestion = 'Produce a structured bar-chart payload (JSON spec or tool artifact with "kind": "bar") of the top 10 scorers.';
  const inlineBar = auditAnswerNumbers(
    {
      blocks: [{
        text: 'SGA leads at 32.7.\n```json\n{"kind": "bar", "title": "Top scorers", "xLabels": ["SGA"], "series": [{"name": "ppg", "values": [32.7]}]}\n```',
      }],
    },
    sources,
    barQuestion,
  );
  assert.equal(inlineBar.no_artifacts_on_artifact_ask.length, 0);

  const noSpec = auditAnswerNumbers(
    { blocks: [{ text: "Denver peaked in 2023-24." }] },
    sources,
    question,
  );
  assert.ok(noSpec.no_artifacts_on_artifact_ask.length > 0);
});

test("verify_answer_numbers flags required stat terms absent from prose and payloads", async () => {
  const { auditAnswerNumbers } = await import("../dist/verify-answer.js");
  const sources = [makePayloadSourceRecord("src-1", { rows: [{ ortg: 118.4, pw_net: 9.4 }] })];

  const question = "What were OKC's net rating and pythagorean net rating in 2024-25?";
  const partial = auditAnswerNumbers(
    { blocks: [{ text: "OKC's net rating was +118.4 in 2024-25." }] },
    sources,
    question,
  );
  assert.deepEqual(partial.metric_value_gaps, ['pw_net (asked via "pythagorean")']);

  const payloadCovered = auditAnswerNumbers(
    {
      blocks: [{ text: "OKC's net rating was +118.4." }],
      artifacts: [{ kind: "table", title: "Ratings", columns: [{ key: "pw_net", label: "PW_NET", numeric: true }], rows: [{ team: "OKC", pw_net: 9.4 }] }],
    },
    sources,
    question,
  );
  assert.equal(payloadCovered.metric_value_gaps.length, 0);

  const proseCovered = auditAnswerNumbers(
    { blocks: [{ text: "OKC's net rating was +118.4 and the pythagorean net rating was +9.4." }] },
    sources,
    question,
  );
  assert.equal(proseCovered.metric_value_gaps.length, 0);

  const rotation = auditAnswerNumbers(
    { blocks: [{ text: "DEN's top rotation players average over 30 minutes." }] },
    sources,
    "Compare DEN's rotation minutes and fg% leaders.",
  );
  assert.deepEqual(rotation.metric_value_gaps, ['fg_pct (asked via "fg%")']);

  const roster = auditAnswerNumbers(
    { blocks: [{ text: "The Lakers have a deep roster." }] },
    sources,
    "List the Lakers roster names for 2024-25.",
  );
  assert.equal(roster.metric_value_gaps.length, 0);

  const noQuestion = auditAnswerNumbers(
    { blocks: [{ text: "Anything at all." }] },
    sources,
  );
  assert.equal(noQuestion.metric_value_gaps.length, 0);
});

test("verify_answer_numbers flags stat-shaped figures tracing to no tool output", async () => {
  const { auditAnswerNumbers } = await import("../dist/verify-answer.js");
  const sources = [
    makePayloadSourceRecord("src-1", { rows: [{ pts: 350, fga: 210, fta: 80 }] }),
  ];

  const fabricated = auditAnswerNumbers(
    { blocks: [{ text: "His true shooting was 0.762 with a 31.4 usage rate." }] },
    sources,
  );
  assert.equal(fabricated.unsupported_claims.length, 2);
  assert.ok(fabricated.unsupported_claims[0].includes("0.762"));

  const traced = auditAnswerNumbers(
    { blocks: [{ text: "His true shooting was 0.762." }] },
    [
      ...sources,
      makePayloadSourceRecord("src-2", { stdout: "ts = 350 / (2 * (210 + 0.44 * 80)) = 0.7621" }),
    ],
  );
  assert.equal(traced.unsupported_claims.length, 0);

  const countClaims = auditAnswerNumbers(
    { blocks: [{ text: "He appeared in 7 games and hit 4 threes." }] },
    sources,
  );
  assert.equal(countClaims.unsupported_claims.length, 0);

  const promptConstants = auditAnswerNumbers(
    { blocks: [{ text: "The top-8 share clears the 0.85 benchmark comfortably." }] },
    sources,
    "Compute the HHI of the top-8 rotation minutes share and compare it to the 0.85 benchmark.",
  );
  assert.equal(promptConstants.unsupported_claims.length, 0);

  const supported = auditAnswerNumbers(
    { blocks: [{ text: "He scored 350 points on 210 shots." }] },
    sources,
  );
  assert.equal(supported.unsupported_claims.length, 0);

  const metaNarration = auditAnswerNumbers(
    { blocks: [{ text: "Partial answer: the host's 360 s budget was already ~110 s into retry backoffs when the run timed out, so the deep splits are omitted." }] },
    sources,
  );
  assert.equal(metaNarration.unsupported_claims.length, 0);
});

test("flagAcknowledgedByOmissions matches omitted entries to flagged asks", () => {
  const flag = "corner=3PT and abs(x_legacy)>=220 and y_legacy<=92.5";
  assert.equal(flagAcknowledgedByOmissions(flag, ["corner three frequency and legacy coordinates"]), true);
  assert.equal(flagAcknowledgedByOmissions(flag, ["team ranking"]), false);
  assert.equal(flagAcknowledgedByOmissions(flag, []), false);
  assert.equal(flagAcknowledgedByOmissions("HHI of top-8 minutes distribution", ["minutes HHI of the top-8 rotation"]), true);
  assert.equal(flagAcknowledgedByOmissions("season coverage beyond dataset", ["season coverage beyond dataset is missing"]), true);
});

test("missingRequiredTables flags question-named warehouse tables never queried", async () => {
  const { missingRequiredTables } = await import("../dist/verify-answer.js");
  const question = "Use only silver_salaries rows with _season='2026-27' and join silver_cap_players for names.";
  assert.deepEqual(missingRequiredTables(question, new Set(["silver_salaries"])), ["silver_cap_players"]);
  assert.deepEqual(missingRequiredTables(question, new Set(["silver_salaries", "silver_cap_players"])), []);
  assert.deepEqual(missingRequiredTables("Who led MEM in scoring?", new Set()), []);
  assert.deepEqual(missingRequiredTables(undefined, new Set()), []);
  assert.deepEqual(
    missingRequiredTables("Filter silver_boxscores on SILVER_TEAM_IDS.", new Set()),
    ["silver_boxscores", "silver_team_ids"],
  );
});
test("wrapBridgeTools appends a pool fan-out hint on the 3rd distinct player of one tool, once", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-pool-fanout-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let execCount = 0;
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    turn++;
    let msg;
    if (turn === 1) {
      const code = `
        const r1 = await tools.get_zone_deltas({ player: "Player A" });
        const r2 = await tools.get_zone_deltas({ player: "Player B" });
        const r3 = await tools.get_zone_deltas({ player: "Player C", season: "2024-25" });
        const r4 = await tools.get_zone_deltas({ player: "Player D" });
        const r5 = await tools.get_zone_deltas({ player: "Player A" });
        return { r1, r2, r3, r4, r5 };
      `;
      msg = {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "toolCall", id: "call-pool", name: "codemode", arguments: { code } }],
        stopReason: "toolUse", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    } else {
      msg = {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "text", text: "Done." }],
        stopReason: "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    }
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  const mockBridge = {
    tools: [
      {
        name: "get_zone_deltas",
        label: "get_zone_deltas",
        description: "One player's zone deltas",
        parameters: Type.Object({ player: Type.String() }),
        async execute(callId) {
          execCount++;
          const ref = `src-zone-${execCount}`;
          const payload = { rows: [{ zone: "rim", delta: 2.1 }] };
          const record = {
            ref, callId, tool: "get_zone_deltas",
            response: {
              content: [{ type: "text", text: JSON.stringify(payload) }],
              structuredContent: payload, isError: false,
            },
          };
          resultsMap.set(ref, record);
          return {
            content: [], details: undefined,
            structuredContent: { ref, tool: "get_zone_deltas", result: payload, isError: false },
            isError: false,
          };
        },
      },
    ],
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
      q: "Rank the pool", history: [], model: "fixture:fixture",
      cwd, agentDir, bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    assert.equal(execCount, 4);
    const steers = events.filter((e) => e.type === "tool_result" && e.name === "pool_fanout_steer");
    assert.equal(steers.length, 1, "steer fires once per tool");
    const zoneCall = events.find((e) => e.type === "tool_call" && e.name === "pool_fanout_steer");
    assert.deepEqual(zoneCall?.args, { tool: "get_zone_deltas", players: 3 });
    const sources = events.filter((e) => e.type === "source");
    const hinted = sources.filter(
      (e) => typeof e.record.response?.content?.[0]?.text === "string" &&
        e.record.response.content[0].text.includes("pool enumeration"),
    );
    assert.equal(hinted.length, 0, "hint lives on the codemode tool result content, not the source card");
    const resultEvents = events.filter((e) => e.type === "tool_result" && e.name === "get_zone_deltas");
    assert.equal(resultEvents.length, 5);
    assert.ok(resultEvents.every((e) => e.status === "ok"), "steer never blocks the call");
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("wrapBridgeTools appends a pool fan-out hint on the 3rd distinct team for lineup tools, once", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-lineup-pool-fanout-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let execCount = 0;
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    turn++;
    let msg;
    if (turn === 1) {
      const code = `
        const r1 = await tools.get_lineup_stats({ team: "BOS" });
        const r2 = await tools.get_lineup_stats({ team: "NYK", season: "2024-25" });
        const r3 = await tools.get_lineup_stats({ team: "MEM" });
        const r4 = await tools.get_lineup_stats({ team: "DEN" });
        const r5 = await tools.get_lineup_stats({ team: "BOS" });
        return { r1, r2, r3, r4, r5 };
      `;
      msg = {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "toolCall", id: "call-lineup-pool", name: "codemode", arguments: { code } }],
        stopReason: "toolUse", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    } else {
      msg = {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "text", text: "Done." }],
        stopReason: "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    }
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  const mockBridge = {
    tools: [
      {
        name: "get_lineup_stats",
        label: "get_lineup_stats",
        description: "One team's lineup stats",
        parameters: Type.Object({ team: Type.String(), season: Type.Optional(Type.String()) }),
        async execute(callId) {
          execCount++;
          const ref = `src-lineup-${execCount}`;
          const payload = { rows: [{ group_name: "five" }] };
          const record = {
            ref, callId, tool: "get_lineup_stats",
            response: {
              content: [{ type: "text", text: JSON.stringify(payload) }],
              structuredContent: payload, isError: false,
            },
          };
          resultsMap.set(ref, record);
          return {
            content: [], details: undefined,
            structuredContent: { ref, tool: "get_lineup_stats", result: payload, isError: false },
            isError: false,
          };
        },
      },
    ],
    results: resultsMap,
    pid: 1004,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  try {
    const events = [];
    for await (const event of pi.stream({
      q: "Best five-man units in the league", history: [], model: "fixture:fixture",
      cwd, agentDir, bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    assert.equal(execCount, 4);
    const steers = events.filter((e) => e.type === "tool_result" && e.name === "pool_fanout_steer");
    assert.equal(steers.length, 1, "steer fires once per tool");
    const steerCall = events.find((e) => e.type === "tool_call" && e.name === "pool_fanout_steer");
    assert.deepEqual(steerCall?.args, { tool: "get_lineup_stats", teams: 3 });
    const resultEvents = events.filter((e) => e.type === "tool_result" && e.name === "get_lineup_stats");
    assert.equal(resultEvents.length, 5);
    assert.ok(resultEvents.every((e) => e.status === "ok"), "steer never blocks the call");
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("wrapBridgeTools does not steer a lineup tool used for one team's variants", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-lineup-single-team-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let execCount = 0;
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model, context) => {
    turn++;
    let msg;
    if (turn === 1) {
      const code = `
        const r1 = await tools.get_lineup_stats({ team: "DEN", season: "2024-25" });
        const r2 = await tools.get_lineup_stats({ team: "DEN", season: "2023-24" });
        const r3 = await tools.get_lineup_stats({ team: "DEN" });
        return { r1, r2, r3 };
      `;
      msg = {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "toolCall", id: "call-lineup-one-team", name: "codemode", arguments: { code } }],
        stopReason: "toolUse", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    } else {
      msg = {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "text", text: "Done." }],
        stopReason: "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    }
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  const mockBridge = {
    tools: [
      {
        name: "get_lineup_stats",
        label: "get_lineup_stats",
        description: "One team's lineup stats",
        parameters: Type.Object({ team: Type.String(), season: Type.Optional(Type.String()) }),
        async execute(callId) {
          execCount++;
          const ref = `src-lineup-1t-${execCount}`;
          const payload = { rows: [{ group_name: "five" }] };
          const record = {
            ref, callId, tool: "get_lineup_stats",
            response: {
              content: [{ type: "text", text: JSON.stringify(payload) }],
              structuredContent: payload, isError: false,
            },
          };
          resultsMap.set(ref, record);
          return {
            content: [], details: undefined,
            structuredContent: { ref, tool: "get_lineup_stats", result: payload, isError: false },
            isError: false,
          };
        },
      },
    ],
    results: resultsMap,
    pid: 1005,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  try {
    const events = [];
    for await (const event of pi.stream({
      q: "Denver's best lineup vs their most-used one", history: [], model: "fixture:fixture",
      cwd, agentDir, bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    assert.equal(execCount, 3);
    const steers = events.filter((e) => e.type === "tool_result" && e.name === "pool_fanout_steer");
    assert.equal(steers.length, 0, "no steer for one team's repeated lookups");
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});
test("cap-ask web_search gets one warehouse steer, never blocks the call", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-cap-steer-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let execCount = 0;
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    const code = `await tools.web_search({ q: "nba salary cap rules ${turn}" })`;
    const msg = turn < 3
      ? {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "toolCall", id: `call-web-${turn}`, name: "codemode", arguments: { code } }],
        stopReason: "toolUse", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      }
      : {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "text", text: "Done." }], stopReason: "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  const webTool = {
    name: "web_search", label: "web_search", description: "search the web",
    parameters: Type.Object({ q: Type.String() }),
    async execute(callId) {
      execCount++;
      const ref = `src-web-${execCount}`;
      const payload = { rows: [{ title: "hit" }] };
      resultsMap.set(ref, { ref, callId, tool: "web_search", response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: false } });
      return { content: [], details: undefined, structuredContent: { ref, tool: "web_search", result: payload, isError: false }, isError: false };
    },
  };
  const mockBridge = { tools: [webTool], results: resultsMap, pid: 1004, close: async () => {} };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });
  try {
    const events = [];
    for await (const event of pi.stream({ q: "Is this trade legal under the first apron matching bands?", history: [], model: "fixture:fixture", cwd, agentDir, bridge: { python: "fake", cwd, env: {} } }))
      events.push(event);
    assert.equal(execCount, 2);
    const steers = events.filter((e) => e.type === "tool_result" && e.name === "cap_warehouse_steer");
    assert.equal(steers.length, 1, "steer fires once per run");
    const webResults = events.filter((e) => e.type === "tool_result" && e.name === "web_search");
    assert.equal(webResults.length, 2);
    assert.ok(webResults.every((e) => e.status === "ok"), "steer never blocks the call");
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("cap-ask does not steer web calls on non-cap questions", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-cap-steer-off-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let execCount = 0;
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    const msg = turn === 1
      ? {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "toolCall", id: "call-web", name: "codemode", arguments: { code: 'await tools.web_search({ q: "nba news" })' } }],
        stopReason: "toolUse", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      }
      : {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "text", text: "Done." }], stopReason: "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  const webTool = {
    name: "web_search", label: "web_search", description: "search the web",
    parameters: Type.Object({ q: Type.String() }),
    async execute(callId) {
      execCount++;
      const ref = `src-web-${execCount}`;
      const payload = { rows: [{ title: "hit" }] };
      resultsMap.set(ref, { ref, callId, tool: "web_search", response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: false } });
      return { content: [], details: undefined, structuredContent: { ref, tool: "web_search", result: payload, isError: false }, isError: false };
    },
  };
  const mockBridge = { tools: [webTool], results: resultsMap, pid: 1005, close: async () => {} };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });
  try {
    const events = [];
    for await (const event of pi.stream({ q: "What did the coach say about the rotation?", history: [], model: "fixture:fixture", cwd, agentDir, bridge: { python: "fake", cwd, env: {} } }))
      events.push(event);
    assert.equal(execCount, 1);
    assert.equal(events.filter((e) => e.name === "cap_warehouse_steer").length, 0, "no steer on non-cap asks");
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("wrapBridgeTools steers a failed named data tool to sql_exec once per tool", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-named-steer-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    const msg = turn === 1
      ? {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "toolCall", id: "call-mix", name: "codemode", arguments: { code: `
          const r1 = await tools.get_raptor_history({ player: "Player A" });
          const r2 = await tools.get_raptor_history({ player: "Player B" });
          const r3 = await tools.sql_exec({ sql: "SELECT 1" });
          const r4 = await tools.web_search({ q: "nba" });
          return { r1, r2, r3, r4 };
        ` } }],
        stopReason: "toolUse", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      }
      : {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "text", text: "Done." }], stopReason: "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  let execCount = 0;
  const failingTool = (name) => ({
    name, label: name, description: name,
    parameters: Type.Object({}),
    async execute(callId) {
      execCount++;
      const ref = `src-${name}-${execCount}`;
      const payload = { ok: false, error: `no coverage in ${name}` };
      resultsMap.set(ref, { ref, callId, tool: name, response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: true } });
      return { content: [], details: undefined, structuredContent: { ref, tool: name, result: payload, isError: true }, isError: true };
    },
  });
  const mockBridge = {
    tools: [failingTool("get_raptor_history"), failingTool("sql_exec"), failingTool("web_search")],
    results: resultsMap, pid: 1006, close: async () => {},
  };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });
  try {
    const events = [];
    for await (const event of pi.stream({ q: "Project this player's role", history: [], model: "fixture:fixture", cwd, agentDir, bridge: { python: "fake", cwd, env: {} } }))
      events.push(event);
    const steers = events.filter((e) => e.type === "tool_result" && e.name === "named_tool_sql_steer");
    assert.equal(steers.length, 1, "steer fires once per tool, never for sql_exec/web tools");
    const steerCall = events.find((e) => e.type === "tool_call" && e.name === "named_tool_sql_steer");
    assert.equal(steerCall?.args?.tool, "get_raptor_history");
    assert.equal(steerCall?.args?.reason, "failed");
    const raptorResults = events.filter((e) => e.type === "tool_result" && e.name === "get_raptor_history");
    assert.ok(raptorResults.every((e) => e.status === "fail"), "steer never masks the failure");
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("wrapBridgeTools steers a zero-row named tool result to sql_exec once", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-named-steer-rows-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    const msg = turn === 1
      ? {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "toolCall", id: "call-empty", name: "codemode", arguments: { code: `
          const r1 = await tools.get_leaders({ stat: "pie" });
          const r2 = await tools.get_leaders({ stat: "pie" });
          return { r1, r2 };
        ` } }],
        stopReason: "toolUse", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      }
      : {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "text", text: "Done." }], stopReason: "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  let execCount = 0;
  const emptyTool = {
    name: "get_leaders", label: "get_leaders", description: "league leaders",
    parameters: Type.Object({ stat: Type.String() }),
    async execute(callId) {
      execCount++;
      const ref = `src-leaders-${execCount}`;
      const payload = { rows: [] };
      resultsMap.set(ref, { ref, callId, tool: "get_leaders", response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: false } });
      return { content: [], details: undefined, structuredContent: { ref, tool: "get_leaders", result: payload, isError: false }, isError: false };
    },
  };
  const mockBridge = { tools: [emptyTool], results: resultsMap, pid: 1007, close: async () => {} };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });
  try {
    const events = [];
    for await (const event of pi.stream({ q: "Rank the pool", history: [], model: "fixture:fixture", cwd, agentDir, bridge: { python: "fake", cwd, env: {} } }))
      events.push(event);
    const steers = events.filter((e) => e.type === "tool_result" && e.name === "named_tool_sql_steer");
    assert.equal(steers.length, 1, "zero-row steer fires once even on repeat empty results");
    const steerCall = events.find((e) => e.type === "tool_call" && e.name === "named_tool_sql_steer");
    assert.equal(steerCall?.args?.reason, "no_rows");
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("wrapBridgeTools runs a bounded warehouse fallback when a mapped named tool fails", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-named-fallback-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    const msg = turn === 1
      ? {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "toolCall", id: "call-fb", name: "codemode", arguments: { code: `
          const r1 = await tools.get_scouting_report({ player_name: "Jalen Williams", season: "2024-25" });
          return { r1 };
        ` } }],
        stopReason: "toolUse", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      }
      : {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "text", text: "Done." }], stopReason: "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
    stream.end();
    return stream;
  });

  const resultsMap = new Map();
  let execCount = 0;
  const sqlCalls = [];
  const failingScout = {
    name: "get_scouting_report", label: "get_scouting_report", description: "get_scouting_report",
    parameters: Type.Object({}),
    async execute(callId) {
      execCount++;
      const ref = `src-scout-${execCount}`;
      const payload = { ok: false, error: "invalid team_id" };
      resultsMap.set(ref, { ref, callId, tool: "get_scouting_report", response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: true } });
      return { content: [], details: undefined, structuredContent: { ref, tool: "get_scouting_report", result: payload, isError: true }, isError: true };
    },
  };
  const sqlExec = {
    name: "sql_exec", label: "sql_exec", description: "sql_exec",
    parameters: Type.Object({}),
    async execute(callId, args) {
      sqlCalls.push(args.sql);
      const ref = `src-sql-${execCount}`;
      const payload = { ok: true, rows: [{ player_name: "Jalen Williams", season: "2024-25", pts: 21.6, ts_pct: 0.607 }] };
      resultsMap.set(ref, { ref, callId, tool: "sql_exec", response: { content: [{ type: "text", text: JSON.stringify(payload) }], structuredContent: payload, isError: false } });
      return { content: [], details: undefined, structuredContent: { ref, tool: "sql_exec", result: payload, isError: false }, isError: false };
    },
  };
  const mockBridge = { tools: [failingScout, sqlExec], results: resultsMap, pid: 1007, close: async () => {} };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });
  try {
    const events = [];
    for await (const event of pi.stream({ q: "Scout Jalen Williams", history: [], model: "fixture:fixture", cwd, agentDir, bridge: { python: "fake", cwd, env: {} } }))
      events.push(event);
    assert.equal(sqlCalls.length, 1, "one bounded fallback query ran");
    assert.match(sqlCalls[0], /silver_hist_player_seasons/);
    assert.match(sqlCalls[0], /player_name ILIKE '%Jalen Williams%'/);
    assert.match(sqlCalls[0], /season = 2025/);
    assert.match(sqlCalls[0], /LIMIT 25/);
    const fbResult = events.find((e) => e.type === "tool_result" && e.name === "named_tool_sql_fallback");
    assert.equal(fbResult?.status, "ok");
    const steerCall = events.find((e) => e.type === "tool_call" && e.name === "named_tool_sql_steer");
    assert.equal(steerCall?.args?.fallback, true);
  }
  finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("guard chain replays dab-v1-188 lineup enumeration: steered once, then churn-stopped", async () => {
  const trace = JSON.parse(
    await readFile(join(import.meta.dirname, "fixtures", "dab-v1-188-lineup-teams.json"), "utf8")
  );
  const cwd = await mkdtemp(join(tmpdir(), "dime-replay-188-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let seqIdx = 0;
  let turn = 0;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    if (seqIdx < trace.length) {
      const team = trace[seqIdx++];
      const code = `return await tools.get_lineup_stats({ season: "2024-25", team: ${JSON.stringify(team)} });`;
      const msg = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        content: [
          { type: "toolCall", id: `replay-${turn}`, name: "codemode", arguments: { code } },
        ],
        stopReason: "toolUse",
        timestamp: Date.now(),
        usage: {
          input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: "toolUse", message: msg });
      stream.end();
      return stream;
    }
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content: [{ type: "text", text: "done without submit" }],
      stopReason: "stop",
      timestamp: Date.now(),
      usage: {
        input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
      },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: "stop", message: msg });
    stream.end();
    return stream;
  });

  let execCount = 0;
  const resultsMap = new Map();
  const mockBridge = {
    tools: [
      {
        name: "get_lineup_stats",
        label: "get_lineup_stats",
        description: "Lineup stats",
        parameters: Type.Object({}),
        async execute(callId) {
          execCount++;
          const ref = `src-lineup-${execCount}`;
          const payload = { rows: [{ lineup: "A B C D E", net_rating: 4.2 }] };
          const record = {
            ref,
            callId,
            tool: "get_lineup_stats",
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
            structuredContent: { ref, tool: "get_lineup_stats", result: payload, isError: false },
            isError: false,
          };
        },
      },
    ],
    results: resultsMap,
    pid: 1005,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  process.env.DIME_CALL_CEILING_WARN = "30";
  process.env.DIME_CALL_CEILING_STOP = "60";
  try {
    const events = [];
    for await (const event of pi.stream({
      q: "Best 5-man lineup for every team",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    const steers = events.filter(
      (e) => e.type === "tool_call" && e.name === "pool_fanout_steer"
    );
    assert.equal(steers.length, 1, "lineup pool fan-out steer should fire exactly once");
    assert.deepEqual(steers[0].args, { tool: "get_lineup_stats", teams: 3 });
    const stopSource = events.find(
      (e) => e.type === "source" && e.record.ref.startsWith("churn_stop_")
    );
    assert.ok(stopSource, "churn-stop source record should be emitted");
    assert.equal(stopSource.record.response.structuredContent.stop_reason, "tool_call_churn");
    const failure = events.find((e) => e.type === "failure");
    assert.ok(failure, "run should terminate with a failure event");
    assert.ok(
      seqIdx < trace.length,
      `run must terminate mid-trace (consumed ${seqIdx}/${trace.length}), not dither to the end`
    );
  } finally {
    delete process.env.DIME_CALL_CEILING_WARN;
    delete process.env.DIME_CALL_CEILING_STOP;
    await rm(cwd, { recursive: true, force: true });
  }
});

test("guard chain does not steer or stop same-team lineup volume (dab-v1-189 control)", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "dime-replay-189-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  let seqIdx = 0;
  let turn = 0;
  const N = 20;
  const runtime = await makeFixtureRuntime(agentDir, (model) => {
    turn++;
    if (seqIdx < N) {
      seqIdx++;
      const code = `return await tools.get_lineup_stats({ season: "2024-25", team: "DEN", opponent: "OPP${seqIdx}" });`;
      const msg = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        content: [
          { type: "toolCall", id: `ctrl-${turn}`, name: "codemode", arguments: { code } },
        ],
        stopReason: "toolUse",
        timestamp: Date.now(),
        usage: {
          input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: "toolUse", message: msg });
      stream.end();
      return stream;
    }
    const msg = {
      role: "assistant",
      api: model.api,
      provider: model.provider,
      model: model.id,
      content: [{ type: "text", text: "final answer" }],
      stopReason: "stop",
      timestamp: Date.now(),
      usage: {
        input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
      },
    };
    const stream = createAssistantMessageEventStream();
    stream.push({ type: "done", reason: "stop", message: msg });
    stream.end();
    return stream;
  });

  let execCount = 0;
  const resultsMap = new Map();
  const mockBridge = {
    tools: [
      {
        name: "get_lineup_stats",
        label: "get_lineup_stats",
        description: "Lineup stats",
        parameters: Type.Object({}),
        async execute(callId) {
          execCount++;
          const ref = `src-ctrl-${execCount}`;
          const payload = { rows: [{ lineup: "A B C D E", net_rating: 4.2 }] };
          const record = {
            ref,
            callId,
            tool: "get_lineup_stats",
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
            structuredContent: { ref, tool: "get_lineup_stats", result: payload, isError: false },
            isError: false,
          };
        },
      },
    ],
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
      q: "DEN rotation deep dive",
      history: [],
      model: "fixture:fixture",
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    assert.equal(execCount, N);
    assert.equal(
      events.filter((e) => e.type === "tool_call" && e.name === "pool_fanout_steer").length,
      0,
      "same-team calls must never trip the fan-out steer"
    );
    assert.equal(
      events.findIndex((e) => e.type === "source" && e.record.ref.startsWith("churn_stop_")),
      -1,
      "same-team volume must not hit the churn stop"
    );
  } finally {
    await rm(cwd, { recursive: true, force: true });
  }
});

test("generated tool manifest stays in sync with tools/manifest.json", async () => {
  const manifestUrl = new URL("../tools/manifest.json", import.meta.url);
  const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  const manifestNames = manifest.tools.map((tool) => tool.name);
  assert.deepEqual([...ANALYST_TOOL_NAMES], manifestNames);
  const manifestNamespaces = Object.keys(manifest.namespaces);
  for (const tool of manifest.tools) {
    assert.ok(
      tool.namespace === undefined || manifestNamespaces.includes(tool.namespace),
      `${tool.name} namespace`
    );
    if (tool.live_only_fallback) {
      assert.ok(manifestNames.includes(tool.live_only_fallback), `${tool.name} fallback`);
    }
  }
  const manifestGuidelines = Object.fromEntries(
    manifest.tools.filter((tool) => tool.guidelines).map((tool) => [tool.name, tool.guidelines])
  );
  assert.deepEqual(TOOL_PROMPT_GUIDELINES, manifestGuidelines);
});

test("composition gate: procrastinator shape — directive fires, 3 data calls pass, 4th blocked, submit lifts permanently", async () => {
  const { createCompositionGate } = await import("../dist/pi-execution.js");
  const gate = createCompositionGate();
  gate.noteEvidence();
  assert.equal(gate.fireDirective(), true);
  assert.equal(gate.recordDataCall(), "allow");
  assert.equal(gate.recordDataCall(), "allow");
  assert.equal(gate.recordDataCall(), "allow");
  assert.equal(gate.recordDataCall(), "block");
  assert.equal(gate.recordDataCall(), "block");
  gate.recordSubmitAttempt();
  assert.equal(gate.recordDataCall(), "allow");
  assert.equal(gate.lifted, true);
});

test("composition gate: control shape — early submit attempt means the gate never blocks late data work", async () => {
  const { createCompositionGate } = await import("../dist/pi-execution.js");
  const gate = createCompositionGate();
  gate.noteEvidence();
  gate.recordSubmitAttempt();
  assert.equal(gate.fireDirective(), false);
  for (let i = 0; i < 12; i++)
    assert.equal(gate.recordDataCall(), "allow");
});

test("composition gate: median path — submission before the directive window keeps data tools open throughout", async () => {
  const { createCompositionGate } = await import("../dist/pi-execution.js");
  const gate = createCompositionGate();
  gate.noteEvidence();
  assert.equal(gate.recordDataCall(), "allow");
  gate.recordSubmitAttempt();
  assert.equal(gate.fireDirective(), false);
  assert.equal(gate.recordDataCall(), "allow");
});

test("composition gate: zero-evidence dormancy — no row-bearing result means the directive never fires", async () => {
  const { createCompositionGate } = await import("../dist/pi-execution.js");
  const gate = createCompositionGate();
  assert.equal(gate.fireDirective(), false);
  for (let i = 0; i < 10; i++)
    assert.equal(gate.recordDataCall(), "allow");
  assert.equal(gate.directiveFired, false);
});

test("composition gate: directive is one-shot even if ignored", async () => {
  const { createCompositionGate } = await import("../dist/pi-execution.js");
  const gate = createCompositionGate();
  gate.noteEvidence();
  assert.equal(gate.fireDirective(), true);
  assert.equal(gate.fireDirective(), false);
});

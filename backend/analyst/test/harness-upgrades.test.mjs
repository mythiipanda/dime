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

function makeSourceRecord(ref, { rows = [], isError = false, error } = {}) {
  const result = error !== undefined ? { rows, error } : { rows };
  return {
    ref,
    callId: "call-" + ref,
    tool: "sql_exec",
    response: {
      content: [{ type: "text", text: JSON.stringify(result) }],
      structuredContent: result,
      isError,
    },
  };
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

async function contextsForHistory(compat) {
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
      history: [{ role: "user", content: "Who led the league in points?" }, { role: "assistant", content: "Luka Doncic at 33.5 PPG." }],
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
  assert.equal(messages.filter((m) => m.role === "assistant").length, 1);
});

test("history replays as one transcript when the model requires prior reasoning", async () => {
  const messages = await contextsForHistory({ requiresReasoningContentOnAssistantMessages: true });
  assert.equal(messages.filter((m) => m.role === "assistant").length, 0);
  const transcript = messages.find((m) => m.role === "user" && typeof m.content === "string" && m.content.includes("Analyst: Luka Doncic at 33.5 PPG."));
  assert.ok(transcript);
  assert.ok(transcript.content.includes("User: Who led the league in points?"));
});

test("pi execution stream ends after abort even when the run never settles", async () => {
  const pi = createPiExecution({
    resolveRuntime: () => new Promise(() => {}),
    connectTools: async () => ({ tools: [], results: new Map(), pid: 1, close: async () => {} }),
    abortGraceMs: 50,
  });
  const controller = new AbortController();
  setTimeout(() => controller.abort(), 20);
  const events = [];
  for await (const event of pi.stream({ q: "hang", history: [], model: "fixture:fixture", cwd: tmpdir(), agentDir: tmpdir(), bridge: { python: "fake", cwd: tmpdir(), env: {} } }, controller.signal))
    events.push(event);
  assert.equal(events.some((e) => e.type === "answer"), false);
});

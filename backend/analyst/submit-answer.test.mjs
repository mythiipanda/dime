import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  validateAnswerSubmission,
  createSubmitAnswerTool,
} from "./dist/submit-tool.js";
import { ProductStore } from "./dist/product-store.js";
import { Type } from "typebox";
import { mkdir, writeFile } from "node:fs/promises";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";
import { createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import { createAnalystSession } from "./dist/runtime.js";
import { createPiExecution } from "./dist/pi-execution.js";
import { createAnalyst } from "./dist/analyst.js";
import { priorSourceTool } from "./dist/pi-context.js";

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

test("validateAnswerSubmission accepts valid blocks and anchors", () => {
  const sources = new Map([
    ["src-1", makeSourceRecord("src-1", { rows: [{ player: "Luka Doncic", pts: 33.9 }, { player: "SGA", pts: 30.1 }] })],
    ["src-2", makeSourceRecord("src-2", { rows: [{ team: "DAL", pace: 100.5 }] })],
  ]);

  const submission = {
    blocks: [
      {
        text: "Luka Doncic led the league in scoring.",
        anchors: [{ ref: "src-1", row: 0, columns: ["player", "pts"] }],
      },
      {
        text: "Dallas played at a 100.5 pace.",
        anchors: [{ ref: "src-2", row: 0, columns: ["team", "pace"] }],
      },
    ],
  };

  const validated = validateAnswerSubmission(submission, ref => sources.get(ref));
  assert.equal(validated.blocks.length, 2);
  assert.equal(validated.blocks[0].text, "Luka Doncic led the league in scoring.");
  assert.equal(validated.blocks[0].anchors[0].ref, "src-1");
  assert.equal(validated.blocks[0].anchors[0].row, 0);
  assert.deepEqual(validated.blocks[0].anchors[0].columns, ["player", "pts"]);
});

test("validateAnswerSubmission allows blocks without anchors", () => {
  const sources = new Map();
  const submission = {
    blocks: [
      { text: "Introductory context without anchors.", anchors: [] },
    ],
  };
  const validated = validateAnswerSubmission(submission, ref => sources.get(ref));
  assert.equal(validated.blocks.length, 1);
  assert.equal(validated.blocks[0].anchors.length, 0);
});

test("validateAnswerSubmission rejects non-existent source ref", () => {
  const sources = new Map();
  const submission = {
    blocks: [
      {
        text: "Claim with missing source.",
        anchors: [{ ref: "missing-ref", row: 0, columns: ["col"] }],
      },
    ],
  };
  assert.throws(
    () => validateAnswerSubmission(submission, ref => sources.get(ref)),
    /Unknown source ref: missing-ref/
  );
});

test("validateAnswerSubmission rejects error source ref", () => {
  const sources = new Map([
    ["err-1", makeSourceRecord("err-1", { isError: true, error: "Syntax error" })],
  ]);
  const submission = {
    blocks: [
      {
        text: "Claim referencing failed query.",
        anchors: [{ ref: "err-1", row: 0, columns: ["col"] }],
      },
    ],
  };
  assert.throws(
    () => validateAnswerSubmission(submission, ref => sources.get(ref)),
    /Source ref is an error result: err-1/
  );
});

test("validateAnswerSubmission rejects row index out of bounds", () => {
  const sources = new Map([
    ["src-1", makeSourceRecord("src-1", { rows: [{ id: 1 }] })],
  ]);
  const submission = {
    blocks: [
      {
        text: "Claim referencing row 5.",
        anchors: [{ ref: "src-1", row: 5, columns: ["id"] }],
      },
    ],
  };
  assert.throws(
    () => validateAnswerSubmission(submission, ref => sources.get(ref)),
    /out of bounds \(length: 1\) for ref: src-1/
  );
});

test("validateAnswerSubmission rejects column that does not exist on row", () => {
  const sources = new Map([
    ["src-1", makeSourceRecord("src-1", { rows: [{ player: "Luka", pts: 33.9 }] })],
  ]);
  const submission = {
    blocks: [
      {
        text: "Claim referencing non-existent column.",
        anchors: [{ ref: "src-1", row: 0, columns: ["player", "rebounds"] }],
      },
    ],
  };
  assert.throws(
    () => validateAnswerSubmission(submission, ref => sources.get(ref)),
    /Column 'rebounds' does not exist on row 0 for ref: src-1/
  );
});

test("validateAnswerSubmission rejects empty blocks or empty text", () => {
  const sources = new Map();
  assert.throws(
    () => validateAnswerSubmission({ blocks: [] }, ref => sources.get(ref)),
    /Invalid answer submission schema/
  );
  assert.throws(
    () => validateAnswerSubmission({ blocks: [{ text: "", anchors: [] }] }, ref => sources.get(ref)),
    /Invalid answer submission schema/
  );
});

test("createSubmitAnswerTool executes and calls onAccept", async () => {
  const source = makeSourceRecord("src-1", { rows: [{ stat: "reb", value: 10 }] });
  let accepted = null;
  const tool = createSubmitAnswerTool(
    () => [source],
    sub => { accepted = sub; }
  );

  const submission = {
    blocks: [
      { text: "10 rebounds recorded.", anchors: [{ ref: "src-1", row: 0, columns: ["stat", "value"] }] },
    ],
  };

  const result = await tool.execute("call-1", submission);
  assert.equal(accepted?.blocks.length, 1);
  assert.equal(accepted.blocks[0].text, "10 rebounds recorded.");
  assert.deepEqual(result.content, [{ type: "text", text: "Answer submitted with 1 block(s)." }]);
  assert.equal(result.details, undefined);
});

test("ProductStore persists and reads submission in pi-sources artifact", async () => {
  const tempDir = await mkdtemp(join(tmpdir(), "dime-r625-test-"));
  try {
    const dbPath = join(tempDir, "conversations.sqlite3");
    const sourcesDir = join(tempDir, "sources");
    const store = new ProductStore(dbPath, sourcesDir);

    const runId = "run-" + "a".repeat(32);
    const source = makeSourceRecord("src-test", { rows: [{ val: 42 }] });
    const submission = {
      blocks: [
        { text: "The answer is 42.", anchors: [{ ref: "src-test", row: 0, columns: ["val"] }] },
      ],
    };

    store.saveSources(runId, [source], [source], submission);

    const identity = { owner: "user-1", thread: "thread-1" };
    store.append(identity, "What is the answer?", "The answer is 42.", runId);

    const read = store.readSources(identity, runId);
    assert.equal(read.run_id, runId);
    assert.equal(read.sources.length, 1);
    assert.equal(read.sources[0].ref, "src-test");
    assert.deepEqual(read.submission, submission);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
});

test("ProductStore backward compatibility reads legacy artifact without submission", async () => {
  const dir = await mkdtemp(join(tmpdir(), "store-backcompat-"));
  try {
    const dbPath = join(dir, "conversations.sqlite3");
    const sourcesDir = join(dir, "sources");
    await mkdir(sourcesDir, { recursive: true });

    const store = new ProductStore(dbPath, sourcesDir);

    const runId = "run-" + "b".repeat(32);
    const legacyArtifact = {
      run_id: runId,
      source_refs: ["legacy-ref-1"],
      sources: [
        {
          ref: "legacy-ref-1",
          callId: "call-1",
          tool: "sql_exec",
          response: {
            content: [{ type: "text", text: JSON.stringify({ rows: [{ val: 123 }] }) }],
            structuredContent: { rows: [{ val: 123 }] },
            isError: false,
          },
        },
      ],
    };

    // Write legacy JSON without submission
    await writeFile(join(sourcesDir, `${runId}.json`), JSON.stringify(legacyArtifact), "utf-8");

    const identity = { owner: "test-owner", thread: "thread-1" };
    store.append(identity, "Legacy question?", "Legacy answer.", runId);

    // Read through store
    const loaded = store.readSources(identity, runId);
    assert.equal(loaded.run_id, runId);
    assert.equal(loaded.sources.length, 1);
    assert.equal(loaded.sources[0].ref, "legacy-ref-1");
    assert.equal(loaded.submission, undefined);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("ProductStore enforces owner and thread isolation on readSources", async () => {
  const dir = await mkdtemp(join(tmpdir(), "store-isolation-"));
  try {
    const dbPath = join(dir, "conversations.sqlite3");
    const sourcesDir = join(dir, "sources");
    const store = new ProductStore(dbPath, sourcesDir);

    const runId = "run-" + "c".repeat(32);
    const source = makeSourceRecord("src-1", { rows: [{ pts: 30 }] });
    const submission = {
      blocks: [{ text: "Player scored 30.", anchors: [{ ref: "src-1", row: 0, columns: ["pts"] }] }],
    };

    store.saveSources(runId, [source], [source], submission);

    // Append only under Alice on thread-alpha
    store.append({ owner: "alice", thread: "thread-alpha" }, "Q", "A", runId);

    // Alice on thread-alpha can read
    const readByAlice = store.readSources({ owner: "alice", thread: "thread-alpha" }, runId);
    assert.equal(readByAlice.run_id, runId);
    assert.equal(readByAlice.submission?.blocks[0].text, "Player scored 30.");

    // Bob on thread-alpha cannot read Alice's run
    assert.throws(
      () => store.readSources({ owner: "bob", thread: "thread-alpha" }, runId),
      /Source not found/
    );

    // Alice on thread-beta cannot read thread-alpha run
    assert.throws(
      () => store.readSources({ owner: "alice", thread: "thread-beta" }, runId),
      /Source not found/
    );
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

test("Pi session fixture validates current and prior refs, rejects invalid selectors, and permits revision", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-session-fixture-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const currentRecord = makeSourceRecord("current", { rows: [{ pts_total: 2484, gp_total: 76 }] });
  const priorRecord = makeSourceRecord("prior-owned", { rows: [{ PPG: 32.7, TS_PCT: 0.637 }] });
  const failedRecord = makeSourceRecord("failed", { isError: true, error: "table not found" });

  const sourcesMap = new Map([
    ["current", currentRecord],
    ["prior-owned", priorRecord],
    ["failed", failedRecord],
  ]);

  let submitted;
  const accepted = [];
  const rejected = [];

  const submitTool = createSubmitAnswerTool(
    () => Array.from(sourcesMap.values()),
    (sub) => {
      submitted = structuredClone(sub);
      accepted.push(submitted);
    }
  );

  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });

  const requests = [];
  const code = `
    const invalid = [
      { ref: "unknown", row: 0, columns: ["pts_total"] },
      { ref: "failed", row: 0, columns: ["pts_total"] },
      { ref: "current", row: 99, columns: ["pts_total"] },
      { ref: "current", row: 0, columns: ["missing"] },
      { ref: "current", row: -1, columns: ["pts_total"] }
    ];
    const rejections = [];
    for (const anchor of invalid) {
      try {
        await tools.submit_answer({ blocks: [{ text: "claim", anchors: [anchor] }] });
        rejections.push(false);
      } catch (e) {
        rejections.push(true);
      }
    }
    // Valid selector with false assertion accepted by tool (selectors do not verify truth)
    await tools.submit_answer({
      blocks: [{ text: "He scored 9999 points.", anchors: [{ ref: "current", row: 0, columns: ["pts_total"] }] }]
    });
    // Revision with multiple blocks and current + prior refs
    await tools.submit_answer({
      blocks: [
        { text: "He scored 2484 points in 76 games.", anchors: [{ ref: "current", row: 0, columns: ["pts_total", "gp_total"] }] },
        { text: "He averaged 32.7 points and TS was 0.637.", anchors: [{ ref: "prior-owned", row: 0, columns: ["PPG", "TS_PCT"] }] }
      ]
    });
    return { rejections, done: true };
  `;

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
      },
    ],
    streamSimple(model, context) {
      requests.push(structuredClone(context));
      const first = requests.length === 1;
      const message = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        content: first
          ? [{ type: "toolCall", id: "submit-fixture", name: "codemode", arguments: { code } }]
          : [{ type: "text", text: "Unanchored trailing prose must not replace submitted answer" }],
        stopReason: first ? "toolUse" : "stop",
        timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: message.stopReason, message });
      stream.end();
      return stream;
    },
  });

  const session = await createAnalystSession({
    cwd,
    agentDir,
    model: runtime.getModel("fixture", "fixture"),
    modelRuntime: runtime,
    tools: [submitTool, priorSourceTool([priorRecord])],
  });

  try {
    assert.deepEqual(session.getActiveToolNames(), ["codemode"]);
    assert.deepEqual(session.getCallableToolNames(), ["submit_answer", "read_source"]);

    await session.prompt("Run synthetic submission fixture");
    assert.equal(requests.length, 2);
    assert.equal(accepted.length, 2);
    const secondReq = JSON.stringify(requests[1]);
    assert.ok(secondReq.includes("true,true,true,true,true"));

    // Revision submission is final
    assert.equal(submitted.blocks.length, 2);
    assert.equal(submitted.blocks[0].anchors[0].ref, "current");
    assert.equal(submitted.blocks[1].anchors[0].ref, "prior-owned");
  } finally {
    await session.abort();
    session.dispose();
    await rm(cwd, { recursive: true, force: true });
  }
});

test("createPiExecution canonical text overrides trailing prose, retains sources, and handles fallback", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-exec-fixture-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const currentRecord = makeSourceRecord("src-current", { rows: [{ pts: 33.9, player: "Luka" }] });
  const failedRecord = makeSourceRecord("src-failed", { isError: true, error: "table not found" });

  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });

  let mode = "canonical";
  let execRequests = 0;
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
      },
    ],
    streamSimple(model, context) {
      execRequests++;
      if (mode === "canonical") {
        if (execRequests === 1) {
          const code = `
            await tools.query_tool({ q: "points" });
            await tools.fail_tool({});
            await tools.submit_answer({
              blocks: [
                { text: "Luka led scoring with 33.9 PPG.", anchors: [{ ref: "src-current", row: 0, columns: ["pts", "player"] }] },
                { text: "Conclusion block without anchors.", anchors: [] }
              ]
            });
            return { done: true };
          `;
          const msg = {
            role: "assistant",
            api: model.api,
            provider: model.provider,
            model: model.id,
            content: [{ type: "toolCall", id: "call-1", name: "codemode", arguments: { code } }],
            stopReason: "toolUse",
            timestamp: Date.now(),
            usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
          };
          const stream = createAssistantMessageEventStream();
          stream.push({ type: "done", reason: "toolUse", message: msg });
          stream.end();
          return stream;
        } else {
          // Trailing prose from assistant
          const msg = {
            role: "assistant",
            api: model.api,
            provider: model.provider,
            model: model.id,
            content: [{ type: "text", text: "Trailing model text that MUST be overridden by canonical text." }],
            stopReason: "stop",
            timestamp: Date.now(),
            usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
          };
          const stream = createAssistantMessageEventStream();
          stream.push({ type: "done", reason: "stop", message: msg });
          stream.end();
          return stream;
        }
      } else {
        // Fallback mode: no submit_answer called
        const msg = {
          role: "assistant",
          api: model.api,
          provider: model.provider,
          model: model.id,
          content: [{ type: "text", text: "Plain fallback prose without tool call." }],
          stopReason: "stop",
          timestamp: Date.now(),
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        };
        const stream = createAssistantMessageEventStream();
        stream.push({ type: "done", reason: "stop", message: msg });
        stream.end();
        return stream;
      }
    },
  });

  const mockBridge = {
    tools: [
      {
        name: "query_tool",
        label: "Query Tool",
        description: "Run query",
        parameters: Type.Object({ q: Type.String() }),
        async execute() {
          return {
            content: [{ type: "text", text: JSON.stringify({ rows: [{ pts: 33.9, player: "Luka" }] }) }],
            structuredContent: { ref: "src-current", tool: "query_tool", isError: false, result: { rows: [{ pts: 33.9, player: "Luka" }] } },
          };
        },
      },
      {
        name: "fail_tool",
        label: "Fail Tool",
        description: "Fail query",
        parameters: Type.Object({}),
        async execute() {
          return {
            content: [{ type: "text", text: "table not found" }],
            structuredContent: { ref: "src-failed", tool: "fail_tool", isError: true, result: { error: "table not found" } },
          };
        },
      },
    ],
    results: new Map([
      ["src-current", currentRecord],
      ["src-failed", failedRecord],
    ]),
    pid: 12345,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  // Test 1: Canonical text overrides trailing prose
  const events = [];
  for await (const event of pi.stream({
    q: "Who led scoring?",
    history: [],
    model: "fixture:fixture",
    cwd,
    agentDir,
    bridge: { python: "fake", cwd, env: {} },
  })) {
    events.push(event);
  }

  const answerEvent = events.find((e) => e.type === "answer");
  assert.ok(answerEvent);
  // Canonical text from blocks joined by double newline
  const expectedCanonical = "Luka led scoring with 33.9 PPG.\n\nConclusion block without anchors.";
  assert.equal(answerEvent.text, expectedCanonical);
  assert.notEqual(answerEvent.text, "Trailing model text that MUST be overridden by canonical text.");
  assert.ok(answerEvent.submission);
  assert.equal(answerEvent.submission.blocks.length, 2);

  // Retains source records in emitted events
  const sourceEvents = events.filter((e) => e.type === "source");
  assert.equal(sourceEvents.length, 2);
  assert.ok(sourceEvents.some((e) => e.record.ref === "src-current"));
  assert.ok(sourceEvents.some((e) => e.record.ref === "src-failed"));

  // Test 2: Fallback mode when model does not call submit_answer
  mode = "fallback";
  execRequests = 0;
  const fallbackEvents = [];
  for await (const event of pi.stream({
    q: "Who led scoring?",
    history: [],
    model: "fixture:fixture",
    cwd,
    agentDir,
    bridge: { python: "fake", cwd, env: {} },
  })) {
    fallbackEvents.push(event);
  }

  const fallbackAnswer = fallbackEvents.find((e) => e.type === "answer");
  assert.ok(fallbackAnswer);
  assert.equal(fallbackAnswer.text, "Plain fallback prose without tool call.");
  assert.equal(fallbackAnswer.submission, undefined);

  await rm(cwd, { recursive: true, force: true });
});

test("createAnalyst downstream verification remains unassessed and preserves submission carry", async () => {
  const dir = await mkdtemp(join(tmpdir(), "analyst-downstream-"));
  try {
    const dbPath = join(dir, "conversations.sqlite3");
    const sourcesDir = join(dir, "sources");
    const privateDir = join(dir, "private");
    const warehousePath = join(dir, "warehouse.duckdb");
    const statePath = join(dir, "state.duckdb");
    const store = new ProductStore(dbPath, sourcesDir);

    const testEnv = {
      ...process.env,
      DIME_CONVERSATION_STORE: dbPath,
      DIME_PI_SOURCES_DIR: sourcesDir,
      DIME_PI_PRIVATE_DIR: privateDir,
      DIME_WAREHOUSE: warehousePath,
      DIME_STATE_DB: statePath,
    };

    const submission = {
      blocks: [
        {
          text: "Downstream test statement.",
          anchors: [{ ref: "src-1", row: 0, columns: ["stat"] }],
        },
      ],
    };

    const mockExecute = {
      async *stream() {
        yield {
          type: "source",
          record: makeSourceRecord("src-1", { rows: [{ stat: 42 }] }),
        };
        yield {
          type: "answer",
          text: "Downstream test statement.",
          submission,
        };
        yield { type: "closed" };
      },
    };

    const analyst = createAnalyst({
      env: testEnv,
      resolveModel: () => ({
        id: "fixture",
        name: "Fixture",
        provider: "fixture",
        api: "openai-completions",
        reasoning: false,
        input: ["text"],
        contextWindow: 100000,
        maxTokens: 4000,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      }),
      store,
      execution: mockExecute,
      saveChat: async () => {},
      saveRun: async () => {},
    });

    const observed = [];
    for await (const event of analyst.stream({
      q: "synthetic downstream question",
      thread: "thread-1",
      client: "test-client",
    })) {
      observed.push(event);
    }

    const final = observed.find((e) => e.type === "final_answer");
    assert.ok(final);
    // Unassessed status preserved - truth is not verified
    assert.equal(final.data.carry.verification, "unassessed");
    assert.equal(final.data.carry.answer_status, "unassessed");
    assert.deepEqual(final.data.carry.source_refs, ["src-1"]);
    assert.deepEqual(final.data.carry.submission, submission);

    // Stored sources also include the submission
    const runId = final.data.carry.run_id;
    const loaded = store.readSources({ owner: "test-client", thread: "thread-1" }, runId);
    assert.deepEqual(loaded.submission, submission);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

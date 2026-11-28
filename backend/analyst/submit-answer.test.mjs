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
import { sourceResult } from "./dist/python-tools.js";

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
    assert.deepEqual(session.getActiveToolNames(), ["codemode", "submit_answer", "load_skill"]);
    assert.deepEqual(new Set(session.getCallableToolNames()), new Set(["submit_answer", "read_source", "load_skill"]));

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

test("createPiExecution steers a substantial unsubmitted answer through submit_answer, once", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-turn-end-steer-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });

  const longText = "MEM went 56-26 in the 2021-22 regular season. The early split was 30-10 and the late split 26-16, with the defensive rating tightening after the deadline and the rotation settling. The roster's top-eight minute share concentrated on the closing five.";
  const canonical = "MEM's 2021-22 record: 56-26.";

  let execRequests = 0;
  let submitOnSteer = true;
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
      let msg;
      if (execRequests === 1) {
        msg = {
          role: "assistant",
          api: model.api,
          provider: model.provider,
          model: model.id,
          content: [{ type: "text", text: longText }],
          stopReason: "stop",
          timestamp: Date.now(),
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        };
      } else if (execRequests === 2 && submitOnSteer) {
        const code = `await tools.submit_answer({ blocks: [{ text: ${JSON.stringify(canonical)}, anchors: [] }] }); return { done: true };`;
        msg = {
          role: "assistant",
          api: model.api,
          provider: model.provider,
          model: model.id,
          content: [{ type: "toolCall", id: "call-sub", name: "codemode", arguments: { code } }],
          stopReason: "toolUse",
          timestamp: Date.now(),
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        };
      } else {
        msg = {
          role: "assistant",
          api: model.api,
          provider: model.provider,
          model: model.id,
          content: [{ type: "text", text: submitOnSteer ? "Submitted." : longText }],
          stopReason: "stop",
          timestamp: Date.now(),
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        };
      }
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
      stream.end();
      return stream;
    },
  });

  const mockBridge = {
    tools: [],
    results: new Map(),
    pid: 12345,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  const run = async () => {
    const events = [];
    for await (const event of pi.stream({
      q: "What was MEM's record in 2021-22?",
      history: [],
      model: "fixture:fixture",
      sources: [makeSourceRecord("prior-mem", { rows: [{ team: "MEM", season: "2021-22", wins: 56, losses: 26 }] })],
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
    return events;
  };

  let events = await run();
  assert.equal(execRequests, 3);
  const steerCall = events.find((e) => e.type === "tool_call" && e.name === "turn_end_steer");
  assert.ok(steerCall, "turn_end_steer record should be emitted");
  const answer = events.find((e) => e.type === "answer");
  assert.ok(answer.submission, "answer should carry the submission");
  assert.equal(answer.text, canonical);

  submitOnSteer = false;
  execRequests = 0;
  events = await run();
  assert.equal(execRequests, 3);
  const steers = events.filter((e) => e.type === "tool_call" && e.name === "turn_end_steer");
  assert.equal(steers.length, 1, "steer fires exactly once");
  const giveUps = events.filter((e) => e.type === "tool_call" && e.name === "give_up_correction_steer");
  assert.equal(giveUps.length, 1, "give-up correction fires exactly once");
  const plain = events.find((e) => e.type === "answer");
  assert.equal(plain.submission, undefined);
  assert.equal(plain.text, longText);

  await rm(cwd, { recursive: true, force: true });
});

test("createPiExecution reprompts once when a sourceless data ask ends in plain text with zero data calls", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-zero-evidence-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });

  const longText = "Giannis Antetokounmpo leads the league in restricted-area frequency at 41.2 percent of his shot diet, with Shai Gilgeous-Alexander and Anthony Edwards rounding out the top three on sustained rim pressure across the 2024-25 season, while Denver's Nikola Jokic trails the group on lower drive volume.";
  const canonical = "Top guards by ts% in 2024-25: Giannis leads restricted-area frequency at 41.2%.";
  const bridgeResults = new Map();
  const fakeSqlExec = {
    name: "sql_exec",
    label: "SQL",
    description: "Run SQL",
    parameters: { type: "object", properties: {} },
    async execute(callId) {
      const record = makeSourceRecord("fake-ev-1", { rows: [{ player: "Giannis", ts_pct: 41.2 }] });
      bridgeResults.set(record.ref, record);
      return sourceResult(record);
    },
  };

  let execRequests = 0;
  let mode = "reprompt";
  const seenContexts = [];
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
      seenContexts.push(JSON.stringify(context));
      let msg;
      if (execRequests === 1) {
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "text", text: longText }], stopReason: "stop", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      } else if (execRequests === 2) {
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "text", text: longText }], stopReason: "stop", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      } else if (execRequests === 3 && mode === "reprompt") {
        const code = `await tools.sql_exec({ sql: "select player, ts_pct from silver_leaders where season='2024-25' and pos='guard' order by ts_pct desc limit 10", intent: "rank top guards by ts% in 2024-25" }); await tools.submit_answer({ blocks: [{ text: ${JSON.stringify(canonical)}, anchors: [{ ref: "fake-ev-1", row: 0, columns: ["ts_pct"] }] }], artifacts: [{ kind: "table", title: "Leaders", columns: [{ key: "ts_pct", label: "TS%", numeric: true }], rows: [{ player: "Giannis", ts_pct: 41.2 }] }] }); return { done: true };`;
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "toolCall", id: "call-sub", name: "codemode", arguments: { code } }], stopReason: "toolUse", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      } else {
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "text", text: "Submitted." }], stopReason: "stop", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      }
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
      stream.end();
      return stream;
    },
  });

  const mockBridge = { tools: [fakeSqlExec], results: bridgeResults, pid: 12345, close: async () => {} };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  const run = async (extra = {}) => {
    const events = [];
    for await (const event of pi.stream({
      q: "Rank the top guards by ts% in 2024-25",
      history: [],
      model: "fixture:fixture",
      sources: [],
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
      ...extra,
    })) {
      events.push(event);
    }
    return events;
  };

  let events = await run();
  const reprompts = events.filter((e) => e.type === "tool_call" && e.name === "zero_evidence_reprompt");
  assert.equal(reprompts.length, 1, "forced reprompt fires exactly once");
  const repromptContext = seenContexts.find((c) => c.includes("This is a data question and no data tool has been called"));
  assert.ok(repromptContext, "reprompt text reaches the model context");
  
  assert.ok(repromptContext.includes("duckdb_tables"), "reprompt carries the concrete copy-pasteable probe call");
  assert.ok(repromptContext.includes("nothing has failed"), "reprompt corrects the false-failure belief");
  const zeIdx = events.findIndex((e) => e.type === "tool_call" && e.name === "zero_evidence_reprompt");
  const steerIdx = events.findIndex((e) => e.type === "tool_call" && e.name === "turn_end_steer");
  if (steerIdx !== -1)
    assert.ok(zeIdx < steerIdx, "zero-evidence reprompt fires before turn_end_steer on data asks with no evidence");
  const answer = events.find((e) => e.type === "answer");
  assert.equal(answer.text, canonical);

  mode = "land";
  execRequests = 0;
  bridgeResults.clear();
  events = await run({ runTimeoutMs: 1 });
  const reprompts2 = events.filter((e) => e.type === "tool_call" && e.name === "zero_evidence_reprompt");
  assert.equal(reprompts2.length, 0, "reprompt skipped when budget cannot allow it");
  const landed = events.find((e) => e.type === "answer");
  assert.deepEqual(landed.submission?.omitted, ["zero data tool calls and no evidence sources before submitting a data-grounded answer"]);
  assert.equal(landed.text, longText);

  await rm(cwd, { recursive: true, force: true });
});

test("createPiExecution rejects a zero-evidence submit_answer on a data ask", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-zero-evidence-submit-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });

  const canonical = "Top guards by ts% in 2024-25: Giannis leads restricted-area frequency at 41.2%.";
  const bridgeResults = new Map();
  const fakeSqlExec = {
    name: "sql_exec",
    label: "SQL",
    description: "Run SQL",
    parameters: { type: "object", properties: {} },
    async execute(callId) {
      const record = makeSourceRecord("fake-ev-1", { rows: [{ player: "Giannis", ts_pct: 41.2 }] });
      bridgeResults.set(record.ref, record);
      return sourceResult(record);
    },
  };

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
      let msg;
      if (execRequests === 1) {
        const code = `await tools.submit_answer({ blocks: [{ text: "The answer has been submitted via tools.submit_answer." }], omitted: ["who leads"] }); return { done: true };`;
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "toolCall", id: "call-sub", name: "codemode", arguments: { code } }], stopReason: "toolUse", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      } else if (execRequests === 2) {
        const code = `await tools.sql_exec({ sql: "select player, ts_pct from silver_leaders where season='2024-25' and pos='guard' order by ts_pct desc limit 10", intent: "rank top guards by ts% in 2024-25" }); await tools.submit_answer({ blocks: [{ text: ${JSON.stringify(canonical)}, anchors: [{ ref: "fake-ev-1", row: 0, columns: ["ts_pct"] }] }] }); return { done: true };`;
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "toolCall", id: "call-sub2", name: "codemode", arguments: { code } }], stopReason: "toolUse", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      } else {
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "text", text: "Done." }], stopReason: "stop", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      }
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
      stream.end();
      return stream;
    },
  });

  const mockBridge = { tools: [fakeSqlExec], results: bridgeResults, pid: 12345, close: async () => {} };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  const events = [];
  for await (const event of pi.stream({
    q: "Rank the top guards by ts% in 2024-25",
    history: [],
    model: "fixture:fixture",
    sources: [],
    cwd,
    agentDir,
    bridge: { python: "fake", cwd, env: {} },
  })) {
    events.push(event);
  }

  const audits = events.filter((e) => e.type === "tool_result" && e.name === "submit_answer_audit" && e.status === "fail");
  assert.ok(audits.some((e) => String(e.error).includes("no_evidence_on_data_ask")), "audit rejects a zero-evidence submit");
  const answer = events.find((e) => e.type === "answer");
  assert.equal(answer.text, canonical, "resubmission after a data call lands");

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

test("validateAnswerSubmission permits omitted anchors and normalizes shot_chart pct from 0-1 to 0-100", () => {
  const validated = validateAnswerSubmission({
    blocks: [{ text: "Empirical Bayes ridge estimate without SQL row anchors." }],
    artifacts: [
      {
        kind: "shot_chart",
        title: "Zone Profile",
        zones: [
          { x: 0, y: 2, att: 180, pct: 0.68 },
          { x: 22, y: 1, att: 90, pct: 0.425 },
        ],
      },
    ],
  }, () => undefined);
  assert.deepEqual(validated.blocks[0].anchors, []);
  assert.equal(validated.artifacts[0].zones[0].pct, 68);
  assert.equal(validated.artifacts[0].zones[1].pct, 42.5);
});

test("validateAnswerSubmission accepts valid typed artifacts for every known kind", () => {
  const artifacts = [
    {
      kind: "table",
      title: "Top scorers",
      columns: [
        { key: "player", label: "Player" },
        { key: "ppg", label: "PPG", numeric: true },
        { key: "gp", label: "GP", numeric: true },
      ],
      rows: [
        { player: "Player One", ppg: 30.1, gp: 72 },
        { player: "Player Two", ppg: null, gp: 68 },
      ],
      footnote: "n=2 fixture rows · season 2025-26",
    },
    {
      kind: "table",
      title: "Array rows",
      columns: [
        { key: "player", label: "Player" },
        { key: "ppg", label: "PPG", numeric: true },
      ],
      rows: [["Player One", 30.1], ["Player Two", ""]],
    },
    {
      kind: "compare",
      title: "Head to head",
      aName: "Player One",
      bName: "Player Two",
      rows: [
        { label: "Points per game", a: 30.1, b: 27.4 },
        { label: "True shooting", a: 61.2, b: 59.8 },
      ],
    },
    {
      kind: "chart",
      title: "Scoring trend",
      unit: "PPG",
      xLabels: ["G1-5", "G6-10"],
      series: [
        { name: "Player One", values: [31.2, null], tone: "accent" },
        { name: "Baseline", values: [33.9, 33.9], tone: "muted" },
      ],
      footnote: "Fixture values.",
    },
    {
      kind: "shot_chart",
      title: "Shot diet",
      zones: [
        { x: 0, y: 0, att: 380, pct: 0.684 },
        { x: 22, y: 5, att: 40, pct: 0.395 },
      ],
      footnote: "Fixture zones.",
    },
    {
      kind: "scatter",
      title: "Usage vs efficiency",
      xLabel: "Usage rate",
      yLabel: "True shooting",
      xMid: 20,
      yMid: 57.5,
      points: [
        { label: "Player One", x: 29.5, y: 66.8, highlight: true },
        { label: "League average", x: 20, y: 57.5 },
      ],
    },
  ];
  const validated = validateAnswerSubmission({ blocks: [{ text: "Fixture answer." }], artifacts }, () => undefined);
  assert.equal(validated.artifacts.length, artifacts.length);
  assert.deepEqual(validated.artifacts[0], artifacts[0]);
  assert.deepEqual(validated.artifacts[1], artifacts[1]);
  assert.deepEqual(validated.artifacts[2], artifacts[2]);
  assert.deepEqual(validated.artifacts[3], artifacts[3]);
  assert.equal(validated.artifacts[4].zones[0].pct, 68.4);
  assert.equal(validated.artifacts[4].zones[1].pct, 39.5);
  assert.deepEqual(validated.artifacts[5], artifacts[5]);
});

test("validateAnswerSubmission rejects malformed typed artifacts with actionable errors", () => {
  const cases = [
    [{ kind: "table", title: "Bad", rows: [] }, /Invalid table artifact at artifacts\[0\].*\/rows: must not have fewer than 1 items/i],
    [{ kind: "table", title: "Bad", columns: [], rows: [{}] }, /Invalid table artifact.*\/columns: must not have fewer than 1 items/i],
    [{ kind: "table", title: "Bad", columns: [{ key: "player", label: "Player" }], rows: [{ other: "x" }] }, /missing column 'player'/],
    [{ kind: "table", title: "Bad", columns: [{ key: "ppg", label: "PPG" }], rows: [[1, 2]] }, /expected 1 cell\(s\)/],
    [{ kind: "table", title: "Bad", columns: [{ key: "ppg", label: "PPG" }], rows: [[{}]] }, /string, number or null/],
    [{ kind: "table", title: "Bad", columns: [{ key: "ppg", label: "PPG" }], rows: [{ ppg: 30 }], subtitle: "x" }, /must not have additional properties|additional propert/i],
    [{ kind: "compare", title: "Bad", aName: "A", bName: "B", rows: [] }, /Invalid compare artifact/],
    [{ kind: "compare", title: "Bad", aName: "A", bName: "B", rows: [{ label: "PPG", a: "30", b: 27 }] }, /\/rows\/0\/a: must be number/i],
    [{ kind: "chart", title: "Bad", series: [] }, /Invalid chart artifact.*\/series: must not have fewer than 1 items/i],
    [{ kind: "chart", title: "Bad", series: [{ name: "A", values: [] }] }, /\/series\/0\/values: must not have fewer than 1 items/i],
    [{ kind: "chart", title: "Bad", series: [{ name: "A", values: [null] }] }, /every series value is null/],
    [{ kind: "chart", title: "Bad", series: [{ name: "A", values: [1], tone: "neon" }] }, /\/series\/0\/tone/i],
    [{ kind: "shot_chart", title: "Bad", zones: [] }, /Invalid shot_chart artifact.*\/zones: must not have fewer than 1 items/i],
    [{ kind: "shot_chart", title: "Bad", zones: [{ x: 0, y: 0, att: 10 }] }, /\/zones\/0: must have required properties pct/i],
    [{ kind: "shot_chart", title: "Bad", zones: [{ x: 0, y: 0, att: -3, pct: 50 }] }, /\/zones\/0\/att: must be >= 0/i],
    [{ kind: "scatter", title: "Bad", xLabel: "USG", yLabel: "TS", points: [] }, /Invalid scatter artifact.*\/points: must not have fewer than 1 items/i],
    [{ kind: "scatter", title: "Bad", xLabel: "USG", yLabel: "TS", points: [{ label: "A", y: 60 }] }, /\/points\/0: must have required properties x/i],
    [{ kind: "scatter", title: "Bad", xLabel: "USG", yLabel: "TS", xMid: "20", points: [{ label: "A", x: 1, y: 2 }] }, /\/xMid: must be number/i],
  ];
  for (const [artifact, pattern] of cases) {
    assert.throws(
      () => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [artifact] }, () => undefined),
      error => {
        assert.match(error.message, pattern);
        assert.match(error.message, /visual-artifacts skill/);
        return true;
      },
      `expected rejection for ${JSON.stringify(artifact)}`
    );
  }
  assert.throws(
    () => validateAnswerSubmission({
      blocks: [{ text: "ok" }, { text: "never reached" }],
      artifacts: [
        { kind: "future_kind", title: "Future", payload: { nested: true } },
        { kind: "compare", title: "Bad", aName: "A", bName: "B", rows: [{ label: "X", a: 1 }] },
      ],
    }, () => undefined),
    /Invalid compare artifact at artifacts\[1\]/
  );
});

test("shot_chart zones carry optional label, makes and league-delta fields", () => {
  const validated = validateAnswerSubmission({
    blocks: [{ text: "Shot diet" }],
    artifacts: [
      {
        kind: "shot_chart",
        title: "Zone efficiency vs league",
        zones: [
          { x: 0, y: 4, att: 380, makes: 260, pct: 68.4, delta: 8.1, label: "rim-C" },
          { x: -14, y: 14, att: 120, makes: 56, pct: 46.5, delta: -3.4, label: "long_mid-L" },
        ],
      },
    ],
  }, () => undefined);
  const zone = validated.artifacts[0].zones[0];
  assert.equal(zone.label, "rim-C");
  assert.equal(zone.makes, 260);
  assert.equal(zone.delta, 8.1);
  assert.equal(zone.pct, 68.4);
});

function playerCardInput(overrides = {}) {
  return { kind: "player_card", title: "Player snapshot", ref: "card-source", row: 0, nameColumn: "player", teamColumn: "team",
    metrics: [{ column: "pts", label: "Points" }, { column: "missed", label: "Missed" }, { column: "impact", label: "Impact" }], ...overrides };
}

function playerCardSource() {
  const source = makeSourceRecord("card-source", { rows: [{ player: "Alex Example", team: "Fixture City", pts: 24.6, missed: 0, impact: null }] });
  source.response.structuredContent.declared_column_semantics = { pts: { unit: "points/game" }, missed: { unit: "games" } };
  source.response.structuredContent.meta = { season: "fixture-season", sql: "SELECT player, team, pts FROM fixture WHERE player = ?" };
  return source;
}

test("player cards resolve identity, exact values and declared units from one source row", () => {
  const source = playerCardSource(), input = playerCardInput();
  const original = structuredClone(input);
  const result = validateAnswerSubmission({ blocks: [{ text: "Fixture only" }], artifacts: [input] }, ref => ref === source.ref ? source : undefined);
  const card = result.artifacts[0];
  assert.equal(card.playerName, "Alex Example");
  assert.equal(card.team, "Fixture City");
  assert.equal(card.sourceRef, source.ref);
  assert.equal(card.sourceRow, 0);
  assert.deepEqual(card.metrics, [{ column: "pts", label: "Points", value: 24.6, unit: "points/game" }, { column: "missed", label: "Missed", value: 0, unit: "games" }, { column: "impact", label: "Impact", value: null }]);
  assert.equal(card.provenance.origin, "undeclared");
  assert.equal(card.provenance.season, "fixture-season");
  assert.equal(card.provenance.sql, "SELECT player, team, pts FROM fixture WHERE player = ?");
  assert.deepEqual(input, original);
});

test("player card provenance resolves warehouse, live and undeclared metadata honestly", () => {
  const validate = source => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [playerCardInput()] }, () => source).artifacts[0].provenance;
  const warehouse = playerCardSource();
  warehouse.response.structuredContent.meta = {
    season: "2026-27", source: "warehouse", dataset: "warehouse",
    warehouse_id: "fixture-warehouse", as_of: "2026-06-18",
    sql: "SELECT player, team, pts FROM fixture WHERE player = ?"
  };
  assert.deepEqual(validate(warehouse), {
    capability: "sql_exec", origin: "warehouse", live_sources: [],
    warehouse_id: "fixture-warehouse", dataset: "warehouse",
    season: "2026-27", as_of: "2026-06-18",
    sql: "SELECT player, team, pts FROM fixture WHERE player = ?"
  });

  const live = playerCardSource();
  live.response.structuredContent.meta = {
    season: "2026-27", source: "nba_api_plydsh", fetched_at: "2026-06-18T12:00:00Z", cached: false,
    sql: "SELECT player, team, pts FROM fixture WHERE player = ?"
  };
  assert.deepEqual(validate(live), {
    capability: "sql_exec", origin: "live", live_sources: ["nba_api"],
    dataset: "nba_api_plydsh", season: "2026-27", as_of: "2026-06-18T12:00:00Z",
    sql: "SELECT player, team, pts FROM fixture WHERE player = ?"
  });
  live.response.structuredContent.meta.source = "espn+nba_api+warehouse";
  assert.deepEqual(validate(live).live_sources, ["nba_api", "espn"]);

  const undeclared = playerCardSource();
  assert.equal(validate(undeclared).origin, "undeclared");
  assert.deepEqual(validate(undeclared).live_sources, []);
  assert.equal(validate(undeclared).warehouse_id, undefined);
});

test("player card provenance pins fallback outcomes and composite lineage gaps", () => {
  const validate = source => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [playerCardInput()] }, () => source).artifacts[0].provenance;

  const served = playerCardSource();
  served.response.structuredContent.meta = {
    season: "2026-27", source: "nba_api_plydsh", warehouse_id: "fixture-warehouse",
    cached: false, fetched_at: "2026-06-18T12:00:00Z",
    live_fallback: { outcome: "served", live_source: "nba_api" },
  };
  const servedProvenance = validate(served);
  assert.equal(servedProvenance.origin, "live");
  assert.equal(servedProvenance.warehouse_id, undefined);
  assert.deepEqual(servedProvenance.live_sources, ["nba_api"]);

  const stale = playerCardSource();
  stale.response.structuredContent.meta = {
    season: "2026-27", source: "nba_api_plydsh", warehouse_id: "fixture-warehouse",
    cached: true, stale: true,
    live_fallback: { outcome: "stale", live_source: "nba_api" },
  };
  const staleProvenance = validate(stale);
  assert.equal(staleProvenance.origin, "warehouse");
  assert.equal(staleProvenance.warehouse_id, "fixture-warehouse");
  assert.deepEqual(staleProvenance.live_sources, []);

  const composite = playerCardSource();
  composite.response.structuredContent.meta = {
    season: "2026-27", source: "nba_api+warehouse", warehouse_id: "fixture-warehouse",
  };
  const compositeProvenance = validate(composite);
  assert.equal(compositeProvenance.origin, "undeclared");
  assert.equal(compositeProvenance.warehouse_id, undefined);
  assert.deepEqual(compositeProvenance.live_sources, []);
});

test("player cards reject forged values, units, row joins and invalid selectors", () => {
  const source = playerCardSource();
  const validate = artifact => validateAnswerSubmission({ blocks: [{ text: "Fixture only" }], artifacts: [artifact] }, () => source);
  for (const overrides of [
    { row: -1 }, { row: 0.5 }, { row: 1 }, { nameColumn: "missing" }, { nameColumn: "pts" }, { teamColumn: "missing" },
    { playerName: "Forged" }, { provenance: { origin: "warehouse" } }, { metrics: [] },
    { metrics: Array.from({ length: 7 }, () => ({ column: "pts", label: "Points" })) },
    { metrics: [{ column: "pts", label: "Points", value: 99 }] },
    { metrics: [{ column: "pts", label: "Points", unit: "%" }] },
    { metrics: [{ column: "pts", label: "Points", row: 1 }] },
    { metrics: [{ column: "player", label: "Wrong type" }] },
    { metrics: [{ column: "missing", label: "Missing" }] },
  ]) assert.throws(() => validate(playerCardInput(overrides)));
  assert.throws(() => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [playerCardInput()] }, () => undefined), /Unknown player_card source/);
  source.response.isError = true;
  assert.throws(() => validate(playerCardInput()), /successful source/);
});

test("player cards use source units fallback and refuse non-finite or string metrics", () => {
  const source = playerCardSource();
  source.response.structuredContent.units = { impact: "points/100 possessions" };
  const validate = () => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [playerCardInput()] }, () => source);
  assert.equal(validate().artifacts[0].metrics[2].unit, "points/100 possessions");
  for (const value of ["24.6", Infinity, NaN, {}, undefined]) {
    source.response.structuredContent.rows[0].pts = value;
    assert.throws(validate);
  }
});

test("player card sections resolve values and provenance from their own source rows", () => {
  const header = playerCardSource();
  const contract = makeSourceRecord("contract-src", { rows: [{ salary: 30000000, contract_type: "DVET-EXT" }] });
  contract.response.structuredContent.meta = { season: "2026-27", source: "bref_contracts" };
  const injury = makeSourceRecord("injury-src", { rows: [{ status: "Questionable", detail: "Ankle" }] });
  injury.response.structuredContent.meta = { season: "2026-27", source: "espn" };
  const sources = new Map([[header.ref, header], [contract.ref, contract], [injury.ref, injury]]);
  const input = playerCardInput({
    sections: [
      { label: "Contract", ref: "contract-src", row: 0,
        metrics: [{ column: "salary", label: "Salary" }],
        fields: [{ column: "contract_type", label: "Deal" }] },
      { label: "Availability", ref: "injury-src", row: 0,
        fields: [{ column: "status", label: "Status" }, { column: "detail", label: "Detail" }] },
    ],
  });
  const result = validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [input] }, ref => sources.get(ref));
  const card = result.artifacts[0];
  assert.equal(card.sections.length, 2);
  const [contractSection, injurySection] = card.sections;
  assert.equal(contractSection.label, "Contract");
  assert.equal(contractSection.sourceRef, "contract-src");
  assert.deepEqual(contractSection.metrics, [{ column: "salary", label: "Salary", value: 30000000 }]);
  assert.deepEqual(contractSection.fields, [{ column: "contract_type", label: "Deal", value: "DVET-EXT" }]);
  assert.equal(contractSection.provenance.season, "2026-27");
  assert.equal(contractSection.provenance.dataset, "bref_contracts");
  assert.equal(contractSection.provenance.capability, "sql_exec");
  assert.deepEqual(injurySection.fields, [{ column: "status", label: "Status", value: "Questionable" }, { column: "detail", label: "Detail", value: "Ankle" }]);
  assert.equal(injurySection.metrics, undefined);
  assert.equal(injurySection.provenance.dataset, "espn");
});

test("player card sections reject bad selectors, forged values and empty sections", () => {
  const header = playerCardSource();
  const other = makeSourceRecord("other-src", { rows: [{ val: 5, status: "ok" }] });
  const sources = new Map([[header.ref, header], [other.ref, other]]);
  const validate = input => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [input] }, ref => sources.get(ref));
  for (const sections of [
    [],
    Array.from({ length: 7 }, () => ({ label: "S", ref: "other-src", row: 0, metrics: [{ column: "val", label: "V" }] })),
    [{ label: "S", ref: "other-src", row: 0 }],
    [{ label: "S", ref: "other-src", row: 0, metrics: [], fields: [] }],
    [{ label: "S", ref: "missing-src", row: 0, metrics: [{ column: "val", label: "V" }] }],
    [{ label: "S", ref: "other-src", row: 3, metrics: [{ column: "val", label: "V" }] }],
    [{ label: "S", ref: "other-src", row: 0, metrics: [{ column: "missing", label: "V" }] }],
    [{ label: "S", ref: "other-src", row: 0, metrics: [{ column: "status", label: "V" }] }],
    [{ label: "S", ref: "other-src", row: 0, fields: [{ column: "val", label: "F" }] }],
    [{ label: "S", ref: "other-src", row: 0, fields: [{ column: "status", label: "F", value: "forged" }] }],
    [{ label: "S", ref: "other-src", row: 0, metrics: [{ column: "val", label: "V" }], provenance: { origin: "warehouse" } }],
  ]) assert.throws(() => validate(playerCardInput({ sections })));
});

function teamCardInput(overrides = {}) {
  return { kind: "team_card", title: "Team snapshot", ref: "team-src", row: 0, nameColumn: "team_name",
    metrics: [{ column: "wins", label: "W" }, { column: "losses", label: "L" }, { column: "net_rating", label: "Net Rtg" }], ...overrides };
}

function teamCardSource() {
  const source = makeSourceRecord("team-src", { rows: [{ team_name: "Example City Club", wins: 42, losses: 22, net_rating: 4.1 }] });
  source.response.structuredContent.declared_column_semantics = { net_rating: { unit: "points/100 possessions" } };
  source.response.structuredContent.meta = {
    season: "2026-27", source: "warehouse", dataset: "warehouse",
    warehouse_id: "fixture-team-warehouse", as_of: "2026-06-18",
    sql: "SELECT team_name, wins, losses, net_rating FROM fixture_team"
  };
  return source;
}

test("team cards resolve identity, metrics and sections with per-section provenance", () => {
  const header = teamCardSource();
  const cap = makeSourceRecord("cap-src", { rows: [{ total_salary: 187000000, apron_room: -12000000, cap_status: "Above first apron" }] });
  cap.response.structuredContent.units = {
    total_salary: "usd_dollars",
    apron_room: "usd_dollars",
  };
  cap.response.structuredContent.meta = { season: "2026-27", source: "orojas119/nba-salary-cap (estimated)", warehouse_id: "configured-runtime" };
  const fourFactors = makeSourceRecord("4f-src", { rows: [{ efg_pct: 0.56, rank_efg: 4, tov_pct: 0.128 }] });
  fourFactors.response.structuredContent.meta = { season: "2026-27", source: "nba_four_factors" };
  const picks = makeSourceRecord("picks-src", { rows: [{ pick_summary: "Own 2027-2032" }] });
  picks.response.structuredContent.meta = { season: "2026-27", source: "picks" };
  const sources = new Map([header, cap, fourFactors, picks].map(s => [s.ref, s]));
  const input = teamCardInput({
    sections: [
      { label: "Payroll", ref: "cap-src", row: 0,
        metrics: [{ column: "total_salary", label: "Payroll" }, { column: "apron_room", label: "Apron room" }],
        fields: [{ column: "cap_status", label: "Cap status" }] },
      { label: "Four factors", ref: "4f-src", row: 0,
        metrics: [{ column: "efg_pct", label: "eFG%" }, { column: "rank_efg", label: "eFG rank" }] },
      { label: "Draft capital", ref: "picks-src", row: 0,
        fields: [{ column: "pick_summary", label: "Picks" }] },
    ],
  });
  const result = validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [input] }, ref => sources.get(ref));
  const card = result.artifacts[0];
  assert.equal(card.kind, "team_card");
  assert.equal(card.teamName, "Example City Club");
  assert.equal(card.sourceRef, "team-src");
  assert.deepEqual(card.metrics[2], { column: "net_rating", label: "Net Rtg", value: 4.1, unit: "points/100 possessions" });
  assert.deepEqual(card.provenance, {
    capability: "sql_exec", origin: "warehouse", live_sources: [],
    warehouse_id: "fixture-team-warehouse", dataset: "warehouse",
    season: "2026-27", as_of: "2026-06-18",
    sql: "SELECT team_name, wins, losses, net_rating FROM fixture_team"
  });
  assert.equal(card.sections.length, 3);
  const [capSection, fourFactorSection, pickSection] = card.sections;
  assert.deepEqual(capSection.metrics, [{ column: "total_salary", label: "Payroll", value: 187000000, unit: "usd_dollars" }, { column: "apron_room", label: "Apron room", value: -12000000, unit: "usd_dollars" }]);
  assert.deepEqual(capSection.fields, [{ column: "cap_status", label: "Cap status", value: "Above first apron" }]);
  assert.equal(capSection.provenance.origin, "warehouse");
  assert.equal(capSection.provenance.warehouse_id, "configured-runtime");
  assert.equal(capSection.provenance.dataset, "orojas119/nba-salary-cap (estimated)");
  assert.equal(fourFactorSection.metrics[1].value, 4);
  assert.equal(fourFactorSection.provenance.dataset, "nba_four_factors");
  assert.equal(pickSection.fields[0].value, "Own 2027-2032");
});

test("team cards reject forged values, bad rows and invalid selectors", () => {
  const source = teamCardSource();
  const other = makeSourceRecord("other-src", { rows: [{ val: 5, note: "ok" }] });
  const sources = new Map([[source.ref, source], [other.ref, other]]);
  const validate = input => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [input] }, ref => sources.get(ref));
  for (const overrides of [
    { row: -1 }, { row: 1 }, { nameColumn: "missing" }, { nameColumn: "wins" }, { teamName: "Forged" },
    { metrics: [] }, { metrics: [{ column: "wins", label: "W", value: 42 }] },
    { metrics: [{ column: "team_name", label: "Name" }] },
    { sections: [{ label: "S", ref: "other-src", row: 0 }] },
    { sections: [{ label: "S", ref: "missing-src", row: 0, metrics: [{ column: "val", label: "V" }] }] },
    { sections: [{ label: "S", ref: "other-src", row: 0, fields: [{ column: "val", label: "F" }] }] },
    { sections: [{ label: "S", ref: "other-src", row: 0, metrics: [{ column: "note", label: "V" }] }] },
    { sections: [{ label: "S", ref: "other-src", row: 0, metrics: [{ column: "val", label: "V", unit: "%" }] }] },
  ]) assert.throws(() => validate(teamCardInput(overrides)));
});
test("player card sections resolve values and provenance from their own source rows", () => {
  const header = playerCardSource();
  const contract = makeSourceRecord("contract-src", { rows: [{ salary: 30000000, contract_type: "DVET-EXT" }] });
  contract.response.structuredContent.meta = { season: "2026-27", source: "bref_contracts" };
  const injury = makeSourceRecord("injury-src", { rows: [{ status: "Questionable", detail: "Ankle" }] });
  injury.response.structuredContent.meta = { season: "2026-27", source: "espn" };
  const sources = new Map([[header.ref, header], [contract.ref, contract], [injury.ref, injury]]);
  const input = playerCardInput({
    sections: [
      { label: "Contract", ref: "contract-src", row: 0,
        metrics: [{ column: "salary", label: "Salary" }],
        fields: [{ column: "contract_type", label: "Deal" }] },
      { label: "Availability", ref: "injury-src", row: 0,
        fields: [{ column: "status", label: "Status" }, { column: "detail", label: "Detail" }] },
    ],
  });
  const result = validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [input] }, ref => sources.get(ref));
  const card = result.artifacts[0];
  assert.equal(card.sections.length, 2);
  const [contractSection, injurySection] = card.sections;
  assert.equal(contractSection.label, "Contract");
  assert.equal(contractSection.sourceRef, "contract-src");
  assert.deepEqual(contractSection.metrics, [{ column: "salary", label: "Salary", value: 30000000 }]);
  assert.deepEqual(contractSection.fields, [{ column: "contract_type", label: "Deal", value: "DVET-EXT" }]);
  assert.equal(contractSection.provenance.season, "2026-27");
  assert.equal(contractSection.provenance.dataset, "bref_contracts");
  assert.equal(contractSection.provenance.capability, "sql_exec");
  assert.deepEqual(injurySection.fields, [{ column: "status", label: "Status", value: "Questionable" }, { column: "detail", label: "Detail", value: "Ankle" }]);
  assert.equal(injurySection.metrics, undefined);
  assert.equal(injurySection.provenance.dataset, "espn");
});

test("player card sections reject bad selectors, forged values and empty sections", () => {
  const header = playerCardSource();
  const other = makeSourceRecord("other-src", { rows: [{ val: 5, status: "ok" }] });
  const sources = new Map([[header.ref, header], [other.ref, other]]);
  const validate = input => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [input] }, ref => sources.get(ref));
  for (const sections of [
    [],
    Array.from({ length: 7 }, () => ({ label: "S", ref: "other-src", row: 0, metrics: [{ column: "val", label: "V" }] })),
    [{ label: "S", ref: "other-src", row: 0 }],
    [{ label: "S", ref: "other-src", row: 0, metrics: [], fields: [] }],
    [{ label: "S", ref: "missing-src", row: 0, metrics: [{ column: "val", label: "V" }] }],
    [{ label: "S", ref: "other-src", row: 3, metrics: [{ column: "val", label: "V" }] }],
    [{ label: "S", ref: "other-src", row: 0, metrics: [{ column: "missing", label: "V" }] }],
    [{ label: "S", ref: "other-src", row: 0, metrics: [{ column: "status", label: "V" }] }],
    [{ label: "S", ref: "other-src", row: 0, fields: [{ column: "val", label: "F" }] }],
    [{ label: "S", ref: "other-src", row: 0, fields: [{ column: "status", label: "F", value: "forged" }] }],
    [{ label: "S", ref: "other-src", row: 0, metrics: [{ column: "val", label: "V" }], provenance: { origin: "warehouse" } }],
  ]) assert.throws(() => validate(playerCardInput({ sections })));
});
test("priorSubmissions returns thread submissions in order and compactPriorSubmissions bounds them", async () => {
  const dir = await mkdtemp(join(tmpdir(), "prior-subs-"));
  try {
    const store = new ProductStore(join(dir, "conversations.sqlite3"), join(dir, "sources"));
    const identity = { owner: "owner-a", thread: "thread-a" };
    const source = makeSourceRecord("src-a", { rows: [{ v: 1 }] });
    const submission1 = { blocks: [{ text: "First answer." }], artifacts: [{ kind: "table", title: "T1", columns: [{ key: "v", label: "V" }], rows: Array.from({ length: 30 }, (_, i) => ({ v: i })) }] };
    const submission2 = { blocks: [{ text: "Second answer." }] };
    store.saveSources("run-" + "a".repeat(32), [source], [source], submission1);
    store.append(identity, "Q1", "A1", "run-" + "a".repeat(32));
    store.saveSources("run-" + "b".repeat(32), [source], [source]);
    store.append(identity, "Q2", "A2", "run-" + "b".repeat(32));
    store.saveSources("run-" + "c".repeat(32), [source], [source], submission2);
    store.append(identity, "Q3", "A3", "run-" + "c".repeat(32));

    const priors = store.priorSubmissions(identity);
    assert.equal(priors.length, 2);
    assert.equal(priors[0].run_id, "run-" + "a".repeat(32));
    assert.equal(priors[1].run_id, "run-" + "c".repeat(32));
    assert.equal(priors[0].submission.blocks[0].text, "First answer.");
    assert.deepEqual(store.priorSubmissions({ owner: "other", thread: "thread-a" }), []);

    const { compactPriorSubmissions } = await import("./dist/pi-execution.js");
    const compact = compactPriorSubmissions(priors);
    assert.equal(compact.length, 2);
    assert.equal(compact[0].run_id, "run-" + "c".repeat(32));
    assert.equal(compact[1].run_id, "run-" + "a".repeat(32));
    const table = compact[1].artifacts[0];
    assert.equal(table.kind, "table");
    assert.equal(table.rows.length, 25);
    assert.equal(table.rows[24], "…6 more");
    const longText = compactPriorSubmissions([{ run_id: "run-x", submission: { blocks: [{ text: "t".repeat(800) }] } }]);
    assert.equal(longText[0].blocks[0].text.length, 501);
    assert(longText[0].blocks[0].text.endsWith("…"));
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
test("memo artifacts validate section anchors like block anchors", () => {
  const sources = new Map([
    ["cap-source", makeSourceRecord("cap-source", { rows: [{ team: "ORL", payroll: 172400000 }] })],
  ]);
  const memo = {
    kind: "memo",
    title: "Cap & roster strategy",
    sections: [
      { heading: "Cap position", body: "Orlando sits under the first apron.", anchors: [{ ref: "cap-source", row: 0, columns: ["team", "payroll"] }] },
      { heading: "Options", body: "Aggregate mid-tier salary." },
    ],
  };
  const validated = validateAnswerSubmission({ blocks: [{ text: "Fixture only" }], artifacts: [memo] }, ref => sources.get(ref));
  assert.equal(validated.artifacts[0].kind, "memo");
  assert.equal(validated.artifacts[0].sections[0].anchors[0].ref, "cap-source");
});

test("memo artifacts reject anchors to unknown refs, bad rows and missing columns", () => {
  const source = makeSourceRecord("cap-source", { rows: [{ team: "ORL", payroll: 172400000 }] });
  const memo = anchors => ({
    kind: "memo",
    title: "Cap & roster strategy",
    sections: [{ heading: "Cap position", body: "Body.", anchors }],
  });
  const validate = artifact => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [artifact] }, ref => ref === "cap-source" ? source : undefined);
  assert.throws(() => validate(memo([{ ref: "ghost", row: 0, columns: ["team"] }])), /Unknown source ref/);
  assert.throws(() => validate(memo([{ ref: "cap-source", row: 5, columns: ["team"] }])), /out of bounds/);
  assert.throws(() => validate(memo([{ ref: "cap-source", row: 0, columns: ["salary"] }])), /does not exist/);
  assert.throws(() => validate(memo([{ ref: "cap-source", row: 0 }])), /Invalid memo section anchor/);
});

test("unknown and empty artifact kinds are dropped with a warning the agent sees", async () => {
  const source = makeSourceRecord("src-1", { rows: [{ stat: "reb", value: 10 }] });
  let accepted = null;
  const tool = createSubmitAnswerTool(
    () => [source],
    sub => { accepted = sub; }
  );
  const submission = {
    blocks: [{ text: "Done." }],
    artifacts: [
      { kind: "pie", title: "Playstyle pie" },
      { kind: "chart", title: "Empty trend" },
      { kind: "memo", title: "No sections", sections: [] },
      { kind: "table", title: "Rebounds", columns: [{ key: "stat", label: "Stat" }, { key: "value", label: "Value" }], rows: [["reb", 10]] },
    ],
  };
  const result = await tool.execute("call-2", submission);
  assert.equal(accepted.artifacts.length, 1);
  assert.equal(accepted.artifacts[0].kind, "table");
  const text = result.content[0].text;
  assert.match(text, /unknown artifact kind "pie"/);
  assert.match(text, /"chart" artifact has no series/);
  assert.match(text, /"memo" artifact has no sections/);
  assert.match(text, /Supported kinds: .*memo/);
});

test("validateAnswerSubmission drops rejected artifacts but keeps valid ones", () => {
  const warnings = [];
  const validated = validateAnswerSubmission(
    { blocks: [{ text: "x" }], artifacts: [{ kind: "mystery", title: "?" }, { kind: "scatter", title: "ok", xLabel: "USG", yLabel: "TS", points: [{ label: "p", x: 1, y: 2 }] }] },
    () => undefined,
    undefined,
    warnings,
  );
  assert.equal(validated.artifacts.length, 1);
  assert.equal(validated.artifacts[0].kind, "scatter");
  assert.deepEqual(warnings, ['dropped artifact: unknown artifact kind "mystery"']);
});
test("memo artifacts validate section anchors like block anchors", () => {
  const sources = new Map([
    ["cap-source", makeSourceRecord("cap-source", { rows: [{ team: "ORL", payroll: 172400000 }] })],
  ]);
  const memo = {
    kind: "memo",
    title: "Cap & roster strategy",
    sections: [
      { heading: "Cap position", body: "Orlando sits under the first apron.", anchors: [{ ref: "cap-source", row: 0, columns: ["team", "payroll"] }] },
      { heading: "Options", body: "Aggregate mid-tier salary." },
    ],
  };
  const validated = validateAnswerSubmission({ blocks: [{ text: "Fixture only" }], artifacts: [memo] }, ref => sources.get(ref));
  assert.equal(validated.artifacts[0].kind, "memo");
  assert.equal(validated.artifacts[0].sections[0].anchors[0].ref, "cap-source");
});

test("memo artifacts reject anchors to unknown refs, bad rows and missing columns", () => {
  const source = makeSourceRecord("cap-source", { rows: [{ team: "ORL", payroll: 172400000 }] });
  const memo = anchors => ({
    kind: "memo",
    title: "Cap & roster strategy",
    sections: [{ heading: "Cap position", body: "Body.", anchors }],
  });
  const validate = artifact => validateAnswerSubmission({ blocks: [{ text: "Fixture" }], artifacts: [artifact] }, ref => ref === "cap-source" ? source : undefined);
  assert.throws(() => validate(memo([{ ref: "ghost", row: 0, columns: ["team"] }])), /Unknown source ref/);
  assert.throws(() => validate(memo([{ ref: "cap-source", row: 5, columns: ["team"] }])), /out of bounds/);
  assert.throws(() => validate(memo([{ ref: "cap-source", row: 0, columns: ["salary"] }])), /does not exist/);
  assert.throws(() => validate(memo([{ ref: "cap-source", row: 0 }])), /Invalid memo section anchor/);
});
test("validateAnswerSubmission promotes a markdown table in blocks into a table artifact", () => {
  const text = [
    "Top-10 picks by pre-draft organization type:",
    "",
    "| Org Type | Top-10 Picks | Share |",
    "| --- | ---: | ---: |",
    "| College | 232 | 95.3% |",
    "| Other club | 34 | 14.0% |",
    "| High school | 13 | 5.3% |",
    "",
    "College dominates the pipeline.",
  ].join("\n");
  const validated = validateAnswerSubmission({ blocks: [{ text }] }, () => undefined);
  assert.equal(validated.artifacts.length, 1);
  const table = validated.artifacts[0];
  assert.equal(table.kind, "table");
  assert.equal(table.title, "Top-10 picks by pre-draft organization type:");
  assert.deepEqual(table.columns.map(c => c.key), ["org_type", "top_10_picks", "share"]);
  assert.equal(table.columns[1].numeric, true);
  assert.deepEqual(table.rows[0], { org_type: "College", top_10_picks: 232, share: 95.3 });
  assert.equal(table.rows.length, 3);
});

test("validateAnswerSubmission does not promote markdown tables when a table artifact already exists", () => {
  const text = "| A | B |\n| --- | --- |\n| 1 | 2 |";
  const artifacts = [{ kind: "table", title: "Given", columns: [{ key: "x", label: "X" }], rows: [{ x: 5 }] }];
  const validated = validateAnswerSubmission({ blocks: [{ text }], artifacts }, () => undefined);
  assert.equal(validated.artifacts.length, 1);
  assert.equal(validated.artifacts[0].title, "Given");
});

test("validateAnswerSubmission leaves blocks without tables artifact-free", () => {
  const validated = validateAnswerSubmission({ blocks: [{ text: "No table here, just prose." }] }, () => undefined);
  assert.equal(validated.artifacts, undefined);
});

test("validateAnswerSubmission promotes multiple markdown tables up to the cap", () => {
  const text = [
    "| Team | Wins |",
    "| --- | ---: |",
    "| OKC | 50 |",
    "",
    "Some words between the tables.",
    "",
    "| Player | PPG |",
    "| --- | ---: |",
    "| SGA | 31.2 |",
  ].join("\n");
  const validated = validateAnswerSubmission({ blocks: [{ text }] }, () => undefined);
  assert.equal(validated.artifacts.length, 2);
  assert.equal(validated.artifacts[0].columns[0].key, "team");
  assert.equal(validated.artifacts[1].columns[0].key, "player");
});

test("createPiExecution formats missing_in_artifacts feedback with the figure named", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-exec-miafmt-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const currentRecord = makeSourceRecord("src-cur", { rows: [{ player: "Giannis", ts_pct: 41.2, fga: 359 }] });
  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });

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
      if (execRequests === 1) {
        const code = `
          await tools.query_tool({ q: "x" });
          await tools.submit_answer({
            blocks: [{ text: "Giannis posted 41.2% true shooting across 359 attempts this season, a heavy workload.", anchors: [] }],
            artifacts: [{ kind: "table", title: "TS leaders", columns: [{ key: "player", label: "Player" }, { key: "ts", label: "TS%", numeric: true }], rows: [{ player: "Giannis", ts: 41.2 }] }]
          });
          return { done: true };
        `;
        const msg = {
          role: "assistant", api: model.api, provider: model.provider, model: model.id,
          content: [{ type: "toolCall", id: "call-1", name: "codemode", arguments: { code } }],
          stopReason: "toolUse", timestamp: Date.now(),
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        };
        const stream = createAssistantMessageEventStream();
        stream.push({ type: "done", reason: "toolUse", message: msg });
        stream.end();
        return stream;
      }
      const msg = {
        role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: [{ type: "text", text: "Done." }],
        stopReason: "stop", timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: "stop", message: msg });
      stream.end();
      return stream;
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
            content: [{ type: "text", text: JSON.stringify({ rows: [{ player: "Giannis", ts_pct: 41.2, fga: 359 }] }) }],
            structuredContent: { ref: "src-cur", tool: "query_tool", isError: false, result: { rows: [{ player: "Giannis", ts_pct: 41.2, fga: 359 }] } },
          };
        },
      },
    ],
    results: new Map([["src-cur", currentRecord]]),
    pid: 12345,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  const events = [];
  for await (const event of pi.stream({
    q: "How did Giannis shoot?",
    history: [],
    model: "fixture:fixture",
    cwd,
    agentDir,
    bridge: { python: "fake", cwd, env: {} },
  })) {
    events.push(event);
  }

  const auditFail = events.find((e) => e.type === "tool_result" && e.name === "submit_answer_audit" && e.status === "fail");
  assert.ok(auditFail, "expected an audit rejection");
  assert.ok(String(auditFail.error).includes("missing_in_artifacts"), "missing_in_artifacts fired");
  assert.ok(String(auditFail.error).includes("359"), "the missing figure itself is named in the feedback");
  assert.ok(String(auditFail.error).includes("artifact payload"), "feedback explains the figure must move into an artifact row");
  assert.ok(!String(auditFail.error).includes("**"), "markdown debris is stripped from the feedback");

  await rm(cwd, { recursive: true, force: true });
});

test("createPiExecution salvages a rejected submission over a thin meta-echo ending", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-exec-salvage-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const currentRecord = makeSourceRecord("src-current", { rows: [{ pts: 33.9, player: "Luka" }] });
  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });

  const realContent = "Luka Doncic led all scorers with 33.9 points per game in a dominant season, well clear of the field.";
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
      if (execRequests === 1) {
        const code = `
          await tools.query_tool({ q: "points" });
          await tools.submit_answer({
            blocks: [
              { text: ${JSON.stringify(realContent)} + " He also scored 99.9 in the finale.", anchors: [] }
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
      }
      const echo = execRequests === 2 ? "Submitted." : "Submitted.";
      const msg = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        content: [{ type: "text", text: echo }],
        stopReason: "stop",
        timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: "stop", message: msg });
      stream.end();
      return stream;
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
    ],
    results: new Map([["src-current", currentRecord]]),
    pid: 12345,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

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
  assert.equal(answerEvent.text, realContent + " He also scored 99.9 in the finale.");
  assert.ok(answerEvent.submission, "salvaged submission should be attached");
  const auditRejection = events.find((e) => e.type === "tool_result" && e.name === "submit_answer_audit" && e.status === "fail");
  assert.ok(auditRejection, "the submission must actually have been rejected for this test to exercise the salvage path");
  assert.ok(execRequests >= 2, "model should have continued after the rejection");

  await rm(cwd, { recursive: true, force: true });
});

test("createPiExecution salvages final narration when a normal-end run never submits", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-exec-narrsalv-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const currentRecord = makeSourceRecord("src-current", { rows: [{ gp: 75, ppg: 18.43 }] });
  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });

  const narration = "Reconciling the stints: Detroit 28 games at 10.79 points per game, Brooklyn 23 games at 18.43 points per game, Golden State 24 games at 10.58 points per game, for a confirmed total of 75 games matching the season summary row exactly.";
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
      const isFirst = execRequests === 1;
      const content = isFirst
        ? [{ type: "toolCall", id: "call-1", name: "codemode", arguments: { code: "await tools.query_tool({ q: 'gp' }); return { done: true };" } }]
        : [{ type: "text", text: narration }];
      const msg = {
        role: "assistant",
        api: model.api,
        provider: model.provider,
        model: model.id,
        content,
        stopReason: isFirst ? "toolUse" : "stop",
        timestamp: Date.now(),
        usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
      };
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: isFirst ? "toolUse" : "stop", message: msg });
      stream.end();
      return stream;
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
            content: [{ type: "text", text: JSON.stringify({ rows: [{ gp: 75, ppg: 18.43 }] }) }],
            structuredContent: { ref: "src-current", tool: "query_tool", isError: false, result: { rows: [{ gp: 75, ppg: 18.43 }] } },
          };
        },
      },
    ],
    results: new Map([["src-current", currentRecord]]),
    pid: 12345,
    close: async () => {},
  };

  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  const events = [];
  for await (const event of pi.stream({
    q: "Reconcile the stints.",
    history: [],
    model: "fixture:fixture",
    cwd,
    agentDir,
    bridge: { python: "fake", cwd, env: {} },
  })) {
    events.push(event);
  }

  const answerEvent = events.find((e) => e.type === "answer");
  assert.ok(answerEvent, "narration should be salvaged into an accepted answer on normal end");
  assert.equal(answerEvent.text, narration);

  await rm(cwd, { recursive: true, force: true });
});

test("createPiExecution corrects a tool-not-found error with bare registered names", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-notfound-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });

  const runtime = await ModelRuntime.create({
    authPath: join(agentDir, "auth.json"),
    modelsPath: null,
    allowModelNetwork: false,
    refreshOnCreate: false,
  });

  const canonical = "Giannis leads at 41.2%.";
  const bridgeResults = new Map();
  const fakeSqlExec = {
    name: "sql_exec",
    label: "sql_exec",
    description: "fake",
    parameters: Type.Object({ sql: Type.String(), intent: Type.Optional(Type.String()) }),
    execute: async () => {
      const record = makeSourceRecord("nf-ev-1", { rows: [{ player: "Giannis", ts_pct: 41.2 }] });
      bridgeResults.set(record.ref, record);
      return sourceResult(record);
    },
  };

  let execRequests = 0;
  const seenContexts = [];
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
      seenContexts.push(JSON.stringify(context));
      let msg;
      if (execRequests === 1) {
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "toolCall", id: "call-bogus", name: "tools.submit_answer", arguments: { blocks: [{ text: "x" }] } }], stopReason: "toolUse", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      } else if (execRequests === 2) {
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "toolCall", id: "call-sql", name: "sql_exec", arguments: { sql: "select 1", intent: "probe" } }], stopReason: "toolUse", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      } else if (execRequests === 3) {
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "toolCall", id: "call-sub", name: "submit_answer", arguments: { blocks: [{ text: canonical, anchors: [{ ref: "nf-ev-1", row: 0, columns: ["ts_pct"] }] }], artifacts: [{ kind: "table", title: "Leaders", columns: [{ key: "ts_pct", label: "TS%", numeric: true }], rows: [{ player: "Giannis", ts_pct: 41.2 }] }] } }], stopReason: "toolUse", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      } else {
        msg = { role: "assistant", api: model.api, provider: model.provider, model: model.id, content: [{ type: "text", text: "Done." }], stopReason: "stop", timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      }
      const stream = createAssistantMessageEventStream();
      stream.push({ type: "done", reason: msg.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
      stream.end();
      return stream;
    },
  });

  const mockBridge = { tools: [fakeSqlExec], results: bridgeResults, pid: 12345, close: async () => {} };
  const pi = createPiExecution({
    resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
    connectTools: async () => mockBridge,
  });

  const events = [];
  let runError = null;
  try {
    for await (const event of pi.stream({
      q: "Rank the top guards by ts% in 2024-25",
      history: [],
      model: "fixture:fixture",
      sources: [],
      cwd,
      agentDir,
      bridge: { python: "fake", cwd, env: {} },
    })) {
      events.push(event);
    }
  } catch (err) {
    runError = err;
  }

  const corrections = events.filter((e) => e.type === "tool_call" && e.name === "tool_not_found_correction");
  const correctionContext = seenContexts.find((c) => c.includes("nothing is missing"));
  assert.equal(runError, null, "run completes after the malformed call");
  assert.ok(corrections.length >= 1, "not-found correction fires at least once, per-occurrence");
  assert.ok(correctionContext, "correction text reaches the model context");
  assert.ok(correctionContext.includes("invocation form was wrong"), "correction frames the error as invocation form, not missing tools");
  assert.ok(correctionContext.includes("tools.submit_answer"), "correction names the malformed invocation");
  assert.ok(correctionContext.includes("no tools.xxx invocation form"), "correction blocks the tools. prefixed form");
  assert.ok(correctionContext.includes("sql_exec"), "correction names the bare registered tools");
  assert.ok(correctionContext.includes("submit_answer"), "correction lists bare registered direct tool names");
  assert.ok(!correctionContext.includes("Available right now: tools."), "correction lists only bare names");
  assert.equal(execRequests >= 4, true, "model recovers to bare sql_exec and submit_answer calls after the correction");

  await rm(cwd, { recursive: true, force: true });
});

function makeNondeliveryFixture(script) {
  return async (cwd, agentDir) => {
    const runtime = await ModelRuntime.create({
      authPath: join(agentDir, "auth.json"),
      modelsPath: null,
      allowModelNetwork: false,
      refreshOnCreate: false,
    });
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
      streamSimple(model) {
        execRequests++;
        const step = script[Math.min(execRequests - 1, script.length - 1)];
        const msg = {
          role: "assistant",
          api: model.api,
          provider: model.provider,
          model: model.id,
          content: step.content,
          stopReason: step.stopReason,
          timestamp: Date.now(),
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
        };
        const stream = createAssistantMessageEventStream();
        stream.push({ type: "done", reason: step.stopReason === "toolUse" ? "toolUse" : "stop", message: msg });
        stream.end();
        return stream;
      },
    });
    const mockBridge = { tools: [], results: new Map(), pid: 12345, close: async () => {} };
    const pi = createPiExecution({
      resolveRuntime: async () => ({ runtime, model: runtime.getModel("fixture", "fixture") }),
      connectTools: async () => mockBridge,
    });
    return { pi, runtime };
  };
}

const narrationChunk = "Kentucky leads with three first-round picks in the studied window, followed by Duke with two, while North Carolina at seventeen total selections anchors the second tier and Kansas at thirteen plus Arizona and UCLA at eleven each form the third tier of programs.";
const shortCloser = "The analysis is complete.";

test("nondelivery interception fires on multi-message narration with a short closer", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-nondeliv-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });
  const script = [
    { stopReason: "toolUse", content: [{ type: "text", text: narrationChunk }, { type: "toolCall", id: "c1", name: "codemode", arguments: { code: "return { x: 1 };" } }] },
    { stopReason: "stop", content: [{ type: "text", text: " " + narrationChunk }] },
    { stopReason: "stop", content: [{ type: "text", text: shortCloser }] },
    { stopReason: "toolUse", content: [{ type: "toolCall", id: "c2", name: "codemode", arguments: { code: 'await tools.submit_answer({ blocks: [{ text: "Kentucky leads with three first-round picks.", anchors: [] }] }); return { done: true };' } }] },
    { stopReason: "stop", content: [{ type: "text", text: "Submitted." }] },
  ];
  const fixture = makeNondeliveryFixture(script);
  const { pi } = await fixture(cwd, agentDir);
  const events = [];
  for await (const event of pi.stream({
    q: "Which programs produced the most first-round picks?",
    history: [],
    model: "fixture:fixture",
    sources: [],
    cwd,
    agentDir,
    bridge: { python: "fake", cwd, env: {} },
  })) {
    events.push(event);
  }
  const interceptions = events.filter((e) => e.type === "tool_call" && e.name === "nondelivery_interception");
  assert.ok(interceptions.length >= 1, "interception fires on spread narration with short closer");
  await rm(cwd, { recursive: true, force: true });
});

test("nondelivery interception does not fire on clarifying-question endings", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-nondeliv-q-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });
  const script = [
    { stopReason: "toolUse", content: [{ type: "text", text: narrationChunk }, { type: "toolCall", id: "c1", name: "codemode", arguments: { code: "return { x: 1 };" } }] },
    { stopReason: "stop", content: [{ type: "text", text: "Which season window did you want for this analysis?" }] },
    { stopReason: "stop", content: [{ type: "text", text: "standing by" }] },
  ];
  const fixture = makeNondeliveryFixture(script);
  const { pi } = await fixture(cwd, agentDir);
  const events = [];
  for await (const event of pi.stream({
    q: "Which programs produced the most first-round picks?",
    history: [],
    model: "fixture:fixture",
    sources: [],
    cwd,
    agentDir,
    bridge: { python: "fake", cwd, env: {} },
  })) {
    events.push(event);
  }
  const interceptions = events.filter((e) => e.type === "tool_call" && e.name === "nondelivery_interception");
  assert.equal(interceptions.length, 0, "no interception when the ending is a user-directed question");
  await rm(cwd, { recursive: true, force: true });
});

test("nondelivery interception skips to salvage when under 45s remain", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-nondeliv-budget-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });
  const script = [
    { stopReason: "toolUse", content: [{ type: "text", text: narrationChunk }, { type: "toolCall", id: "c1", name: "codemode", arguments: { code: "return { x: 1 };" } }] },
    { stopReason: "stop", content: [{ type: "text", text: " " + narrationChunk }] },
    { stopReason: "stop", content: [{ type: "text", text: shortCloser }] },
    { stopReason: "stop", content: [{ type: "text", text: shortCloser }] },
  ];
  const fixture = makeNondeliveryFixture(script);
  const { pi } = await fixture(cwd, agentDir);
  const events = [];
  for await (const event of pi.stream({
    q: "Which programs produced the most first-round picks?",
    history: [],
    model: "fixture:fixture",
    sources: [],
    cwd,
    agentDir,
    bridge: { python: "fake", cwd, env: {} },
    runTimeoutMs: 40000,
  })) {
    events.push(event);
  }
  const interceptions = events.filter((e) => e.type === "tool_call" && e.name === "nondelivery_interception");
  assert.equal(interceptions.length, 0, "no interception when under 45s of budget remain");
  await rm(cwd, { recursive: true, force: true });
});

test("nondelivery interception counter is independent of turn_end_steer and give-up shots", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "pi-nondeliv-counters-"));
  const agentDir = join(cwd, "agent");
  await mkdir(agentDir, { recursive: true });
  const script = [
    { stopReason: "toolUse", content: [{ type: "text", text: narrationChunk }, { type: "toolCall", id: "c1", name: "codemode", arguments: { code: "return { x: 1 };" } }] },
    { stopReason: "stop", content: [{ type: "text", text: narrationChunk }] },
    { stopReason: "stop", content: [{ type: "text", text: narrationChunk }] },
    { stopReason: "stop", content: [{ type: "text", text: narrationChunk }] },
    { stopReason: "stop", content: [{ type: "text", text: narrationChunk }] },
    { stopReason: "stop", content: [{ type: "text", text: narrationChunk }] },
  ];
  const fixture = makeNondeliveryFixture(script);
  const { pi } = await fixture(cwd, agentDir);
  const events = [];
  for await (const event of pi.stream({
    q: "Which programs produced the most first-round picks?",
    history: [],
    model: "fixture:fixture",
    sources: [],
    cwd,
    agentDir,
    bridge: { python: "fake", cwd, env: {} },
  })) {
    events.push(event);
  }
  const interceptions = events.filter((e) => e.type === "tool_call" && e.name === "nondelivery_interception");
  assert.equal(interceptions.length, 2, "interception caps at exactly 2 per run");
  const steers = events.filter((e) => e.type === "tool_call" && e.name === "turn_end_steer");
  assert.equal(steers.length, 1, "turn_end_steer still fires its own shot after interceptions");
  const giveUps = events.filter((e) => e.type === "tool_call" && e.name === "give_up_correction_steer");
  assert.equal(giveUps.length, 1, "give_up_correction_steer still fires its own shot after interceptions");
  await rm(cwd, { recursive: true, force: true });
});

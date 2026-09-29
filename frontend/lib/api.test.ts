


import { test } from "node:test";
import assert from "node:assert/strict";
import { apiPath } from "./api";

const ENV_KEY = "NEXT_PUBLIC_API_RUNTIME";

function setRuntime(v: string | undefined) {
  if (v === undefined) delete process.env[ENV_KEY];
  else process.env[ENV_KEY] = v;
}

test("defaults to the v1 router when the flag is unset", () => {
  setRuntime(undefined);
  assert.equal(apiPath("/today"), "/api/v1/today");
});

test("defaults to the v1 router on any non-v2 value", () => {
  setRuntime("v1");
  assert.equal(apiPath("/models"), "/api/v1/models");
  setRuntime("bogus");
  assert.equal(apiPath("/models"), "/api/v1/models");
  setRuntime(undefined);
});

test("points at the v2 router when the flag is v2", () => {
  setRuntime("v2");
  try {
    assert.equal(apiPath("/today"), "/api/today");
    assert.equal(apiPath("/watchlist"), "/api/watchlist");
    assert.equal(apiPath("/sql/rerun"), "/api/sql/rerun");
    assert.equal(apiPath("/datasets/freshness"), "/api/datasets/freshness");
    assert.equal(apiPath("/debate-card/file?name=x"), "/api/debate-card/file?name=x");
  } finally {
    setRuntime(undefined);
  }
});

test("preserves query strings through the mapping", () => {
  setRuntime(undefined);
  assert.equal(
    apiPath("/today?season=2025-26"),
    "/api/v1/today?season=2025-26",
  );
  setRuntime("v2");
  try {
    assert.equal(
      apiPath("/threads/abc/runs?client=xyz"),
      "/api/threads/abc/runs?client=xyz",
    );
  } finally {
    setRuntime(undefined);
  }
});





import {
  appendCachedRun,
  getRuns,
  loadCachedRuns,
  type RunInfo,
} from "./api";

function installLocalStorage() {
  const store = new Map<string, string>();
  const shim = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => { store.set(k, String(v)); },
    removeItem: (k: string) => { store.delete(k); },
    clear: () => store.clear(),
  };
  (globalThis as Record<string, unknown>).localStorage = shim;
  return store;
}

function run(question: string, created_at: string, id?: string): RunInfo {
  return { id, question, answer: `a:${question}`, tables: [], suggestions: [], created_at };
}

test("appendCachedRun persists runs oldest-first and dedupes repeats", () => {
  installLocalStorage();
  appendCachedRun("t-1", run("q1", "2026-09-27T20:00:00Z"));
  appendCachedRun("t-1", run("q2", "2026-09-27T20:01:00Z"));
  appendCachedRun("t-1", run("q2", "2026-09-27T20:01:00Z"));
  const cached = loadCachedRuns("t-1");
  assert.deepEqual(cached.map((r) => r.question), ["q1", "q2"]);
});

test("loadCachedRuns self-heals a stale newest-first cache", () => {
  const store = installLocalStorage();
  const key = "dime_runs__t-9";
  store.set(key, JSON.stringify([
    run("q2", "2026-09-27T20:01:00Z"),
    run("q1", "2026-09-27T20:00:00Z"),
  ]));
  const cached = loadCachedRuns("t-9");
  assert.deepEqual(cached.map((r) => r.question), ["q1", "q2"]);
});

test("getRuns returns oldest-first when the server sends newest-first", async () => {
  installLocalStorage();
  const seen: string[] = [];
  (globalThis as Record<string, unknown>).fetch = async (url: string) => {
    seen.push(String(url));
    return {
      ok: true,
      json: async () => ({
        runs: [
          run("q2", "2026-09-27T20:01:00Z"),
          run("q1", "2026-09-27T20:00:00Z"),
        ],
      }),
    };
  };
  try {
    const runs = await getRuns("t-2");
    assert.deepEqual(runs.map((r) => r.question), ["q1", "q2"]);

    assert.match(seen[0], /\/threads\/t-2\/runs\?client=/);
    assert.doesNotMatch(seen[0], /\$\{/);

    assert.deepEqual(loadCachedRuns("t-2").map((r) => r.question), ["q1", "q2"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns falls back to the local cache after a deploy wipe", async () => {
  installLocalStorage();
  appendCachedRun("t-3", run("q1", "2026-09-27T20:00:00Z"));
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({ runs: [] }),
  });
  try {
    const runs = await getRuns("t-3");
    assert.deepEqual(runs.map((r) => r.question), ["q1"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns merges a partial post-wipe server instead of clobbering local runs", async () => {


  installLocalStorage();
  appendCachedRun("t-4", run("q1", "2026-09-27T20:00:00Z"));
  appendCachedRun("t-4", run("q2", "2026-09-27T20:01:00Z"));
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({
      runs: [run("q2", "2026-09-27T20:01:00Z")],
    }),
  });
  try {
    const runs = await getRuns("t-4");
    assert.deepEqual(runs.map((r) => r.question), ["q1", "q2"]);

    assert.deepEqual(loadCachedRuns("t-4").map((r) => r.question), ["q1", "q2"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns picks up server-only runs this browser never cached", async () => {
  installLocalStorage();
  appendCachedRun("t-5", run("q1", "2026-09-27T20:00:00Z"));
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({
      runs: [
        run("q3", "2026-09-27T20:02:00Z"),
        run("q2", "2026-09-27T20:01:00Z"),
      ],
    }),
  });
  try {
    const runs = await getRuns("t-5");
    assert.deepEqual(runs.map((r) => r.question), ["q1", "q2", "q3"]);
    assert.deepEqual(loadCachedRuns("t-5").map((r) => r.question), ["q1", "q2", "q3"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns dedupes a server run already in the local cache", async () => {
  installLocalStorage();
  appendCachedRun("t-6", run("q1", "2026-09-27T20:00:00Z"));
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({ runs: [run("q1", "2026-09-27T20:00:00Z")] }),
  });
  try {
    const runs = await getRuns("t-6");
    assert.deepEqual(runs.map((r) => r.question), ["q1"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns dedupes a server run whose created_at is skewed vs the local copy", async () => {



  installLocalStorage();
  appendCachedRun("t-7", run("q1", "2026-09-27T20:00:12Z"));
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({ runs: [run("q1", "2026-09-27T20:00:03Z")] }),
  });
  try {
    const runs = await getRuns("t-7");
    assert.deepEqual(runs.map((r) => r.question), ["q1"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns dedupes on run id even when the server timestamp drifts far", async () => {
  installLocalStorage();
  appendCachedRun("t-10", run("q1", "2026-09-27T20:00:00Z", "run-abc"));
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({ runs: [run("q1", "2026-09-27T20:42:00Z", "run-abc")] }),
  });
  try {
    const runs = await getRuns("t-10");
    assert.deepEqual(runs.map((r) => r.question), ["q1"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns keeps a genuinely repeated question outside the skew window", async () => {

  installLocalStorage();
  appendCachedRun("t-11", run("q1", "2026-09-27T20:00:00Z"));
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({ runs: [run("q1", "2026-09-27T20:30:00Z")] }),
  });
  try {
    const runs = await getRuns("t-11");
    assert.deepEqual(runs.map((r) => r.question), ["q1", "q1"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns keeps identical Q/A asked 5 min apart when ids differ", async () => {



  installLocalStorage();
  appendCachedRun("t-12", run("q1", "2026-09-27T20:00:00Z", "run-first"));
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({ runs: [run("q1", "2026-09-27T20:05:00Z", "run-second")] }),
  });
  try {
    const runs = await getRuns("t-12");
    assert.deepEqual(runs.map((r) => r.question), ["q1", "q1"]);
    assert.deepEqual(runs.map((r) => r.id), ["run-first", "run-second"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns collapses on id even when content drifted", async () => {

  installLocalStorage();
  appendCachedRun("t-13", run("q1", "2026-09-27T20:00:00Z", "run-x"));
  const serverRun = run("q1-changed", "2026-09-27T21:00:00Z", "run-x");
  serverRun.answer = "a:q1 (edited)";
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({ runs: [serverRun] }),
  });
  try {
    const runs = await getRuns("t-13");
    assert.equal(runs.length, 1);
    assert.equal(runs[0].id, "run-x");
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("getRuns never merges an id'd run with an id-less legacy row", async () => {


  installLocalStorage();
  appendCachedRun("t-14", run("q1", "2026-09-27T20:00:12Z"));
  (globalThis as Record<string, unknown>).fetch = async () => ({
    ok: true,
    json: async () => ({ runs: [run("q1", "2026-09-27T20:00:03Z", "run-new")] }),
  });
  try {
    const runs = await getRuns("t-14");
    assert.deepEqual(runs.map((r) => r.id), ["run-new", undefined]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("appendCachedRun keeps a repeat question when the run id is new", () => {



  installLocalStorage();
  appendCachedRun("t-15", run("q1", "2026-09-27T20:00:00Z", "run-one"));
  appendCachedRun("t-15", run("q1", "2026-09-27T20:00:01Z", "run-one"));
  appendCachedRun("t-15", run("q1", "2026-09-27T20:00:02Z", "run-two"));
  const cached = loadCachedRuns("t-15");
  assert.deepEqual(cached.map((r) => r.id), ["run-one", "run-two"]);
});






import { postChatStream } from "./api";

const CHAT_RUNTIME_KEY = "NEXT_PUBLIC_CHAT_RUNTIME";

type SseMock = {
  emit: (event: string) => void;
  end: () => void;
};




function installSseMock(): SseMock {
  const encoder = new TextEncoder();
  const queue: Uint8Array[] = [];
  const pending: ((r: { done: boolean; value?: Uint8Array }) => void)[] = [];
  const rejectors: ((e: Error) => void)[] = [];
  const reader = {
    read(): Promise<{ done: boolean; value?: Uint8Array }> {
      const next = queue.shift();
      if (next) return Promise.resolve({ done: false, value: next });
      return new Promise((resolve, reject) => {
        pending.push(resolve);
        rejectors.push(reject);
      });
    },
  };
  const api: SseMock = {
    emit(event: string) {
      const chunk = encoder.encode(
        `event: ${event}\ndata: ${JSON.stringify({})}\n\n`,
      );
      const resolve = pending.shift();
      if (resolve) {
        rejectors.shift();
        resolve({ done: false, value: chunk });
      } else {
        queue.push(chunk);
      }
    },
    end() {
      let resolve = pending.shift();
      while (resolve) {
        rejectors.shift();
        resolve({ done: true });
        resolve = pending.shift();
      }
    },
  };
  (globalThis as Record<string, unknown>).fetch = async (
    _url: string,
    init?: { signal?: AbortSignal },
  ) => {
    init?.signal?.addEventListener(
      "abort",
      () => {
        const err = new DOMException("The operation was aborted.", "AbortError");
        let reject = rejectors.shift();
        while (reject) {
          reject(err);
          reject = rejectors.shift();
        }
      },
      { once: true },
    );
    return {
      ok: true,
      headers: { get: () => "text/event-stream" },
      body: { getReader: () => reader },
    };
  };
  return api;
}

function streamHandlers() {  const events: string[] = [];
  const errors: string[] = [];
  let done = false;
  return {
    events,
    errors,
    handlers: {
      onEvent: (type: string) => {
        events.push(type);
      },
      onDone: () => {
        done = true;
      },
      onError: (message: string) => {
        errors.push(message);
      },
    },
    wasDone: () => done,
  };
}

function setChatRuntime(v: string | undefined) {
  if (v === undefined) delete process.env[CHAT_RUNTIME_KEY];
  else process.env[CHAT_RUNTIME_KEY] = v;
}






async function settle(rounds = 25) {
  for (let i = 0; i < rounds; i++) await Promise.resolve();
}





async function advance(t: { mock: { timers: { tick: (ms: number) => void } } }, ms: number) {
  await settle();
  t.mock.timers.tick(ms);
  await settle();
}

test("watchdog: no bytes for 90s aborts with an idle error (v1)", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval", "Date"] });
  setChatRuntime(undefined);
  installSseMock();
  const s = streamHandlers();
  try {
    const p = postChatStream("q", null, s.handlers);
    await advance(t, 95_000);
    await p;
    assert.deepEqual(s.errors, [
      "No response from the server for 90s. The backend may be down - try again in a moment.",
    ]);
    assert.equal(s.wasDone(), false);
  } finally {
    setChatRuntime(undefined);
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("watchdog: v1 pings-only stream aborts after 3 min with a progress error", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval", "Date"] });
  setChatRuntime(undefined);
  const sse = installSseMock();
  const s = streamHandlers();
  try {
    const p = postChatStream("q", null, s.handlers);


    for (let i = 0; i < 13; i++) {
      sse.emit("ping");
      await advance(t, 15_000);
    }
    await p;
    assert.ok(s.events.every((e) => e === "ping"), "only pings were seen");
    assert.deepEqual(s.errors, [
      "The model stopped making progress for 3 minutes. The run was stopped - try again.",
    ]);
  } finally {
    setChatRuntime(undefined);
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("watchdog: v2 pings-only stream does NOT abort on progress (gating)", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval", "Date"] });
  setChatRuntime("v2");
  const sse = installSseMock();
  const s = streamHandlers();
  try {
    const p = postChatStream("q", null, s.handlers);


    for (let i = 0; i < 13; i++) {
      sse.emit("ping");
      await advance(t, 15_000);
    }
    assert.deepEqual(s.errors, []);

    sse.emit("graph_end");
    await Promise.resolve();
    sse.end();
    await p;
    assert.equal(s.wasDone(), true);
    assert.deepEqual(s.errors, []);
  } finally {
    setChatRuntime(undefined);
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("watchdog: v2 dead connection still aborts on idle after 90s", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval", "Date"] });
  setChatRuntime("v2");
  installSseMock();
  const s = streamHandlers();
  try {
    const p = postChatStream("q", null, s.handlers);
    await advance(t, 95_000);
    await p;
    assert.deepEqual(s.errors, [
      "No response from the server for 90s. The backend may be down - try again in a moment.",
    ]);
  } finally {
    setChatRuntime(undefined);
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

test("watchdog: 8-min absolute ceiling fires even with real events flowing (v1)", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval", "Date"] });
  setChatRuntime(undefined);
  const sse = installSseMock();
  const s = streamHandlers();
  try {
    const p = postChatStream("q", null, s.handlers);


    for (let i = 0; i < 17; i++) {
      sse.emit("message");
      await advance(t, 30_000);
    }
    await p;
    assert.deepEqual(s.errors, [
      "The request timed out after 8 minutes. Try a simpler question or try again.",
    ]);
  } finally {
    setChatRuntime(undefined);
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

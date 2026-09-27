// Tests for the v1 -> v2 frontend cutover path helper (Step 4).
// apiPath() maps every frontend API path onto the v1 or v2 router based
// on NEXT_PUBLIC_API_RUNTIME; default is v1 (zero behavior change).
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

// --- Thread-history load path: local runs cache + oldest-first order ---
// The server session store is wiped on every deploy; the local cache is
// the durable source of truth, and getRuns must return oldest-first
// (the server sends newest-first).
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

function run(question: string, created_at: string): RunInfo {
  return { question, answer: `a:${question}`, tables: [], suggestions: [], created_at };
}

test("appendCachedRun persists runs oldest-first and dedupes repeats", () => {
  installLocalStorage();
  appendCachedRun("t-1", run("q1", "2026-09-27T20:00:00Z"));
  appendCachedRun("t-1", run("q2", "2026-09-27T20:01:00Z"));
  appendCachedRun("t-1", run("q2", "2026-09-27T20:01:00Z")); // duplicate - dropped
  const cached = loadCachedRuns("t-1");
  assert.deepEqual(cached.map((r) => r.question), ["q1", "q2"]);
});

test("loadCachedRuns self-heals a stale newest-first cache", () => {
  const store = installLocalStorage();
  const key = "dime_runs__t-9"; // getClientId() is "" under node
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
    // Thread id and client id are interpolated, not sent as literals.
    assert.match(seen[0], /\/threads\/t-2\/runs\?client=/);
    assert.doesNotMatch(seen[0], /\$\{/);
    // The normalized order is what lands in the cache.
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
    json: async () => ({ runs: [] }), // wiped server
  });
  try {
    const runs = await getRuns("t-3");
    assert.deepEqual(runs.map((r) => r.question), ["q1"]);
  } finally {
    delete (globalThis as Record<string, unknown>).fetch;
  }
});

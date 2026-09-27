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

import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";

function freshDom() {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/" });
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    localStorage: dom.window.localStorage,
  });
  return dom;
}

function sampleBoard() {
  return {
    id: "board-test-1",
    title: "Scoring guards",
    season: "2025-26",
    rows: [
      { player_id: 1628369, name: "Jayson Tatum", team: "BOS" },
      { player_id: 1627759, name: "Jaylen Brown", team: "BOS" },
    ],
    columns: [{ metric_id: "ppg" }, { metric_id: "ts_pct" }],
    cells: {},
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    template_id: "scoring-guards",
  };
}

test("boardIntent strips evaluated output and display caching, keeping pure intent", async () => {
  freshDom();
  const { boardIntent } = await import("./lib/board-objects");
  const board = sampleBoard() as never;
  const intent = boardIntent(board);
  assert.deepEqual(intent, {
    season: "2025-26",
    rows: [{ player_id: 1628369 }, { player_id: 1627759 }],
    columns: [{ metric_id: "ppg" }, { metric_id: "ts_pct" }],
    template_id: "scoring-guards",
  });
  assert.equal(JSON.stringify(intent).includes("cells"), false);
  assert.equal(JSON.stringify(intent).includes("Tatum"), false, "names re-resolve at fill time — never persisted");
});

test("syncBoardObject creates a server object and retains the mapping + owner token", async () => {
  freshDom();
  const posts: { body: { kind: string; payload: { template_id?: string } }; headers: Record<string, string> }[] = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.endsWith("/api/objects") && init?.method === "POST") {
      posts.push({ body: JSON.parse(String(init.body)), headers: Object.fromEntries(Object.entries(init.headers ?? {})) });
      return Response.json({ object_id: "obj-abc", read_token: "read-token-1", owner_token: "owner-token-1" }, { status: 201 });
    }
    throw new Error(`unexpected fetch ${url}`);
  };
  try {
    const { syncBoardObject, boardObjectMapping } = await import("./lib/board-objects");
    const result = await syncBoardObject(sampleBoard() as never);
    assert.deepEqual(result, { objectId: "obj-abc", readToken: "read-token-1" });
    assert.equal(posts.length, 1);
    assert.equal(posts[0].body.kind, "board");
    assert.equal(posts[0].body.payload.template_id, "scoring-guards");
    assert.ok(posts[0].headers["x-dime-owner"], "owner header present");
    assert.equal(boardObjectMapping("board-test-1"), "obj-abc");
    assert.equal(window.localStorage.getItem("dime_object_token:obj-abc"), "owner-token-1");
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("syncBoardObject updates the existing object instead of duplicating on re-sync", async () => {
  freshDom();
  window.localStorage.setItem("dime_board_object:board-test-1", "obj-existing");
  window.localStorage.setItem("dime_object_token:obj-existing", "owner-token-1");
  const calls: { method: string; url: string }[] = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    calls.push({ method: String(init?.method ?? "GET"), url: String(input) });
    if (init?.method === "PATCH") return Response.json({ ok: true });
    return Response.json({ object_id: "obj-should-not-create", read_token: "x", owner_token: "y" }, { status: 201 });
  };
  try {
    const { syncBoardObject } = await import("./lib/board-objects");
    const result = await syncBoardObject(sampleBoard() as never);
    assert.ok(result);
    assert.equal(result?.objectId, "obj-existing");
    assert.equal(calls.length, 1);
    assert.equal(calls[0].method, "PATCH", "existing objects update in place — the live link is stable across edits");
    assert.equal(calls.filter((c) => c.method === "POST").length, 0, "no duplicate object minted");
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("boards without rows or columns never reach the server", async () => {
  freshDom();
  const previousFetch = globalThis.fetch;
  let fetched = false;
  globalThis.fetch = async () => { fetched = true; return Response.json({}); };
  try {
    const { syncBoardObject } = await import("./lib/board-objects");
    const empty = { ...sampleBoard(), rows: [] } as never;
    assert.equal(await syncBoardObject(empty), null);
    assert.equal(fetched, false);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("archiveBoardObject archives server-side and clears the mapping — local copy untouched", async () => {
  freshDom();
  window.localStorage.setItem("dime_board_object:board-test-1", "obj-gone");
  window.localStorage.setItem("dime_object_token:obj-gone", "owner-token-1");
  const patches: unknown[] = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    if (init?.method === "PATCH") { patches.push(JSON.parse(String(init.body))); return Response.json({ ok: true }); }
    throw new Error("unexpected");
  };
  try {
    const { archiveBoardObject, boardObjectMapping } = await import("./lib/board-objects");
    await archiveBoardObject("board-test-1");
    assert.deepEqual(patches, [{ archived: true }]);
    assert.equal(boardObjectMapping("board-test-1"), null);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("boardShareToken resolves for already-synced boards — the mint-at-creation path never dead-ends sharing", async () => {
  freshDom();
  window.localStorage.setItem("dime_board_object:board-test-1", "obj-existing");
  window.localStorage.setItem("dime_object_token:obj-existing", "owner-token-1");
  const calls: { method: string; url: string; headers: unknown }[] = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    calls.push({ method: String(init?.method ?? "GET"), url, headers: init?.headers });
    if (init?.method === "PATCH") return Response.json({ ok: true });
    if (init?.method === undefined || init?.method === "GET") {
      assert.match(url, /\/api\/objects\/obj-existing$/, "recovery must use the owner-token object GET, not the token-stripped list endpoint");
      return Response.json({ object_id: "obj-existing", read_token: "recovered-read-token" });
    }
    throw new Error(`unexpected ${init?.method} ${url}`);
  };
  try {
    const { boardShareToken } = await import("./lib/board-objects");
    const result = await boardShareToken(sampleBoard() as never);
    assert.deepEqual(result, { objectId: "obj-existing", readToken: "recovered-read-token" });
    assert.equal(calls.some((c) => c.url.endsWith("/api/objects") && c.method === "GET"), false, "the list endpoint strips read_token by design — never a recovery source");
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("boardShareToken prefers the locally retained read token without a network round trip", async () => {
  freshDom();
  window.localStorage.setItem("dime_board_object:board-test-1", "obj-existing");
  window.localStorage.setItem("dime_object_token:obj-existing", "owner-token-1");
  window.localStorage.setItem("dime_object_rtoken:obj-existing", "cached-read-token");
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    if (init?.method === "PATCH") return Response.json({ ok: true });
    throw new Error(`unexpected fetch ${String(input)}`);
  };
  try {
    const { boardShareToken } = await import("./lib/board-objects");
    const result = await boardShareToken(sampleBoard() as never);
    assert.deepEqual(result, { objectId: "obj-existing", readToken: "cached-read-token" });
  } finally {
    globalThis.fetch = previousFetch;
  }
});


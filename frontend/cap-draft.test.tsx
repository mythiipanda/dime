import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";

function freshDom() {
  const dom = new JSDOM("", { url: "http://localhost/" });
  Object.assign(globalThis, { window: dom.window, localStorage: dom.window.localStorage });
}

const moves = [{ kind: "trade_out" as const, player: "Player One", amount: 40000000 }];

test("first sync mints a draft object keyed per team+season; reload restores the exact moves", async () => {
  freshDom();
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const previousFetch = globalThis.fetch;
  const stored = { payload: null as unknown };
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    calls.push({ method: String(init?.method ?? "GET"), url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (init?.method === "POST") {
      stored.payload = JSON.parse(String(init.body)).payload;
      return Response.json({ object_id: "obj-draft-1", read_token: "rt", owner_token: "ot" }, { status: 201 });
    }
    if ((init?.method ?? "GET") === "GET") return Response.json({ object_id: "obj-draft-1", payload: stored.payload, archived: false, read_token: "rt" });
    return Response.json({ ok: true });
  };
  try {
    const { syncCapDraft, loadCapDraft } = await import("./lib/cap-draft");
    await syncCapDraft("DAL", "2026-27", moves);
    assert.equal(calls[0].method, "POST", "first sync mints");
    assert.equal(window.localStorage.getItem("dime_cap_draft:DAL:2026-27"), "obj-draft-1");
    const restored = await loadCapDraft("DAL", "2026-27");
    assert.deepEqual(restored?.moves, moves, "reload recovery restores the working draft exactly");
    assert.equal(restored?.groups, undefined, "no groups minted for ungrouped moves");
    assert.equal(await loadCapDraft("NYK", "2026-27"), null, "identity is per team — no clobbering across teams");
    assert.equal(await loadCapDraft("DAL", "2027-28"), null, "identity is per season too");
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("edits update the same object in place — the draft is one live document", async () => {
  freshDom();
  window.localStorage.setItem("dime_cap_draft:DAL:2026-27", "obj-draft-1");
  window.localStorage.setItem("dime_object_token:obj-draft-1", "ot");
  const methods: string[] = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    methods.push(String(init?.method ?? "GET"));
    return Response.json({ ok: true });
  };
  try {
    const { syncCapDraft } = await import("./lib/cap-draft");
    await syncCapDraft("DAL", "2026-27", [...moves, { kind: "trade_in" as const, player: "Player Two" }]);
    assert.deepEqual(methods, ["PATCH"], "update in place, never a duplicate object");
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("clearing all moves archives the draft honestly — reload then shows an empty sheet", async () => {
  freshDom();
  window.localStorage.setItem("dime_cap_draft:DAL:2026-27", "obj-draft-1");
  window.localStorage.setItem("dime_object_token:obj-draft-1", "ot");
  const patches: unknown[] = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    if (init?.method === "PATCH") { patches.push(JSON.parse(String(init.body))); return Response.json({ ok: true }); }
    return Response.json({});
  };
  try {
    const { syncCapDraft, loadCapDraft } = await import("./lib/cap-draft");
    await syncCapDraft("DAL", "2026-27", []);
    assert.deepEqual(patches, [{ archived: true }]);
    assert.equal(window.localStorage.getItem("dime_cap_draft:DAL:2026-27"), null, "mapping cleared after archive");
    assert.equal(await loadCapDraft("DAL", "2026-27"), null);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("sync failures never throw into the UI — the session-state draft keeps working offline", async () => {
  freshDom();
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("offline"); };
  try {
    const { syncCapDraft, loadCapDraft } = await import("./lib/cap-draft");
    await syncCapDraft("DAL", "2026-27", moves);
    assert.equal(await loadCapDraft("DAL", "2026-27"), null);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("groups metadata round-trips through sync and reload", async () => {
  freshDom();
  const previousFetch = globalThis.fetch;
  const stored = { payload: null as unknown };
  globalThis.fetch = async (input, init) => {
    if (init?.method === "POST") {
      stored.payload = JSON.parse(String(init.body)).payload;
      return Response.json({ object_id: "obj-draft-g", read_token: "rt", owner_token: "ot" }, { status: 201 });
    }
    if ((init?.method ?? "GET") === "GET") return Response.json({ object_id: "obj-draft-g", payload: stored.payload, archived: false, read_token: "rt" });
    return Response.json({ ok: true });
  };
  try {
    const { syncCapDraft, loadCapDraft } = await import("./lib/cap-draft");
    const grouped = [
      { kind: "trade_out" as const, player: "Player One", group: "trade-test-1" },
      { kind: "trade_in" as const, player: "Player Two", group: "trade-test-1" },
    ];
    const groups = { "trade-test-1": { partner: "NYK", verdict: true, evaluated_at: "2026-11-27T00:00:00.000Z" } };
    await syncCapDraft("MIA", "2026-27", grouped, groups);
    const restored = await loadCapDraft("MIA", "2026-27");
    assert.deepEqual(restored?.moves, grouped, "group-tagged moves survive the round trip");
    assert.deepEqual(restored?.groups, groups, "group metadata survives the round trip");
  } finally {
    globalThis.fetch = previousFetch;
  }
});

import { describe, it, afterEach } from "node:test";
import * as assert from "node:assert";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import ExploreFeed from "./components/ExploreFeed";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
});
const win = dom.window as unknown as Window & typeof globalThis;
const gx = globalThis as unknown as Record<string, unknown>;
gx.window = win;
gx.document = win.document;
Object.defineProperty(globalThis, "navigator", {
  value: win.navigator,
  configurable: true,
  writable: true,
});
gx.HTMLElement = win.HTMLElement;
gx.Element = win.Element;
gx.Node = win.Node;
gx.DocumentFragment = win.DocumentFragment;
gx.Text = win.Text;
gx.Comment = win.Comment;
gx.Event = win.Event;
gx.MouseEvent = win.MouseEvent;
gx.CustomEvent = win.CustomEvent;
gx.getComputedStyle = win.getComputedStyle.bind(win);
gx.requestAnimationFrame = (cb: FrameRequestCallback) => setTimeout(cb, 0);
gx.IS_REACT_ACT_ENVIRONMENT = true;

type Call = { url: string; method: string };

let calls: Call[] = [];
let roots: Root[] = [];
let mounts: HTMLElement[] = [];

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function envelope(rows: unknown) {
  return {
    ok: true,
    json: async () => ({ ok: true, rows }),
  };
}

const TODAY_ROWS = {
  last_night: [],
  tonight: [],
  movers: [{ PLAYER: "Test Player", TEAM: "BOS", RANK_CHANGE: "2", PTS_CHANGE: 1.5 }],
  streaks: [{ TEAM: "Boston Celtics", W: 50, L: 20, STREAK: "W5" }],
};

const WATCH_ROWS = [
  {
    entity_type: "player",
    entity_id: "p1",
    snapshot: { found: true, player: "Watch Guy", team: "LAL", ppg: 20.5 },
  },
];

function mockFeedFetch(
  todayGate: Promise<unknown>,
  watchGate: Promise<unknown>,
) {
  calls = [];
  gx.fetch = ((url: string, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, method: init?.method || "GET" });
    if (u.includes("/today?")) return todayGate.then(() => envelope(TODAY_ROWS));
    if (u.includes("/watchlist")) return watchGate.then(() => envelope(WATCH_ROWS));
    return Promise.reject(new TypeError("unexpected " + u));
  }) as unknown as typeof fetch;
}

async function mount() {
  const el = win.document.createElement("div");
  win.document.body.appendChild(el);
  mounts.push(el);
  const root = createRoot(el);
  roots.push(root);
  await act(async () => {
    root.render(
      React.createElement(ExploreFeed, {
        onAsk: () => {},
        onSelect: () => {},
      }),
    );
  });
  return el;
}

async function tick(ms = 10) {
  await act(async () => {
    await new Promise((r) => setTimeout(r, ms));
  });
}

afterEach(async () => {
  await act(async () => {
    for (const r of roots) r.unmount();
  });
  for (const m of mounts) m.remove();
  roots = [];
  mounts = [];
});

describe("explore feed loading", () => {
  it("requests today and watchlist in parallel", async () => {
    const today = deferred<unknown>();
    const watch = deferred<unknown>();
    mockFeedFetch(today.promise, watch.promise);
    await mount();
    await tick();
    const urls = calls.map((c) => c.url);
    assert.ok(urls.some((u) => u.includes("/today?")), "today not requested");
    assert.ok(urls.some((u) => u.includes("/watchlist")), "watchlist not requested until today resolves");
    today.resolve(null);
    watch.resolve(null);
    await tick();
  });

  it("shows movers first, then merges the watchlist", async () => {
    const today = deferred<unknown>();
    const watch = deferred<unknown>();
    mockFeedFetch(today.promise, watch.promise);
    const el = await mount();
    await tick();
    today.resolve(null);
    await tick(50);
    assert.ok(el.textContent?.includes("Test Player"), "movers missing:\n" + el.textContent);
    assert.ok(!el.textContent?.includes("Watch Guy"), "watchlist shown before it resolved");
    watch.resolve(null);
    await tick(50);
    assert.ok(el.textContent?.includes("Watch Guy"), "watchlist never merged:\n" + el.textContent);
    assert.ok(el.textContent?.includes("Test Player"), "movers lost after merge");
  });

  it("shows nothing when today fails, even if the watchlist succeeds", async () => {
    const today = deferred<unknown>();
    const watch = deferred<unknown>();
    mockFeedFetch(today.promise, watch.promise);
    const el = await mount();
    await tick();
    today.reject(new TypeError("fetch failed"));
    watch.resolve(null);
    await tick(50);
    assert.equal(el.textContent, "");
  });
});

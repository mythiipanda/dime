import { describe, it, afterEach } from "node:test";
import * as assert from "node:assert";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import DataArtifacts from "./components/DataArtifacts";
import BriefsPage from "./app/briefs/page";
import { listBriefs, saveBrief } from "./lib/briefs";
import type { AiMessage } from "./lib/chat";

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

let roots: Root[] = [];
let mounts: HTMLElement[] = [];

const PREVIEW_ROWS = {
  game: { away: "BOS", home: "NYK", date: "Oct 9", arena: "MSG" },
  form: { away: { record: "2-1" }, home: { record: "3-0" } },
};

function previewAi(): AiMessage {
  return {
    text: "done",
    done: true,
    nodes: {
      analytics: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: [
          {
            tool: "get_matchup_preview",
            rows: PREVIEW_ROWS,
          } as never,
        ],
      },
    },
  };
}

async function mountEl(el: React.ReactElement) {
  const host = win.document.createElement("div");
  win.document.body.appendChild(host);
  mounts.push(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(el);
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 80));
  });
  return host;
}

function buttons(host: HTMLElement, name: string): HTMLButtonElement[] {
  return [...host.querySelectorAll("button")].filter((b) =>
    (b.textContent || "").includes(name),
  ) as HTMLButtonElement[];
}

afterEach(async () => {
  await act(async () => {
    for (const r of roots) r.unmount();
  });
  for (const m of mounts) m.remove();
  roots = [];
  mounts = [];
  win.localStorage.clear();
  win.sessionStorage.clear();
});

function isolateFetch(impl: (url: string) => Promise<unknown>) {
  const prev = (globalThis as Record<string, unknown>).fetch;
  (globalThis as Record<string, unknown>).fetch = impl as unknown as typeof fetch;
  return () => {
    if (prev === undefined) delete (globalThis as Record<string, unknown>).fetch;
    else (globalThis as Record<string, unknown>).fetch = prev;
  };
}

describe("matchup brief doc", () => {
  it("saves a cited brief from a matchup answer", async () => {
    const restore = isolateFetch(() => Promise.reject(new TypeError("offline")));
    try {
      const host = await mountEl(
        React.createElement(DataArtifacts, {
          ai: previewAi(),
          question: "How do Boston and New York match up Friday?",
        }),
      );
      assert.equal(buttons(host, "Save brief").length, 1);
      await act(async () => {
        buttons(host, "Save brief")[0].click();
        await new Promise((r) => setTimeout(r, 60));
      });
      assert.ok(host.textContent?.includes("Open briefs"));
      const docs = listBriefs();
      assert.equal(docs.length, 1);
      assert.ok(docs[0].title.includes("BOS"));
      assert.deepEqual(docs[0].rows, PREVIEW_ROWS);
      assert.equal(docs[0].packHash, null);
    } finally {
      restore();
    }
  });

  it("save captures the current pack hash", async () => {
    const prev = (globalThis as Record<string, unknown>).fetch;
    (globalThis as Record<string, unknown>).fetch = (async (url: string) => {
      if (String(url).includes("/api/revision")) {
        return { ok: true, json: async () => ({ revision: "abc123" }) };
      }
      throw new TypeError("unexpected " + url);
    }) as unknown as typeof fetch;
    try {
      const host = await mountEl(
        React.createElement(DataArtifacts, {
          ai: previewAi(),
          question: "How do Boston and New York match up Friday?",
        }),
      );
      await act(async () => {
        buttons(host, "Save brief")[0].click();
        await new Promise((r) => setTimeout(r, 60));
      });
      assert.equal(listBriefs()[0]?.packHash, "abc123");
    } finally {
      if (prev === undefined) delete (globalThis as Record<string, unknown>).fetch;
      else (globalThis as Record<string, unknown>).fetch = prev;
    }
  });

  it("viewer warns when the saved pack hash differs", async () => {
    const prev = (globalThis as Record<string, unknown>).fetch;
    (globalThis as Record<string, unknown>).fetch = (async (url: string) => {
      if (String(url).includes("/api/revision")) {
        return { ok: true, json: async () => ({ revision: "new-hash" }) };
      }
      throw new TypeError("unexpected " + url);
    }) as unknown as typeof fetch;
    try {
      saveBrief({
        title: "BOS at NYK",
        question: "How do Boston and New York match up Friday?",
        rows: PREVIEW_ROWS,
        packHash: "old-hash",
      });
      const host = await mountEl(React.createElement(BriefsPage));
      await act(async () => {
        buttons(host, "BOS at NYK")[0].click();
        await new Promise((r) => setTimeout(r, 30));
      });
      assert.ok(host.textContent?.includes("may be out of date"));
    } finally {
      if (prev === undefined) delete (globalThis as Record<string, unknown>).fetch;
      else (globalThis as Record<string, unknown>).fetch = prev;
    }
  });

  it("viewer stays quiet when hashes match", async () => {
    const prev = (globalThis as Record<string, unknown>).fetch;
    (globalThis as Record<string, unknown>).fetch = (async () => ({
      ok: true,
      json: async () => ({ revision: "same-hash" }),
    })) as unknown as typeof fetch;
    try {
      saveBrief({
        title: "BOS at NYK",
        question: "How do Boston and New York match up Friday?",
        rows: PREVIEW_ROWS,
        packHash: "same-hash",
      });
      const host = await mountEl(React.createElement(BriefsPage));
      await act(async () => {
        buttons(host, "BOS at NYK")[0].click();
        await new Promise((r) => setTimeout(r, 30));
      });
      assert.ok(!host.textContent?.includes("may be out of date"));
    } finally {
      if (prev === undefined) delete (globalThis as Record<string, unknown>).fetch;
      else (globalThis as Record<string, unknown>).fetch = prev;
    }
  });

  it("briefs page lists, opens, and re-runs a saved brief", async () => {
    const restore = isolateFetch(() => Promise.reject(new TypeError("offline")));
    try {
      saveBrief({
        title: "BOS at NYK",
        question: "How do Boston and New York match up Friday?",
        rows: PREVIEW_ROWS,
      });
      const host = await mountEl(React.createElement(BriefsPage));
      assert.ok(host.textContent?.includes("BOS at NYK"));
      await act(async () => {
        buttons(host, "BOS at NYK")[0].click();
        await new Promise((r) => setTimeout(r, 30));
      });
      assert.ok(host.textContent?.includes("NYK"));
      await act(async () => {
        buttons(host, "Re-run")[0].click();
        await new Promise((r) => setTimeout(r, 30));
      });
      assert.equal(win.sessionStorage.getItem("dime_rerun"), "How do Boston and New York match up Friday?");
    } finally {
      restore();
    }
  });
});

import { describe, it, afterEach } from "node:test";
import * as assert from "node:assert";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import DataArtifacts from "./components/DataArtifacts";
import BriefsPage, { BriefEditor } from "./app/briefs/page";
import { briefFieldDiff, listBriefs, saveBrief, updateBrief } from "./lib/briefs";
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

  it("editor fields render the saved values with no conflict notice", async () => {
    saveBrief({
      title: "BOS at NYK",
      question: "How do Boston and New York match up Friday?",
      rows: PREVIEW_ROWS,
    });
    const host = await mountEl(React.createElement(BriefsPage));
    await act(async () => {
      buttons(host, "BOS at NYK")[0].click();
      await new Promise((r) => setTimeout(r, 30));
    });
    const titleBox = host.querySelector(
      'input[aria-label="Brief title"]',
    ) as HTMLInputElement | null;
    const questionBox = host.querySelector(
      'input[aria-label="Brief question"]',
    ) as HTMLInputElement | null;
    assert.ok(titleBox, "title field missing");
    assert.ok(questionBox, "question field missing");
    assert.equal(titleBox.value, "BOS at NYK");
    assert.equal(questionBox.value, "How do Boston and New York match up Friday?");
    assert.ok(!host.textContent?.includes("Brief changed elsewhere"));
    assert.equal(buttons(host, "Reload saved").length, 0);
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

  it("briefFieldDiff names exactly the changed regions", () => {
    const base = { title: "BOS at NYK", question: "How do they match up?" };
    assert.deepEqual(briefFieldDiff(base, base), []);
    assert.deepEqual(briefFieldDiff(base, { ...base, title: "LAL at BOS" }), ["title"]);
    assert.deepEqual(briefFieldDiff(base, { ...base, question: "New question?" }), ["question"]);
    assert.deepEqual(
      briefFieldDiff(base, { title: "LAL at BOS", question: "New question?" }),
      ["title", "question"],
    );
  });

  it("clean remote write adopts values and flashes the changed region", async () => {
    const doc = saveBrief({
      title: "BOS at NYK",
      question: "How do Boston and New York match up Friday?",
      rows: PREVIEW_ROWS,
    });
    const host = await mountEl(
      React.createElement(BriefEditor, { doc, onSaved: () => {}, pollMs: 25 }),
    );
    await act(async () => {
      updateBrief(doc.id, { title: "LAL at BOS" }, 1);
      await new Promise((r) => setTimeout(r, 150));
    });
    const titleBox = host.querySelector('input[aria-label="Brief title"]') as HTMLInputElement;
    const questionBox = host.querySelector('input[aria-label="Brief question"]') as HTMLInputElement;
    assert.equal(titleBox.value, "LAL at BOS");
    assert.equal(questionBox.value, "How do Boston and New York match up Friday?");
    assert.ok((titleBox.getAttribute("style") || "").includes("bg-selected"));
    assert.ok(!(questionBox.getAttribute("style") || "").includes("bg-selected"));
    assert.ok(!host.textContent?.includes("Brief changed elsewhere"));
  });

  it("flash settles back to the plain field after the sweep", async () => {
    const doc = saveBrief({
      title: "BOS at NYK",
      question: "How do Boston and New York match up Friday?",
      rows: PREVIEW_ROWS,
    });
    const host = await mountEl(
      React.createElement(BriefEditor, { doc, onSaved: () => {}, pollMs: 25 }),
    );
    await act(async () => {
      updateBrief(doc.id, { question: "New question?" }, 1);
      await new Promise((r) => setTimeout(r, 150));
    });
    const questionBox = host.querySelector('input[aria-label="Brief question"]') as HTMLInputElement;
    assert.ok((questionBox.getAttribute("style") || "").includes("bg-selected"));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 1700));
    });
    assert.ok(!(questionBox.getAttribute("style") || "").includes("bg-selected"));
    assert.equal(questionBox.value, "New question?");
  });

  it("remote write with identical content adopts silently with no flash", async () => {
    const doc = saveBrief({
      title: "BOS at NYK",
      question: "How do Boston and New York match up Friday?",
      rows: PREVIEW_ROWS,
    });
    const host = await mountEl(
      React.createElement(BriefEditor, { doc, onSaved: () => {}, pollMs: 25 }),
    );
    await act(async () => {
      updateBrief(doc.id, { title: "BOS at NYK" }, 1);
      await new Promise((r) => setTimeout(r, 150));
    });
    const titleBox = host.querySelector('input[aria-label="Brief title"]') as HTMLInputElement;
    assert.equal(titleBox.value, "BOS at NYK");
    assert.ok(!(titleBox.getAttribute("style") || "").includes("bg-selected"));
  });

  it("cross-tab storage event adopts the remote write without waiting for poll", async () => {
    const doc = saveBrief({
      title: "BOS at NYK",
      question: "How do Boston and New York match up Friday?",
      rows: PREVIEW_ROWS,
    });
    const host = await mountEl(
      React.createElement(BriefEditor, { doc, onSaved: () => {}, pollMs: 60000 }),
    );
    await act(async () => {
      updateBrief(doc.id, { title: "NYK at MIA" }, 1);
      win.dispatchEvent(new win.Event("storage"));
      await new Promise((r) => setTimeout(r, 60));
    });
    const titleBox = host.querySelector('input[aria-label="Brief title"]') as HTMLInputElement;
    assert.equal(titleBox.value, "NYK at MIA");
    assert.ok((titleBox.getAttribute("style") || "").includes("bg-selected"));
  });
});

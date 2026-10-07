import { describe, it, afterEach } from "node:test";
import * as assert from "node:assert";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import ArtifactCanvas from "./components/ArtifactCanvas";
import DataArtifacts from "./components/DataArtifacts";
import {
  briefViewerSeen,
  markBriefViewerSeen,
  shouldAutoOpenBrief,
} from "./lib/briefs";
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
gx.Event = win.Event;
gx.MouseEvent = win.MouseEvent;
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

describe("brief auto-open governance", () => {
  it("opens once: unseen plus quiet panel", () => {
    assert.equal(shouldAutoOpenBrief(false, false), true);
    assert.equal(shouldAutoOpenBrief(true, false), false);
    assert.equal(shouldAutoOpenBrief(false, true), false);
    assert.equal(shouldAutoOpenBrief(true, true), false);
  });

  it("seen flag round-trips through storage", () => {
    assert.equal(briefViewerSeen(), false);
    markBriefViewerSeen();
    assert.equal(briefViewerSeen(), true);
  });

  it("first save opens the brief panel once", async () => {
    const prev = gx.fetch;
    gx.fetch = (() => Promise.reject(new TypeError("offline"))) as unknown as typeof fetch;
    try {
      const opened: unknown[] = [];
      const host = await mountEl(
        React.createElement(DataArtifacts, {
          ai: previewAi(),
          question: "How do Boston and New York match up Friday?",
          onOpenArtifact: (a: unknown) => opened.push(a),
        }),
      );
      assert.equal(buttons(host, "Save brief").length, 1);
      await act(async () => {
        buttons(host, "Save brief")[0].click();
        await new Promise((r) => setTimeout(r, 120));
      });
      assert.equal(opened.length, 1);
      assert.equal((opened[0] as { tool: string }).tool, "brief");
      assert.ok(((opened[0] as { title: string }).title || "").includes("BOS"));
    } finally {
      if (prev === undefined) delete gx.fetch;
      else gx.fetch = prev;
    }
  });

  it("a seen viewer never pops the panel on save", async () => {
    markBriefViewerSeen();
    const prev = gx.fetch;
    gx.fetch = (() => Promise.reject(new TypeError("offline"))) as unknown as typeof fetch;
    try {
      const opened: unknown[] = [];
      const host = await mountEl(
        React.createElement(DataArtifacts, {
          ai: previewAi(),
          question: "How do Boston and New York match up Friday?",
          onOpenArtifact: (a: unknown) => opened.push(a),
        }),
      );
      await act(async () => {
        buttons(host, "Save brief")[0].click();
        await new Promise((r) => setTimeout(r, 120));
      });
      assert.equal(opened.length, 0);
      assert.ok(host.textContent?.includes("Open briefs"));
    } finally {
      if (prev === undefined) delete gx.fetch;
      else gx.fetch = prev;
    }
  });

  it("an open panel never gets yanked by a later save", async () => {
    const prev = gx.fetch;
    gx.fetch = (() => Promise.reject(new TypeError("offline"))) as unknown as typeof fetch;
    try {
      const opened: unknown[] = [];
      const host = await mountEl(
        React.createElement(DataArtifacts, {
          ai: previewAi(),
          question: "How do Boston and New York match up Friday?",
          onOpenArtifact: (a: unknown) => opened.push(a),
          activeArtifactId: "get_leaders-3",
        }),
      );
      await act(async () => {
        buttons(host, "Save brief")[0].click();
        await new Promise((r) => setTimeout(r, 120));
      });
      assert.equal(opened.length, 0);
    } finally {
      if (prev === undefined) delete gx.fetch;
      else gx.fetch = prev;
    }
  });

  it("brief artifact renders the matchup preview in the panel", async () => {
    const host = await mountEl(
      React.createElement(ArtifactCanvas, {
        artifact: {
          id: "brief-b-1",
          tool: "brief",
          title: "BOS at NYK",
          rows: PREVIEW_ROWS,
        },
        onClose: () => {},
      }),
    );
    assert.ok(host.textContent?.includes("BOS at NYK"));
    assert.ok(host.textContent?.includes("NYK"));
  });
});

describe("brief auto-open race hardening", () => {
  function deferredFetch() {
    let reject!: (e: unknown) => void;
    const impl = () => new Promise((_, rej) => { reject = rej; });
    return { impl, fire: () => reject(new TypeError("offline")) };
  }
  function artifactProps(extra: Record<string, unknown> = {}) {
    return {
      ai: previewAi(),
      question: "How do Boston and New York match up Friday?",
      ...extra,
    };
  }
  it("a panel opened mid-save is not replaced when the save lands", async () => {
    const gate = deferredFetch();
    const prev = gx.fetch;
    gx.fetch = gate.impl as unknown as typeof fetch;
    try {
      const opened: unknown[] = [];
      const host = await mountEl(
        React.createElement(DataArtifacts, artifactProps({
          onOpenArtifact: (a: unknown) => opened.push(a),
        }) as never),
      );
      buttons(host, "Save brief")[0].click();
      const root = roots[roots.length - 1];
      await act(async () => {
        root.render(
          React.createElement(DataArtifacts, artifactProps({
            onOpenArtifact: (a: unknown) => opened.push(a),
            activeArtifactId: "get_leaders-3",
          }) as never),
        );
      });
      await act(async () => {
        gate.fire();
        await new Promise((r) => setTimeout(r, 120));
      });
      assert.equal(opened.length, 0);
      assert.ok(host.textContent?.includes("Open briefs"));
    } finally {
      if (prev === undefined) delete gx.fetch;
      else gx.fetch = prev;
    }
  });
  it("viewer-seen flipping mid-save suppresses the pop", async () => {
    const gate = deferredFetch();
    const prev = gx.fetch;
    gx.fetch = gate.impl as unknown as typeof fetch;
    try {
      const opened: unknown[] = [];
      const host = await mountEl(
        React.createElement(DataArtifacts, artifactProps({
          onOpenArtifact: (a: unknown) => opened.push(a),
        }) as never),
      );
      buttons(host, "Save brief")[0].click();
      markBriefViewerSeen();
      await act(async () => {
        gate.fire();
        await new Promise((r) => setTimeout(r, 120));
      });
      assert.equal(opened.length, 0);
      assert.ok(host.textContent?.includes("Open briefs"));
    } finally {
      if (prev === undefined) delete gx.fetch;
      else gx.fetch = prev;
    }
  });
});

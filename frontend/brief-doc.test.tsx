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

describe("matchup brief doc", () => {
  it("saves a cited brief from a matchup answer", async () => {
    const host = await mountEl(
      React.createElement(DataArtifacts, {
        ai: previewAi(),
        question: "How do Boston and New York match up Friday?",
      }),
    );
    assert.equal(buttons(host, "Save brief").length, 1);
    await act(async () => {
      buttons(host, "Save brief")[0].click();
      await new Promise((r) => setTimeout(r, 30));
    });
    assert.ok(host.textContent?.includes("Open briefs"));
    const docs = listBriefs();
    assert.equal(docs.length, 1);
    assert.ok(docs[0].title.includes("BOS"));
    assert.deepEqual(docs[0].rows, PREVIEW_ROWS);
  });

  it("briefs page lists, opens, and re-runs a saved brief", async () => {
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
  });
});

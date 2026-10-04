import { describe, it, afterEach } from "node:test";
import * as assert from "node:assert";
import { JSDOM } from "jsdom";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import CitedAnswerText, { flagEntry } from "./components/CitedAnswerText";
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

function aiWith(carry: unknown, tables: unknown[]): AiMessage {
  return {
    text: "answer",
    done: true,
    carry: carry as AiMessage["carry"],
    nodes: {
      analytics: {
        status: "complete",
        thoughts: [],
        toolCalls: [],
        toolResults: [],
        tables: tables as never,
      },
    },
  };
}

const TABLES = [
  {
    output_id: "NET_RATING",
    subject_type: "team",
    subject_id: "BOS",
    value: "9.4",
    unit: "points_per_100_possessions",
    provenance: { capability: "team_ratings", season: "2024-25" },
  },
  {
    output_id: "OFF_RATING",
    subject_type: "team",
    subject_id: "BOS",
    value: "118.2",
    unit: "points_per_100_possessions",
    provenance: { capability: "team_ratings", season: "2024-25" },
  },
];

const TEXT = "Boston finished with a 9.4 net rating and a 118.2 offensive rating.";

async function mount(text: string = TEXT) {
  const el = win.document.createElement("div");
  win.document.body.appendChild(el);
  mounts.push(el);
  const root = createRoot(el);
  roots.push(root);
  await act(async () => {
    root.render(
      React.createElement(CitedAnswerText, {
        text,
        ai: aiWith({ verification: "pass", verified_claims: 2, gaps: [] }, TABLES),
      }),
    );
  });
  return el;
}

function buttons(el: HTMLElement, name: string): HTMLButtonElement[] {
  return [...el.querySelectorAll("button")].filter((b) =>
    (b.textContent || "").includes(name),
  ) as HTMLButtonElement[];
}

async function tick(ms = 20) {
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

describe("claim accept and flag", () => {
  it("flag entries carry exact claim identity and nothing else", () => {
    assert.deepEqual(
      flagEntry(
        { key: "k", index: 0, subject: "Boston", stat: "net rating", value: "9.4", origin: "Team ratings" },
        "2026-10-04T00:00:00.000Z",
      ),
      {
        stat: "net rating",
        subject: "Boston",
        value: "9.4",
        source: "Team ratings",
        timestamp: "2026-10-04T00:00:00.000Z",
      },
    );
  });

  it("open rows offer accept and flag", async () => {
    const el = await mount();
    await tick();
    const markers = el.querySelectorAll(".cite-marker");
    assert.equal(markers.length, 2);
    await act(async () => {
      (markers[0] as HTMLButtonElement).click();
    });
    await tick();
    assert.equal(buttons(el, "Accept").length, 1);
    assert.equal(buttons(el, "Flag").length, 1);
  });

  it("flagging records the claim and offers the log download", async () => {
    const el = await mount();
    await tick();
    await act(async () => {
      (el.querySelector(".cite-marker") as HTMLButtonElement).click();
    });
    await tick();
    await act(async () => {
      buttons(el, "Flag")[0].click();
    });
    await tick();
    assert.ok(el.textContent?.includes("Flagged"));
    assert.equal(buttons(el, "Download log (1)").length, 1);
  });

  it("accepting hides that anchor but keeps its number", async () => {
    const el = await mount();
    await tick();
    await act(async () => {
      (el.querySelector(".cite-marker") as HTMLButtonElement).click();
    });
    await tick();
    await act(async () => {
      buttons(el, "Accept")[0].click();
    });
    await tick();
    assert.equal(el.querySelectorAll(".cite-marker").length, 1);
    assert.ok(el.textContent?.includes("9.4"));
    assert.ok(el.textContent?.includes("118.2"));
  });
});

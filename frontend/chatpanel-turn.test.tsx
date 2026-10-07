import test from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import ChatPanel, { AiTurnBody } from "./components/ChatPanel";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/?tab=chat",
});
const gx = globalThis as unknown as Record<string, unknown>;
gx.window = dom.window;
gx.document = dom.window.document;
gx.HTMLElement = dom.window.HTMLElement;
gx.Element = dom.window.Element;
gx.Node = dom.window.Node;
gx.Event = dom.window.MouseEvent;
gx.localStorage = dom.window.localStorage;
gx.sessionStorage = dom.window.sessionStorage;
gx.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
gx.requestAnimationFrame = (cb: FrameRequestCallback) => setTimeout(cb, 0);
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
gx.IS_REACT_ACT_ENVIRONMENT = true;

function stubFetch() {
  const prev = gx.fetch;
  gx.fetch = (async (url: string) => {
    if (String(url).includes("/models")) {
      return { ok: true, json: async () => ({ models: [{ id: "m1", engine: "e", default: true }], available: {} }) };
    }
    if (String(url).includes("/runs")) {
      return {
        ok: true,
        json: async () => ({
          runs: [
            {
              question: "Who leads in assists?",
              answer: "Trae Young leads at 11.7 assists per game.",
              tables: [],
              suggestions: [],
            },
          ],
        }),
      };
    }
    throw new TypeError("unexpected " + url);
  }) as unknown as typeof fetch;
  return () => {
    if (prev === undefined) delete gx.fetch;
    else gx.fetch = prev;
  };
}

test("ai turn without ai renders the legacy answer body", async () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(React.createElement(AiTurnBody, { m: { role: "ai", text: "plain answer" } }));
    await new Promise((r) => setTimeout(r, 60));
  });
  assert.ok(container.textContent?.includes("plain answer"));
  await act(async () => {
    root.unmount();
  });
  container.remove();
});

test("chat thread mounts exactly one answer body per ai message", async () => {
  const restore = stubFetch();
  try {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => {
      root.render(React.createElement(ChatPanel, { thread: "t", onRunDone: () => {} }));
      await new Promise((r) => setTimeout(r, 300));
    });
    const bodies = [...container.querySelectorAll(".chat-ai-message")];
    assert.equal(bodies.length, 1);
    const hits = bodies[0].textContent?.match(/Trae Young leads at 11\.7 assists per game\./g) || [];
    assert.equal(hits.length, 1);
    await act(async () => {
      root.unmount();
    });
    container.remove();
    winLocalClear();
  } finally {
    restore();
  }
});

function winLocalClear() {
  (globalThis as unknown as { localStorage: Storage }).localStorage.clear();
  (globalThis as unknown as { sessionStorage: Storage }).sessionStorage.clear();
}

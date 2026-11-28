import test from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";

let sharedStorage: Storage | null = null;

async function boot(thread: string) {
  const dom = new JSDOM("<div id='root'></div>", { url: `http://localhost/?tab=chat&thread=${thread}` });
  if (!sharedStorage) sharedStorage = dom.window.localStorage;
  Object.defineProperty(dom.window, "localStorage", { value: sharedStorage, configurable: true });
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    HTMLElement: dom.window.HTMLElement,
    Element: dom.window.Element,
    Node: dom.window.Node,
    localStorage: sharedStorage,
    IS_REACT_ACT_ENVIRONMENT: true,
  });
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (input) => {
    const url = String(input);
    if (url.includes("/models")) return Response.json({ ok: true, models: [{ id: "test:model", label: "Test model", available: true }], providers: ["test"] });
    if (url.includes("/threads") || url.includes("/runs")) return Response.json({ ok: true, runs: [], threads: [] });
    return Response.json({ ok: true });
  };
  const { ChatView } = await import("./components/shell/ChatView");
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  return { dom, host, root, ChatView, restore: () => { globalThis.fetch = previousFetch; } };
}

async function flush(ms = 40) {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)); });
}

test("unsent drafts survive remount (navigation/reload) and are keyed per thread", async () => {
  const first = await boot("thread-a");
  try {
    await act(async () => first.root.render(<first.ChatView thread="thread-a" replay={null} onRunDone={() => {}} />));
    await flush();
    const suggestion = [...first.host.querySelectorAll("button")].find((b) => (b.textContent ?? "").includes("Can Miami aggregate"));
    assert.ok(suggestion, "suggested prompts render in the empty state");
    await act(async () => (suggestion as HTMLElement).click());
    await flush();
    assert.equal(first.dom.window.localStorage.getItem("dime.chat-draft:thread-a")?.includes("Can Miami aggregate"), true, "draft persisted on change");
    await act(async () => first.root.unmount());

    const second = await boot("thread-a");
    try {
      await act(async () => second.root.render(<second.ChatView thread="thread-a" replay={null} onRunDone={() => {}} />));
      await flush();
      const textarea = second.host.querySelector("textarea") as HTMLTextAreaElement | null;
      assert.ok(textarea, "composer renders");
      assert.ok(textarea.value.includes("Can Miami aggregate"), `draft restored after remount, got "${textarea.value}"`);
    } finally {
      await act(async () => second.root.unmount());
      second.restore();
    }

    const other = await boot("thread-b");
    try {
      await act(async () => other.root.render(<other.ChatView thread="thread-b" replay={null} onRunDone={() => {}} />));
      await flush();
      const textarea = other.host.querySelector("textarea") as HTMLTextAreaElement | null;
      assert.ok(textarea && !textarea.value.includes("Can Miami aggregate"), "thread-switch does not leak the other thread's draft");
    } finally {
      await act(async () => other.root.unmount());
      other.restore();
    }
  } finally {
    first.restore();
  }
});

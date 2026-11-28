import test from "node:test";
import assert from "node:assert/strict";
import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";

test("normalizeFailureCopy maps raw browser fetch strings, leaves honest copy verbatim", async () => {
  const { normalizeFailureCopy } = await import("./lib/failure-copy");
  const human = "The network connection dropped before the run finished.";
  assert.equal(normalizeFailureCopy("Failed to fetch"), human);
  assert.equal(normalizeFailureCopy("NetworkError when attempting to fetch resource."), human);
  assert.equal(normalizeFailureCopy("Load failed"), human);
  assert.equal(normalizeFailureCopy("Could not reach the Dime backend. Check your connection and try again."), "Could not reach the Dime backend. Check your connection and try again.");
  assert.equal(normalizeFailureCopy("quota exceeded for this model"), "quota exceeded for this model");
});

async function boot(thread: string, streamResponses: Array<() => Response>) {
  const dom = new JSDOM("<div id='root'></div>", { url: `http://localhost/?tab=chat&thread=${thread}` });
  Object.assign(globalThis, {
    window: dom.window,
    document: dom.window.document,
    HTMLElement: dom.window.HTMLElement,
    Element: dom.window.Element,
    Node: dom.window.Node,
    localStorage: dom.window.localStorage,
    IS_REACT_ACT_ENVIRONMENT: true,
  });
  dom.window.matchMedia = dom.window.matchMedia ?? ((query: string) => ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, onchange: null, dispatchEvent: () => false }) as MediaQueryList);
  Object.assign(globalThis, { matchMedia: dom.window.matchMedia });
  if (!dom.window.Element.prototype.scrollTo) dom.window.Element.prototype.scrollTo = () => {};
  const previousFetch = globalThis.fetch;
  let streamCalls = 0;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("/chat/stream")) {
      const responder = streamResponses[Math.min(streamCalls, streamResponses.length - 1)];
      streamCalls += 1;
      return responder();
    }
    if (url.includes("/models")) return Response.json({ ok: true, models: [{ id: "test:model", label: "Test model", available: true }], providers: ["test"] });
    if (url.includes("/threads") || url.includes("/runs")) return Response.json({ ok: true, runs: [], threads: [] });
    return Response.json({ ok: true });
    void init;
  };
  const { ChatView } = await import("./components/shell/ChatView");
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  return { dom, host, root, ChatView, calls: () => streamCalls, restore: () => { globalThis.fetch = previousFetch; } };
}

async function flush(ms = 60) {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)); });
}

const failStream = () => new Response("boom", { status: 500, headers: { "content-type": "text/plain" } });

test("failed run renders a Try again button that resubmits without duplicating the user turn", async () => {
  const env = await boot("thread-retry", [failStream]);
  try {
    await act(async () => env.root.render(<env.ChatView thread="thread-retry" replay={null} onRunDone={() => {}} />));
    await flush();
    const suggestion = [...env.host.querySelectorAll("button")].find((b) => (b.textContent ?? "").includes("Can Miami aggregate"));
    assert.ok(suggestion, "suggested prompt renders");
    await act(async () => (suggestion as HTMLElement).click());
    const send = [...env.host.querySelectorAll("button")].find((b) => (b.getAttribute("aria-label") ?? "").toLowerCase().includes("send"));
    assert.ok(send, "send button renders");
    await act(async () => (send as HTMLElement).click());
    await flush(160);
    assert.equal(env.calls(), 1, "first stream call fired");
    const alert = env.host.querySelector("[role='alert']");
    assert.ok(alert, "failure card renders after the stream fails");
    const retry = [...env.host.querySelectorAll("button")].find((b) => (b.textContent ?? "").trim() === "Try again");
    assert.ok(retry, "Try again is a real button, not text");
    await act(async () => (retry as HTMLElement).click());
    await flush(160);
    assert.equal(env.calls(), 2, "retry resubmits to the stream endpoint");
    const userTurns = env.host.querySelectorAll(".user-turn");
    assert.equal(userTurns.length, 1, `retry must not duplicate the user turn, got ${userTurns.length}`);
  } finally {
    await act(async () => env.root.unmount());
    env.restore();
  }
});

test("reconcileRetryRuns drops a failed run superseded by an identical-question retry, keeps honest history otherwise", async () => {
  const { reconcileRetryRuns } = await import("./lib/chat-persistence");
  const fail = (q: string) => ({ question: q, snapshot: { failed: { kind: "connection", message: "x" } } as never });
  const ok = (q: string) => ({ question: q, snapshot: { failed: null } as never });
  assert.deepEqual(reconcileRetryRuns([fail("a"), ok("a")]).map(r => r.question), ["a"], "failed run superseded by adjacent identical retry is dropped");
  assert.equal(reconcileRetryRuns([fail("a"), ok("a")]).length, 1);
  assert.deepEqual(reconcileRetryRuns([fail("a"), ok("b")]).map(r => r.question), ["a", "b"], "different follow-up question keeps the failure");
  assert.deepEqual(reconcileRetryRuns([ok("a"), fail("b")]).map(r => r.question), ["a", "b"], "trailing failure with no retry survives");
  assert.deepEqual(reconcileRetryRuns([fail("a"), fail("a"), ok("a")]).map(r => r.question), ["a"], "a chain of retries collapses to the final run");
  assert.deepEqual(reconcileRetryRuns([ok("a"), ok("a")]).map(r => r.question), ["a", "a"], "successful duplicates are never collapsed");
});

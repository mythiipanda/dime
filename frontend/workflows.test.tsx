import { it } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act } from "react";
import { createRoot } from "react-dom/client";
import WorkflowsPanel from "./components/WorkflowsPanel";
import ChatPanel from "./components/ChatPanel";
import { workflows } from "./lib/workflows";

it("fills a workflow, previews its request and runs only when complete", async () => {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost" });
  const gx = globalThis as unknown as Record<string, unknown>;
  gx.window = dom.window;
  gx.document = dom.window.document;
  gx.IS_REACT_ACT_ENVIRONMENT = true;
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  const requests: string[] = [];
  try {
    await act(async () => root.render(<WorkflowsPanel onRun={(text) => requests.push(text)} />));
    const card = [...host.querySelectorAll("button")].find((button) => button.textContent?.includes("Opponent scouting report"))!;
    await act(async () => card.click());
    const run = host.querySelector<HTMLButtonElement>('button[type="submit"]')!;
    assert.equal(run.disabled, true);
    await act(async () => run.click());
    assert.equal(requests.length, 0);
    const selects = host.querySelectorAll("select");
    await act(async () => {
      selects[0].value = "OKC";
      selects[0].dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    });
    assert.equal(run.disabled, true);
    await act(async () => {
      selects[1].value = "DEN";
      selects[1].dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    });
    assert.equal(run.disabled, false);
    const expected = workflows[0].buildRequest({ team: "OKC", opponent: "DEN" });
    assert.equal(host.querySelector("pre")!.textContent, expected);
    await act(async () => run.click());
    assert.deepEqual(requests, [expected]);
    await act(async () => [...host.querySelectorAll("button")].find((b) => b.textContent?.includes("All workflows"))!.click());
    await act(async () => [...host.querySelectorAll("button")].find((b) => b.querySelector("h3")?.textContent === "Player evaluation")!.click());
    assert.equal(host.querySelector("input")!.value, "");
    assert.equal(host.querySelector<HTMLButtonElement>('button[type="submit"]')!.disabled, true);
  } finally {
    await act(async () => root.unmount());
    dom.window.close();
  }
});

it("preserves preset prefill and auto-sends a new workflow request once, showing backend errors", async () => {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost" });
  const gx = globalThis as unknown as Record<string, unknown>;
  gx.window = dom.window;
  gx.document = dom.window.document;
  gx.localStorage = dom.window.localStorage;
  gx.sessionStorage = dom.window.sessionStorage;
  gx.HTMLElement = dom.window.HTMLElement;
  gx.Element = dom.window.Element;
  gx.Node = dom.window.Node;
  gx.DocumentFragment = dom.window.DocumentFragment;
  gx.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
  gx.IS_REACT_ACT_ENVIRONMENT = true;
  Object.assign(dom.window.HTMLElement.prototype, { attachEvent() {}, detachEvent() {} });
  dom.window.HTMLElement.prototype.scrollIntoView = () => {};
  const originalFetch = globalThis.fetch;
  const requests: { q: string; thread: string }[] = [];
  globalThis.fetch = async (url, init) => {
    if (String(url).includes("/chat/stream")) {
      requests.push(JSON.parse(String(init?.body)));
      return new Response("unavailable", { status: 503 });
    }
    return Response.json(String(url).includes("/models") ? { models: [{ id: "test", label: "Test", default: true }] } : { runs: [], threads: [] });
  };
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  const request = { thread: "workflow-thread", text: "Evaluate OKC against DEN" };
  let consumed = 0;
  try {
    await act(async () => root.render(<ChatPanel thread="original-thread" preset="Prefill only" onRunDone={() => {}} />));
    assert.equal(host.querySelector("textarea")!.value, "Prefill only");
    assert.equal(requests.length, 0);
    await act(async () => {
      root.render(<ChatPanel key="workflow-thread" thread="workflow-thread" autoSend={request} onAutoSendConsumed={() => consumed++} onRunDone={() => {}} />);
    });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)); });
    assert.deepEqual(requests, [{ q: request.text, thread: request.thread, model: "test", client: dom.window.localStorage.getItem("dime_client") }]);
    assert.equal(consumed, 1);
    assert.match(host.textContent!, /Chat failed with status 503/);
    await act(async () => root.render(<ChatPanel key="workflow-thread" thread="workflow-thread" autoSend={request} onRunDone={() => {}} />));
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });
    assert.equal(requests.length, 1);
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    dom.window.close();
  }
});

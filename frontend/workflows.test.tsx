import { it } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act } from "react";
import { createRoot } from "react-dom/client";
import WorkflowsPanel from "./components/WorkflowsPanel";
import { workflows } from "./lib/workflows";
import { DimeShell } from "./components/shell/DimeShell";
import { StrictMode } from "react";
import { clearWorkflowDraft, hasPendingWorkflowDraft, loadWorkflowDraft, saveWorkflowDraft } from "./lib/workflow-drafts";
import { ChatView } from "./components/shell/ChatView";

it("stores workflow drafts per thread and tolerates unavailable storage", () => {
  const previous = globalThis.window;
  const dom = new JSDOM("", { url: "http://localhost" });
  Object.assign(globalThis, { window: dom.window });
  try {
    assert.equal(loadWorkflowDraft("missing"), null);
    saveWorkflowDraft("one", "Prepare a player evaluation.");
    assert.equal(loadWorkflowDraft("one"), "Prepare a player evaluation.");
    assert.equal(loadWorkflowDraft("two"), null);
    saveWorkflowDraft("one", "  ");
    assert.equal(loadWorkflowDraft("one"), null);
    assert.equal(hasPendingWorkflowDraft("one"), true);
    clearWorkflowDraft("one");
    assert.equal(hasPendingWorkflowDraft("one"), false);
    Object.defineProperty(dom.window, "localStorage", { get() { throw new Error("Storage blocked"); } });
    assert.doesNotThrow(() => saveWorkflowDraft("one", "Request"));
    assert.doesNotThrow(() => clearWorkflowDraft("one"));
    assert.equal(loadWorkflowDraft("one"), null);
    assert.equal(hasPendingWorkflowDraft("one"), false);
  } finally { Object.assign(globalThis, { window: previous }); dom.window.close(); }
});

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
    const cards = [...host.querySelectorAll(".workflow-card")];
    assert.match(cards.find(card => card.querySelector("h3")?.textContent === "Player evaluation")!.textContent!, /5 sections.*1 input\s*·/);
    assert.match(cards.find(card => card.querySelector("h3")?.textContent === "Player comparison")!.textContent!, /6 sections.*2 inputs\s*·/);
    assert.match(host.textContent!, /6 workflows/);
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
      selects[1].value = "OKC";
      selects[1].dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    });
    assert.equal(run.disabled, true);
    assert.equal(host.querySelector('[role="alert"]')!.textContent, "Opponent must differ from Your team.");
    assert.equal(selects[1].getAttribute("aria-invalid"), "true");
    await act(async () => host.querySelector("form")!.dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true })));
    assert.equal(requests.length, 0);
    await act(async () => {
      selects[1].value = "DEN";
      selects[1].dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    });
    assert.equal(run.disabled, false);
    assert.equal(host.querySelector('[role="alert"]'), null);
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

for (const mode of ["edit", "clear-rewrite"]) it(`workflow draft ${mode}: user changes survive model loading and reload until manually sent`, async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/?tab=chat&thread=pending-workflow" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });
  dom.window.matchMedia = (() => ({ matches: true, addEventListener() {}, removeEventListener() {} })) as unknown as typeof dom.window.matchMedia;
  Object.assign(dom.window.HTMLElement.prototype, { scrollTo() {}, scrollIntoView() {}, attachEvent() {}, detachEvent() {} });
  const previous = globalThis.fetch;
  const requests: Record<string, unknown>[] = [];
  let resolveModels!: () => void;
  const ready = new Promise<void>(resolve => { resolveModels = resolve; });
  globalThis.fetch = async (input, init) => {
    if (String(input).includes("/models")) {
      await ready;
      return Response.json({ models: [{ id: "gemini:flash", available: true, default: true }], available: { gemini: true } });
    }
    if (String(input).includes("/chat/stream")) { requests.push(JSON.parse(String(init?.body))); return new Response("unavailable", { status: 503 }); }
    return Response.json({ runs: [] });
  };
  const host = dom.window.document.getElementById("root")!;
  let root = createRoot(host);
  const original = "Prepare an opponent scouting report.";
  const revised = "Compare OKC and DEN transition defense instead.";
  saveWorkflowDraft("pending-workflow", original);
  const edit = async (value: string) => act(async () => {
    const input = host.querySelector("textarea")!;
    input.focus();
    Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    input.dispatchEvent(new dom.window.KeyboardEvent("keyup", { key: "x", bubbles: true }));
  });
  try {
    await act(async () => root.render(<StrictMode><ChatView thread="pending-workflow" replay={null} onRunDone={() => {}} workflowRequest={{ thread: "pending-workflow", text: original }} /></StrictMode>));
    assert.equal(host.querySelector("textarea")!.value, original);
    if (mode === "clear-rewrite") {
      await edit("");
      assert.equal(loadWorkflowDraft("pending-workflow"), null);
      assert.equal(hasPendingWorkflowDraft("pending-workflow"), true);
    }
    await edit(revised);
    assert.equal(loadWorkflowDraft("pending-workflow"), revised);
    await act(async () => resolveModels());
    assert.equal(host.querySelector("textarea")!.value, revised);
    assert.equal(requests.length, 0);
    await act(async () => root.unmount());
    root = createRoot(host);
    await act(async () => root.render(<StrictMode><ChatView thread="pending-workflow" replay={null} onRunDone={() => {}} /></StrictMode>));
    assert.equal(host.querySelector("textarea")!.value, revised);
    assert.equal(requests.length, 0);
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Send message"]')!.click());
    assert.equal(requests.length, 1);
    assert.equal(requests[0].q, revised);
    assert.equal(loadWorkflowDraft("pending-workflow"), null);
    assert.equal(hasPendingWorkflowDraft("pending-workflow"), false);
  } finally { resolveModels(); await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); }
});

for (const mode of ["available", "empty", "error", "retry"]) it(`workflow handoff ${mode}: uses a fresh thread even when model loading fails`, async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/?tab=workflows&thread=original-thread" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });
  dom.window.matchMedia = (() => ({ matches: true, addEventListener() {}, removeEventListener() {} })) as unknown as typeof dom.window.matchMedia;
  Object.assign(dom.window.HTMLElement.prototype, { scrollTo() {}, scrollIntoView() {}, attachEvent() {}, detachEvent() {} });
  const previous = globalThis.fetch;
  const requests: Record<string, unknown>[] = [];
  let modelsFail = mode === "error" || mode === "retry";
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("/models")) {
      if (modelsFail) return new Response("unavailable", { status: 503 });
      const available = mode === "available" || mode === "retry";
      return Response.json({ models: available ? [{ id: "gemini:flash", available: true, default: true }] : [], available: { gemini: available } });
    }
    if (url.includes("/chat/stream")) { requests.push(JSON.parse(String(init?.body))); return new Response("unavailable", { status: 503 }); }
    return Response.json({ threads: [], runs: [] });
  };
  const host = dom.window.document.getElementById("root")!;
  let root = createRoot(host);
  try {
    await act(async () => root.render(<StrictMode><DimeShell /></StrictMode>));
    await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent?.includes("Opponent scouting report"))!.click());
    for (const [index, team] of ["OKC", "DEN"].entries()) await act(async () => {
      const select = host.querySelectorAll("select")[index];
      select.value = team;
      select.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    });
    const expected = workflows[0].buildRequest({ team: "OKC", opponent: "DEN" });
    await act(async () => { const button = host.querySelector<HTMLButtonElement>('button[type="submit"]')!; button.click(); button.click(); });
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 30)); });
    const url = new URL(dom.window.location.href);
    assert.equal(url.searchParams.get("tab"), "chat");
    assert.notEqual(url.searchParams.get("thread"), "original-thread");
    if (mode === "available") {
      assert.equal(requests.length, 1);
      assert.equal(requests[0].q, expected);
      assert.equal(requests[0].thread, url.searchParams.get("thread"));
      assert.equal(requests[0].model, "gemini:flash");
      assert.match(host.textContent!, /503/);
      assert.equal(loadWorkflowDraft(url.searchParams.get("thread")!), null);
    } else {
      assert.equal(requests.length, 0);
      assert.equal(host.querySelector("textarea")!.value, expected);
      assert.match(host.textContent!, mode === "empty" ? /GEMINI_API_KEY/ : /Models unavailable/);
      assert.equal(host.querySelector<HTMLButtonElement>('[aria-label="Send message"]')!.disabled, true);
      assert.equal(loadWorkflowDraft(url.searchParams.get("thread")!), expected);
      await act(async () => root.unmount());
      root = createRoot(host);
      await act(async () => root.render(<StrictMode><DimeShell /></StrictMode>));
      assert.equal(host.querySelector("textarea")!.value, expected);
      assert.equal(new URL(dom.window.location.href).searchParams.get("thread"), url.searchParams.get("thread"));
      assert.equal(requests.length, 0);
    }
    await act(async () => root.render(<StrictMode><DimeShell /></StrictMode>));
    assert.equal(requests.length, mode === "available" ? 1 : 0);
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Open command palette"]')!.click());
    assert.match(host.querySelector('[role="dialog"]')!.textContent!, /Workflows/);
    if (mode === "retry") {
      modelsFail = false;
      await act(async () => [...host.querySelectorAll("button")].find(button => button.textContent?.includes("Models unavailable"))!.click());
      assert.equal(host.querySelector("textarea")!.value, expected);
      assert.equal(requests.length, 0);
      await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Send message"]')!.click());
      assert.equal(requests.length, 1);
      assert.equal(requests[0].thread, url.searchParams.get("thread"));
      assert.notEqual(requests[0].thread, "original-thread");
      assert.equal(loadWorkflowDraft(url.searchParams.get("thread")!), null);
    }
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); }
});

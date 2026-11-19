import { it } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act } from "react";
import { createRoot } from "react-dom/client";
import WorkflowsPanel from "./components/WorkflowsPanel";
import { workflows } from "./lib/workflows";
import { DimeShell } from "./components/shell/DimeShell";
import { StrictMode } from "react";

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

for (const mode of ["available", "empty", "error"]) it(`workflow handoff ${mode}: uses dev chat once or retains the draft without a new thread`, async () => {
  const dom = new JSDOM("<div id='root'></div>", { url: "http://localhost/?tab=workflows&thread=original-thread" });
  Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, HTMLElement: dom.window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });
  dom.window.matchMedia = (() => ({ matches: true, addEventListener() {}, removeEventListener() {} })) as unknown as typeof dom.window.matchMedia;
  Object.assign(dom.window.HTMLElement.prototype, { scrollTo() {}, scrollIntoView() {}, attachEvent() {}, detachEvent() {} });
  const previous = globalThis.fetch;
  const requests: Record<string, unknown>[] = [];
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("/models")) {
      if (mode === "error") return new Response("unavailable", { status: 503 });
      return Response.json({ models: mode === "available" ? [{ id: "gemini:flash", available: true, default: true }] : [], available: { gemini: mode === "available" } });
    }
    if (url.includes("/chat/stream")) { requests.push(JSON.parse(String(init?.body))); return new Response("unavailable", { status: 503 }); }
    return Response.json({ threads: [], runs: [] });
  };
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
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
    if (mode === "available") {
      assert.notEqual(url.searchParams.get("thread"), "original-thread");
      assert.equal(requests.length, 1);
      assert.equal(requests[0].q, expected);
      assert.equal(requests[0].thread, url.searchParams.get("thread"));
      assert.equal(requests[0].model, "gemini:flash");
      assert.match(host.textContent!, /503/);
    } else {
      assert.equal(url.searchParams.get("thread"), "original-thread");
      assert.equal(requests.length, 0);
      assert.equal(host.querySelector("textarea")!.value, expected);
      assert.match(host.textContent!, mode === "empty" ? /GEMINI_API_KEY/ : /Models unavailable/);
      assert.equal(host.querySelector<HTMLButtonElement>('[aria-label="Send message"]')!.disabled, true);
    }
    await act(async () => root.render(<StrictMode><DimeShell /></StrictMode>));
    assert.equal(requests.length, mode === "available" ? 1 : 0);
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Open command palette"]')!.click());
    assert.match(host.querySelector('[role="dialog"]')!.textContent!, /Workflows/);
  } finally { await act(async () => root.unmount()); globalThis.fetch = previous; dom.window.close(); }
});

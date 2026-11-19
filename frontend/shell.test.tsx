import { it } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { DimeShell, parseShellTab, shellNavigation } from "./components/shell/DimeShell";

it("keeps old URL values and defines the requested navigation", () => {
  assert.deepEqual(shellNavigation.map((n) => n.label), ["Home", "Ask", "Boards", "Workflows", "Library", "Data"]);
  for (const tab of ["chat", "today", "data", "workflows"] as const) assert.equal(parseShellTab(tab), tab);
  assert.equal(parseShellTab("unknown"), "chat");
});

it("navigates boards, searches real threads, and dispatches workflows to a new chat", async () => {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost/?tab=boards&thread=t-existing" });
  const gx = globalThis as unknown as Record<string, unknown>;
  Object.assign(gx, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, DocumentFragment: dom.window.DocumentFragment, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { scrollIntoView() {}, attachEvent() {}, detachEvent() {} });
  const originalFetch = globalThis.fetch;
  const requests: { thread: string; q: string }[] = [];
  globalThis.fetch = async (url, init) => {
    if (String(url).includes("/chat/stream")) { requests.push(JSON.parse(String(init?.body))); return new Response("unavailable", { status: 503 }); }
    return Response.json(String(url).includes("/models") ? { models: [{ id: "test", default: true }] } : { threads: [{ id: "t-existing", title: "Denver rotation", updated: "2026-01-01", turns: 1 }], runs: [] });
  };
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  const button = (label: string) => [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === label)!;
  try {
    await act(async () => root.render(<DimeShell />));
    assert.match(host.textContent!, /Agent-built, cited player grids/);
    assert.match(host.textContent!, /Denver rotation/);
    await act(async () => button("Workflows").click());
    assert.equal(new URL(dom.window.location.href).searchParams.get("tab"), "workflows");
    await act(async () => [...host.querySelectorAll(".workflow-card")].find((b) => b.textContent?.includes("Opponent scouting report"))!.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })));
    const selects = host.querySelectorAll("select");
    for (const [i, value] of ["OKC", "DEN"].entries()) await act(async () => { selects[i].value = value; selects[i].dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await act(async () => button("Run workflow").click());
    await act(async () => { await new Promise((r) => setTimeout(r, 60)); });
    assert.equal(requests.length, 1);
    assert.match(requests[0].q, /OKC/);
    assert.match(requests[0].q, /DEN/);
    assert.notEqual(requests[0].thread, "t-existing");
    assert.equal(new URL(dom.window.location.href).searchParams.get("thread"), requests[0].thread);
    assert.equal(new URL(dom.window.location.href).searchParams.get("tab"), "chat");
    assert.match(host.textContent!, /Chat failed with status 503/);
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Collapse sidebar"]')!.click());
    assert.ok(host.querySelector(".is-collapsed"));
    await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Expand sidebar"]')!.click());
    assert.equal(host.querySelector(".is-collapsed"), null);
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    dom.window.close();
  }
});

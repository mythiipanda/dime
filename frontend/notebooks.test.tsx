import { testDom } from "./test-dom";
import test from "node:test";
import assert from "node:assert/strict";
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { getNotebook, listNotebooks } from "./lib/notebooks";

const requests: { path: string; body: Record<string, unknown> }[] = [];

async function mount(options: { notebookId?: string } = {}) {
  const dom = testDom;
  dom.window.document.body.innerHTML = "<div id='root'></div>";
  dom.window.localStorage.clear();
  dom.window.history.replaceState({}, "", "/");
  Object.assign(globalThis, { localStorage: dom.window.localStorage, IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { attachEvent() {}, detachEvent() {}, scrollIntoView() {} });
  const { NotebooksPanel } = await import("./components/NotebooksPanel");
  function Harness() { const [id, setId] = useState<string | null>(null); return <NotebooksPanel notebookId={id} onOpen={setId} />; }
  const previous = globalThis.fetch;
  requests.length = 0;
  globalThis.fetch = async (url, init) => {
    const path = String(url); const body = init?.body ? JSON.parse(String(init.body)) : {};
    requests.push({ path, body });
    if (path.endsWith("/sql/rerun")) {
      if (String(body.sql ?? "").includes("FAIL")) return Response.json({ ok: false, error: "syntax error near FAIL" });
      return Response.json({ ok: true, rows: { columns: ["PLAYER", "PTS"], rows: [{ PLAYER: "Shai Gilgeous-Alexander", PTS: 31.4 }, { PLAYER: "Nikola Jokić", PTS: 29.6 }], ms: 12, capped: false } });
    }
    if (path.includes("/chat/stream")) {
      const sse = `event: final_answer\ndata: {"text":"Shai leads on 31.4 points."}\n\nevent: graph_end\ndata: {}\n\n`;
      return new Response(sse, { status: 200, headers: { "content-type": "text/event-stream" } });
    }
    return Response.json({ rows: [] });
  };
  const root = createRoot(dom.window.document.getElementById("root")!);
  await act(async () => { root.render(options.notebookId ? <NotebooksPanel notebookId={options.notebookId} onOpen={() => {}} /> : <Harness />); });
  const host = dom.window.document.getElementById("root")!;
  return { dom, host, options, root, cleanup: async () => { await act(async () => { root.unmount(); await new Promise(resolve => setTimeout(resolve, 25)); }); globalThis.fetch = previous; } };
}
const button = (host: ParentNode, text: string) => [...host.querySelectorAll("button")].find((b) => b.textContent?.includes(text))!;
const exactButton = (host: ParentNode, text: string) => [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === text)!;
async function click(el: HTMLElement) { assert.ok(el); await act(async () => { el.click(); await new Promise((r) => setTimeout(r, 30)); }); }
async function type(el: HTMLTextAreaElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value")!.set!;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new testDom.window.Event("input", { bubbles: true })); await new Promise((r) => setTimeout(r, 10)); });
}

test("creates a notebook, runs an SQL cell and shows results with provenance", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "New notebook"));
    assert.ok(m.host.textContent?.includes("Start with a cell"));
    await click(button(m.host, "SQL cell"));
    await type(m.host.querySelector("textarea")!, "SELECT PLAYER, PTS FROM silver_player_season");
    await click(button(m.host, "Run SQL"));
    assert.ok(m.host.textContent?.includes("Shai Gilgeous-Alexander"));
    assert.ok(m.host.textContent?.includes("31.4"));
    assert.ok(m.host.textContent?.includes("warehouse sql"));
    const saved = listNotebooks()[0];
    assert.equal(getNotebook(saved.id)?.cells[0].result?.rows?.length, 2);
    assert.equal(requests.find((r) => r.path.endsWith("/sql/rerun"))?.body.sql, "SELECT PLAYER, PTS FROM silver_player_season");
  } finally { await m.cleanup(); }
});

test("ask cells send the question plus earlier cell context to the agent", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "New notebook"));
    await click(button(m.host, "SQL cell"));
    await type(m.host.querySelector("textarea")!, "SELECT PLAYER, PTS FROM silver_player_season");
    await click(button(m.host, "Run SQL"));
    await click(button(m.host, "Ask Dime cell"));
    const textareas = m.host.querySelectorAll("textarea");
    await type(textareas[textareas.length - 1], "Who leads?");
    await click(exactButton(m.host, "Ask Dime"));
    const stream = requests.find((r) => r.path.includes("/chat/stream"))!;
    assert.match(String(stream.body.q), /Cell 1 · SQL/);
    assert.match(String(stream.body.q), /Shai Gilgeous-Alexander/);
    assert.match(String(stream.body.q), /Question: Who leads\?/);
    assert.ok(m.host.textContent?.includes("Shai leads on 31.4 points."));
    assert.ok(m.host.textContent?.includes("Dime answer"));
  } finally { await m.cleanup(); }
});

test("sql errors stay on the cell without dropping prior results", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "New notebook"));
    await click(button(m.host, "SQL cell"));
    await type(m.host.querySelector("textarea")!, "SELECT FAIL");
    await click(button(m.host, "Run SQL"));
    assert.ok(m.host.textContent?.includes("syntax error near FAIL"));
    assert.equal(listNotebooks()[0].cells[0].result, undefined);
  } finally { await m.cleanup(); }
});

test("saved notebooks list and reopen", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "New notebook"));
    await click(button(m.host, "All notebooks"));
    assert.ok(m.host.textContent?.includes("Saved notebooks"));
    await click(button(m.host, "Open"));
    assert.ok(m.host.textContent?.includes("Notebook"));
  } finally { await m.cleanup(); }
});

import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { JSDOM } from "jsdom";
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { useNotebook } from "./components/notebooks/useNotebook";
import { newCell, type Notebook, type SQLResult } from "./lib/notebooks";

createRequire(`${process.cwd()}/notebooks.test.tsx`).extensions[".css"] = () => {};
const delay = (ms = 25) => new Promise((resolve) => setTimeout(resolve, ms));
const button = (host: ParentNode, text: string) => [...host.querySelectorAll("button")].find((b) => b.textContent?.includes(text))!;
async function click(element: HTMLElement) { assert.ok(element); await act(async () => { element.click(); await delay(); }); }
const sqlResult: SQLResult = { columns: [{ name: "PLAYER", type: "VARCHAR" }, { name: "PTS", type: "DOUBLE" }], rows: [{ PLAYER: "Stephen Curry", PTS: 28.5 }], page: 0, page_size: 100, has_more: false, ms: 7, truncated: false };

async function mount(options: { sqlError?: boolean; empty?: boolean; conflict?: boolean; listError?: boolean; deferredSave?: boolean } = {}, hook = false) {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost/?tab=notebooks", pretendToBeVisual: true });
  Object.assign(globalThis, { window: dom.window, Window: dom.window.Window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, DocumentFragment: dom.window.DocumentFragment, ShadowRoot: dom.window.ShadowRoot, MutationObserver: dom.window.MutationObserver, requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window), cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window), getComputedStyle: dom.window.getComputedStyle.bind(dom.window), IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { attachEvent() {}, detachEvent() {}, scrollIntoView() {}, getClientRects() { return []; } });
  Object.assign(dom.window.Range.prototype, { getClientRects() { return []; }, getBoundingClientRect() { return { left: 0, right: 0, top: 0, bottom: 0 }; } });
  let doc: Notebook = { id: "a".repeat(32), title: "Test notebook", version: 1, created_at: "2026-01-01", updated_at: "2026-01-01", cells: [newCell("sql", "SELECT PLAYER, PPG AS PTS FROM silver_player_season")] };
  const requests: { path: string; method: string; body: Record<string, unknown> }[] = [];
  let resolveSave: (() => void) | undefined;
  const previous = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const path = String(input), method = init?.method || "GET", body = init?.body ? JSON.parse(String(init.body)) : {};
    requests.push({ path, method, body });
    if (path.endsWith("/capabilities")) return Response.json({ python: { enabled: false, trusted_local_only: true, message: "Trusted local Python only. Enable with DIME_NOTEBOOK_PYTHON=1; this is not a security sandbox." } });
    if (path.endsWith("/sql")) return options.sqlError ? Response.json({ detail: "Table is not allowlisted" }, { status: 400 }) : Response.json({ ...sqlResult, rows: options.empty ? [] : sqlResult.rows });
    if (path.endsWith("/notebooks") && method === "POST") { doc = { ...doc, ...body } as Notebook; return Response.json(doc, { status: 201 }); }
    if (path.endsWith("/notebooks")) return options.listError ? Response.json({ detail: "Storage unavailable" }, { status: 503 }) : Response.json({ notebooks: [] });
    if (method === "PUT") {
      if (options.deferredSave) await new Promise<void>((resolve) => { resolveSave = resolve; });
      if (options.conflict) return Response.json({ detail: "Notebook changed; reload before saving" }, { status: 409 });
      assert.equal(body.version, doc.version); doc = { ...doc, ...body, version: doc.version + 1 } as Notebook; return Response.json(doc);
    }
    return Response.json(doc);
  };
  const { default: NotebooksPanel } = await import("./components/notebooks/NotebooksPanel");
  let currentHook: ReturnType<typeof useNotebook>;
  function Hook() { currentHook = useNotebook(doc.id); return <span>{currentHook.state}</span>; }
  function Harness() { const [id, setId] = useState<string | null>(null); return <NotebooksPanel notebookId={id} onOpen={setId} />; }
  const host = dom.window.document.getElementById("root")!, root = createRoot(host);
  await act(async () => { root.render(hook ? <Hook /> : <Harness />); await delay(); });
  return { dom, host, options, requests, hook: () => currentHook!, releaseSave: () => resolveSave?.(), cleanup: async () => { await act(async () => { root.unmount(); await delay(); }); globalThis.fetch = previous; dom.window.close(); } };
}

test("creates a notebook, runs SQL, shows a typed table and explains disabled Python without an error", async () => {
  const m = await mount();
  try {
    assert.match(m.host.textContent!, /Team four factors/); assert.match(m.host.textContent!, /Room for your next insight/);
    await click(button(m.host, "New notebook"));
    await click(m.host.querySelector<HTMLButtonElement>('[aria-label="Run cell 1"]')!);
    assert.match(m.host.querySelector('table[aria-label="Query result"]')!.textContent!, /Stephen Curry/);
    assert.match(m.host.textContent!, /VARCHAR/); assert.match(m.host.textContent!, /28.5/); assert.match(m.host.textContent!, /7 ms/);
    await act(async () => { await delay(700); });
    assert.equal(m.requests.find((r) => r.method === "PUT")!.body.version, 1);
    assert.equal(m.host.querySelector('[role="status"]')!.textContent, "Saved");
    const code = m.host.querySelector<HTMLElement>(".cm-content")!;
    assert.ok(code);
    const source = code.textContent;
    await act(async () => { code.focus(); code.dispatchEvent(new m.dom.window.KeyboardEvent("keydown", { key: "Enter", code: "Enter", shiftKey: true, bubbles: true, cancelable: true })); await delay(); });
    assert.equal(m.requests.filter((r) => r.path.endsWith("/sql")).length, 2);
    assert.equal(code.textContent, source);
    await click(button(m.host, "Add cell"));
    const select = m.host.querySelector<HTMLSelectElement>('[aria-label="Cell 2 kind"]')!;
    await act(async () => { select.value = "python"; select.dispatchEvent(new m.dom.window.Event("change", { bubbles: true })); });
    assert.match(m.host.querySelector('[role="note"]')!.textContent!, /DIME_NOTEBOOK_PYTHON=1/);
    assert.equal(m.host.querySelector('[role="alert"]'), null);
    assert.equal(m.host.querySelector<HTMLButtonElement>('[aria-label="Run cell 2"]')!.disabled, true);
    assert.equal(m.requests.filter((r) => r.path.endsWith("/python")).length, 0);
  } finally { await m.cleanup(); }
});

test("empty SQL output and API errors have distinct treatments", async () => {
  const m = await mount({ empty: true });
  try {
    await click(button(m.host, "New notebook")); await click(m.host.querySelector<HTMLButtonElement>('[aria-label="Run cell 1"]')!);
    assert.match(m.host.textContent!, /No rows matched/); assert.equal(m.host.querySelector('[role="alert"]'), null);
    m.options.sqlError = true;
    await click(m.host.querySelector<HTMLButtonElement>('[aria-label="Run cell 1"]')!);
    assert.match(m.host.querySelector('[role="alert"]')!.textContent!, /Table is not allowlisted/);
  } finally { await m.cleanup(); }
});

test("a 409 stops autosave, shows reload and disables conflicting edits", async () => {
  const m = await mount({ conflict: true });
  try {
    await click(button(m.host, "New notebook")); await click(m.host.querySelector<HTMLButtonElement>('[aria-label="Run cell 1"]')!);
    await act(async () => { await delay(700); });
    assert.match(m.host.querySelector('[role="alert"]')!.textContent!, /Conflict, reload/);
    assert.match(m.host.textContent!, /Reload latest version/);
    assert.equal(m.host.querySelector<HTMLInputElement>('[aria-label="Notebook title"]')!.disabled, true);
    await act(async () => { await delay(700); }); assert.equal(m.requests.filter((r) => r.method === "PUT").length, 1);
  } finally { await m.cleanup(); }
});

test("list loading errors are actionable", async () => {
  const m = await mount({ listError: true });
  try { assert.match(m.host.querySelector('[role="alert"]')!.textContent!, /Storage unavailable/); m.options.listError = false; await click(button(m.host, "Retry")); assert.match(m.host.textContent!, /Room for your next insight/); } finally { await m.cleanup(); }
});

test("autosave serializes writes and preserves edits made during an in-flight save", async () => {
  const m = await mount({ deferredSave: true }, true);
  try {
    let first!: Promise<boolean>, second!: Promise<boolean>;
    await act(async () => { m.hook().edit((doc) => ({ ...doc, title: "First" })); first = m.hook().persist(); });
    assert.equal(m.hook().state, "saving");
    await act(async () => { m.hook().edit((doc) => ({ ...doc, title: "Second" })); second = m.hook().persist(); });
    assert.equal(m.requests.filter((r) => r.method === "PUT").length, 1);
    await act(async () => { m.options.deferredSave = false; m.releaseSave(); await first; await second; });
    assert.deepEqual(m.requests.filter((r) => r.method === "PUT").map((r) => [r.body.title, r.body.version]), [["First", 1], ["Second", 2]]);
    assert.equal(m.hook().notebook!.title, "Second"); assert.equal(m.hook().state, "saved");
  } finally { await m.cleanup(); }
});

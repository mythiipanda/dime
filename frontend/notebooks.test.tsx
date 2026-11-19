import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { JSDOM } from "jsdom";
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { useNotebook } from "./components/notebooks/useNotebook";
import { newCell, type Notebook, type SQLResult } from "./lib/notebooks";
import { findNotebookDraft, writeNotebookDraft } from "./lib/notebook-drafts";

createRequire(`${process.cwd()}/notebooks.test.tsx`).extensions[".css"] = () => {};
const delay = (ms = 25) => new Promise((resolve) => setTimeout(resolve, ms));
const button = (host: ParentNode, text: string) => [...host.querySelectorAll("button")].find((b) => b.textContent?.includes(text))!;
async function click(element: HTMLElement) { assert.ok(element); await act(async () => { element.click(); await delay(); }); }
const sqlResult: SQLResult = { columns: [{ name: "PLAYER", type: "VARCHAR" }, { name: "PTS", type: "DOUBLE" }], rows: [{ PLAYER: "Stephen Curry", PTS: 28.5 }], page: 0, page_size: 100, has_more: false, ms: 7, truncated: false };

async function mount(options: { sqlError?: boolean; empty?: boolean; conflict?: boolean; listError?: boolean; deferredSave?: boolean; pythonEnabled?: boolean; savedPython?: boolean; saveError?: boolean; storedDrafts?: string; openNotebook?: boolean; storedEntries?: Record<string, string>; tabId?: string; serverVersion?: number; serverUpdated?: string; drafts?: { title: string; tab: string; version: number; time: number }[] } = {}, hook = false) {
  const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost/?tab=notebooks", pretendToBeVisual: true });
  if (options.storedDrafts) dom.window.localStorage.setItem("dime_notebook_drafts_v1", options.storedDrafts);
  for (const [key, value] of Object.entries(options.storedEntries || {})) dom.window.localStorage.setItem(key, value);
  if (options.tabId) dom.window.sessionStorage.setItem("dime_notebook_drafts_v1:tab", options.tabId);
  Object.assign(globalThis, { window: dom.window, Window: dom.window.Window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Element: dom.window.Element, Node: dom.window.Node, DocumentFragment: dom.window.DocumentFragment, ShadowRoot: dom.window.ShadowRoot, MutationObserver: dom.window.MutationObserver, requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window), cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window), getComputedStyle: dom.window.getComputedStyle.bind(dom.window), IS_REACT_ACT_ENVIRONMENT: true });
  Object.assign(dom.window.HTMLElement.prototype, { attachEvent() {}, detachEvent() {}, scrollIntoView() {}, getClientRects() { return []; } });
  Object.assign(dom.window.Range.prototype, { getClientRects() { return []; }, getBoundingClientRect() { return { left: 0, right: 0, top: 0, bottom: 0 }; } });
  let doc: Notebook = { id: "a".repeat(32), title: "Test notebook", version: 1, created_at: "2026-01-01", updated_at: "2026-01-01", cells: [newCell("sql", "SELECT PLAYER, PPG AS PTS FROM silver_player_season")] };
  doc.version = options.serverVersion || doc.version;
  doc.updated_at = options.serverUpdated || doc.updated_at;
  for (const draft of options.drafts || []) dom.window.localStorage.setItem(`dime_notebook_drafts_v1:${doc.id}:${draft.tab}:${draft.version}`, JSON.stringify({ notebook: { ...doc, title: draft.title }, base_version: draft.version, saved_at: draft.time }));
  if (options.savedPython) doc.cells = [{ ...newCell("python", "show(df)"), outputs: { kind: "python", data: { ok: true, stdout: "old stdout", tables: [{ columns: [{ name: "old", type: "VARCHAR" }], rows: [{ old: "old table" }], row_count: 1 }], figures: [{ mime_type: "image/png", data: "old-image" }] } } }];
  const requests: { path: string; method: string; body: Record<string, unknown> }[] = [];
  let resolveSave: (() => void) | undefined;
  const previous = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const path = String(input), method = init?.method || "GET", body = init?.body ? JSON.parse(String(init.body)) : {};
    requests.push({ path, method, body });
    if (path.endsWith("/capabilities")) return Response.json({ python: { enabled: !!options.pythonEnabled, trusted_local_only: true, message: "Trusted local Python only. Enable with DIME_NOTEBOOK_PYTHON=1; this is not a security sandbox." } });
    if (path.endsWith("/python")) return Response.json({ ok: true, stdout: "", stderr: "", tables: [], figures: [] });
    if (path.endsWith("/sql")) return options.sqlError ? Response.json({ detail: "Table is not allowlisted" }, { status: 400 }) : Response.json({ ...sqlResult, rows: options.empty ? [] : sqlResult.rows });
    if (path.endsWith("/notebooks") && method === "POST") { doc = { ...doc, ...body } as Notebook; return Response.json(doc, { status: 201 }); }
    if (path.endsWith("/notebooks")) return options.listError ? Response.json({ detail: "Storage unavailable" }, { status: 503 }) : Response.json({ notebooks: [] });
    if (method === "PUT") {
      if (options.saveError) return Response.json({ detail: "Backend unavailable" }, { status: 503 });
      if (options.deferredSave) await new Promise<void>((resolve) => { resolveSave = resolve; });
      if (options.conflict) return Response.json({ detail: "Notebook changed; reload before saving" }, { status: 409 });
      assert.equal(body.version, doc.version); doc = { ...doc, ...body, version: doc.version + 1 } as Notebook; return Response.json(doc);
    }
    return Response.json(doc);
  };
  const { default: NotebooksPanel } = await import("./components/notebooks/NotebooksPanel");
  let currentHook: ReturnType<typeof useNotebook>;
  function Hook() { currentHook = useNotebook(doc.id); return <span>{currentHook.state}</span>; }
  function Harness() { const [id, setId] = useState<string | null>(options.savedPython || options.openNotebook ? doc.id : null); return <NotebooksPanel notebookId={id} onOpen={setId} />; }
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

test("disabled Python hides stale successful outputs restored from disk", async () => {
  const m = await mount({ savedPython: true });
  try {
    assert.match(m.host.textContent!, /Python is off on this backend/);
    assert.doesNotMatch(m.host.textContent!, /Python complete|old stdout|old table/);
    assert.equal(m.host.querySelector(".notebook-figure"), null);
    assert.equal(m.host.querySelector("table"), null);
  } finally { await m.cleanup(); }
});

test("Python runs send the current theme without rerunning code on theme changes", async () => {
  const m = await mount({ pythonEnabled: true });
  try {
    await click(button(m.host, "Player shot profile"));
    m.dom.window.document.documentElement.classList.add("dark");
    await click(m.host.querySelector<HTMLButtonElement>('[aria-label="Run cell 3"]')!);
    const requests = () => m.requests.filter((r) => r.path.endsWith("/python"));
    assert.equal(requests()[0].body.theme, "dark");
    m.dom.window.document.documentElement.classList.remove("dark");
    await act(async () => { await delay(); });
    assert.equal(requests().length, 1);
    await click(m.host.querySelector<HTMLButtonElement>('[aria-label="Run cell 3"]')!);
    assert.equal(requests()[1].body.theme, "light");
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

test("new Markdown cells keep their editor and focus until Escape", async () => {
  const m = await mount();
  try {
    await click(button(m.host, "New notebook"));
    await click(button(m.host, "Add cell"));
    const select = m.host.querySelector<HTMLSelectElement>('[aria-label="Cell 2 kind"]')!;
    await act(async () => { select.value = "markdown"; select.dispatchEvent(new m.dom.window.Event("change", { bubbles: true })); });
    const textarea = m.host.querySelector<HTMLTextAreaElement>('[aria-label="Cell 2 markdown"]')!;
    const setter = Object.getOwnPropertyDescriptor(m.dom.window.HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => { textarea.focus(); setter.call(textarea, "First character"); textarea.dispatchEvent(new m.dom.window.Event("input", { bubbles: true })); textarea.dispatchEvent(new m.dom.window.KeyboardEvent("keyup", { key: "r", bubbles: true })); });
    assert.ok(m.host.querySelector('[aria-label="Cell 2 markdown"]') === textarea, "Markdown editor was replaced");
    assert.ok(m.dom.window.document.activeElement === textarea, "Markdown editor lost focus");
    assert.equal(textarea.value, "First character");
    await act(async () => { textarea.dispatchEvent(new m.dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
    assert.ok(!m.host.querySelector('[aria-label="Cell 2 markdown"]'), "Escape did not leave edit mode");
    assert.match(m.host.querySelector(".notebook-markdown")!.textContent!, /First character/);
  } finally { await m.cleanup(); }
});

test("failed saves survive leaving and reopening, offer restore, and clear after save", async () => {
  const first = await mount({ saveError: true }, true);
  let stored: Record<string, string> = {}, tabId = "";
  try {
    await act(async () => {
      first.hook().edit((doc) => ({ ...doc, title: "Recovered analysis" }));
      assert.equal(await first.hook().persist(), false);
    });
    stored = Object.fromEntries(Object.keys(first.dom.window.localStorage).map((key) => [key, first.dom.window.localStorage.getItem(key)!]));
    assert.equal(JSON.parse(Object.values(stored)[0]).notebook.title, "Recovered analysis");
    tabId = first.dom.window.sessionStorage.getItem("dime_notebook_drafts_v1:tab")!;
  } finally { await first.cleanup(); }
  const reopened = await mount({ storedEntries: stored, tabId, openNotebook: true });
  try {
    assert.match(reopened.host.textContent!, /Restore unsaved changes/);
    assert.equal(reopened.host.querySelector<HTMLInputElement>('[aria-label="Notebook title"]')!.value, "Test notebook");
    await click(button(reopened.host, "Restore unsaved changes"));
    assert.equal(reopened.host.querySelector<HTMLInputElement>('[aria-label="Notebook title"]')!.value, "Recovered analysis");
    await act(async () => { await delay(700); });
    assert.equal(reopened.dom.window.localStorage.length, 0);
  } finally { await reopened.cleanup(); }
});

test("invalid local drafts do not prevent opening a notebook", async () => {
  const m = await mount({ storedDrafts: '{"invalid":null}' });
  try { await click(button(m.host, "New notebook")); assert.doesNotMatch(m.host.textContent!, /Restore unsaved changes/); }
  finally { await m.cleanup(); }
});

test("recovery ignores clock skew, shows base version, and blocks edits until a choice", async () => {
  const options = { serverVersion: 3, serverUpdated: "2099-01-01", drafts: [{ title: "Clock-skewed edits", tab: "old-tab", version: 1, time: 1 }] };
  const m = await mount(options, true);
  try {
    assert.equal(m.hook().draft!.notebook.title, "Clock-skewed edits");
    const before = m.dom.window.localStorage.getItem(m.hook().draft!.key);
    await act(async () => { m.hook().edit((doc) => ({ ...doc, title: "Do not overwrite" })); assert.equal(await m.hook().persist(), false); });
    assert.equal(m.hook().notebook!.title, "Test notebook");
    assert.equal(m.dom.window.localStorage.getItem(m.hook().draft!.key), before);
    assert.equal(m.requests.filter((request) => request.method === "PUT").length, 0);
    await act(async () => { m.hook().restoreDraft(); });
    assert.equal(m.hook().notebook!.title, "Clock-skewed edits");
    assert.equal(m.hook().notebook!.version, 3);
  } finally { await m.cleanup(); }
  const ui = await mount({ ...options, openNotebook: true });
  try {
    assert.match(ui.host.textContent!, /base version 1 · saved elsewhere since/);
    assert.equal(ui.host.querySelector<HTMLInputElement>('[aria-label="Notebook title"]')!.disabled, true);
    await click(button(ui.host, "Discard draft"));
    assert.equal(ui.dom.window.localStorage.length, 0);
    assert.equal(ui.host.querySelector<HTMLInputElement>('[aria-label="Notebook title"]')!.disabled, false);
  } finally { await ui.cleanup(); }
});

test("identical draft content is not offered even if its timestamp is newer", async () => {
  const m = await mount({ drafts: [{ title: "Test notebook", tab: "other", version: 1, time: Date.now() + 100000 }] }, true);
  try { assert.equal(m.hook().draft, null); } finally { await m.cleanup(); }
});

test("tabs store independent drafts, offer the newest difference, and save only clears the saving tab", async () => {
  const m = await mount({}, true);
  try {
    const doc = m.hook().notebook!, storage = m.dom.window.localStorage;
    for (const [tab, title, time] of [["tab-a", "Tab A edits", 100], ["tab-b", "Tab B edits", 200]] as const) {
      m.dom.window.sessionStorage.setItem("dime_notebook_drafts_v1:tab", tab);
      writeNotebookDraft({ ...doc, title }, 1);
      const key = `dime_notebook_drafts_v1:${doc.id}:${tab}:1`;
      storage.setItem(key, JSON.stringify({ ...JSON.parse(storage.getItem(key)!), saved_at: time }));
    }
    assert.equal(findNotebookDraft(doc)!.notebook.title, "Tab B edits");
    const keyA = `dime_notebook_drafts_v1:${doc.id}:tab-a:1`, originalA = storage.getItem(keyA);
    await act(async () => { m.hook().edit((current) => ({ ...current, title: "Tab B saved" })); assert.equal(await m.hook().persist(), true); });
    assert.equal(storage.getItem(keyA), originalA);
    assert.equal(storage.getItem(`dime_notebook_drafts_v1:${doc.id}:tab-b:1`), null);
    assert.equal(findNotebookDraft(m.hook().notebook!)!.notebook.title, "Tab A edits");
  } finally { await m.cleanup(); }
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

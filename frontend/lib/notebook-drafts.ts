import type { Notebook } from "./notebooks";

const KEY = "dime_notebook_drafts_v1";
interface Draft { notebook: Notebook; base_version: number; saved_at: number; key: string; legacy?: string }
const memory = new Map<string, string>();
let fallbackTab = "";

function tabId(): string {
  try {
    let id = window.sessionStorage.getItem(`${KEY}:tab`);
    if (!id) { id = crypto.randomUUID(); window.sessionStorage.setItem(`${KEY}:tab`, id); }
    return id;
  } catch { return fallbackTab ||= crypto.randomUUID(); }
}
function entries(): [string, string][] {
  try { return [...new Map<string, string>([...Object.keys(window.localStorage).filter((key) => key.startsWith(KEY)).map((key): [string, string] => [key, window.localStorage.getItem(key)!]), ...memory])]; }
  catch { return [...memory]; }
}
function put(key: string, value: string) {
  try { window.localStorage.setItem(key, value); memory.delete(key); } catch { memory.set(key, value); }
}
function remove(key: string) {
  memory.delete(key);
  try { window.localStorage.removeItem(key); } catch {}
}
function content(doc: Notebook): string {
  return JSON.stringify({ title: doc.title, origin: doc.origin ?? null, cells: doc.cells.map((cell) => [cell.id, cell.kind, cell.source, cell.outputs ?? null, cell.executed_at ?? null]) });
}
export function writeNotebookDraft(notebook: Notebook, base_version: number) {
  put(`${KEY}:${notebook.id}:${tabId()}:${base_version}`, JSON.stringify({ notebook, base_version, saved_at: Date.now() }));
}
export function clearNotebookDraft(id: string) {
  const prefix = `${KEY}:${id}:${tabId()}:`;
  for (const [key] of entries()) if (key.startsWith(prefix)) remove(key);
}
export function discardNotebookDraft(draft: Draft) {
  if (!draft.legacy) { remove(draft.key); return; }
  try {
    const legacy = JSON.parse(window.localStorage.getItem(KEY) || "{}");
    delete legacy[draft.legacy];
    put(KEY, JSON.stringify(legacy));
  } catch {}
}
export function findNotebookDraft(notebook: Notebook): Draft | null {
  const drafts: Draft[] = [];
  for (const [key, raw] of entries()) {
    try {
      const value = JSON.parse(raw);
      const candidates = key === KEY ? Object.entries(value || {}).map(([legacy, draft]) => ({ ...draft as object, legacy })) : [value];
      for (const draft of candidates) {
        const doc = draft?.notebook;
        if (doc?.id !== notebook.id || !Number.isInteger(draft.base_version) || draft.base_version < 1 ||
            !Number.isFinite(draft.saved_at) || typeof doc.title !== "string" || !Array.isArray(doc.cells) || doc.cells.length > 100 ||
            !doc.cells.every((cell: Notebook["cells"][number]) => cell && typeof cell.id === "string" && typeof cell.source === "string" && ["markdown", "sql", "python"].includes(cell.kind))) continue;
        if (content(doc) !== content(notebook)) drafts.push({ ...draft, key });
      }
    } catch {}
  }
  return drafts.sort((a, b) => b.saved_at - a.saved_at)[0] || null;
}

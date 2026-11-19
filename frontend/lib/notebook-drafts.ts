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
function put(key: string, value: string): boolean {
  try { window.localStorage.setItem(key, value); memory.delete(key); return true; } catch { memory.set(key, value); return false; }
}
function remove(key: string) {
  memory.delete(key);
  try { window.localStorage.removeItem(key); } catch {}
}
function content(doc: Notebook): string {
  return JSON.stringify({ title: doc.title, origin: doc.origin ?? null, cells: doc.cells.map((cell) => [cell.id, cell.kind, cell.source, cell.outputs ?? null, cell.executed_at ?? null]) });
}
export function writeNotebookDraft(notebook: Notebook, base_version: number, source?: Draft) {
  const key = `${KEY}:${notebook.id}:${tabId()}:${base_version}`;
  const durable = put(key, JSON.stringify({ notebook, base_version, saved_at: Date.now() }));
  if (durable && source && (source.legacy || source.key !== key)) discardNotebookDraft(source);
  return durable;
}
export function clearNotebookDraft(id: string, saved?: Notebook) {
  const prefix = `${KEY}:${id}:${tabId()}:`;
  for (const [key] of entries()) if (key.startsWith(prefix)) remove(key);
  if (saved) for (const draft of readNotebookDrafts(saved)) if (content(draft.notebook) === content(saved)) discardNotebookDraft(draft);
}
export function discardNotebookDraft(draft: Draft) {
  if (!draft.legacy) { remove(draft.key); return; }
  try {
    const legacy = JSON.parse(entries().find(([key]) => key === KEY)?.[1] || "{}");
    delete legacy[draft.legacy];
    put(KEY, JSON.stringify(legacy));
  } catch {}
}
function readNotebookDrafts(notebook: Notebook): Draft[] {
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
        drafts.push({ ...draft, key });
      }
    } catch {}
  }
  return drafts;
}
export function findNotebookDraft(notebook: Notebook): Draft | null {
  return readNotebookDrafts(notebook).filter((draft) => content(draft.notebook) !== content(notebook)).sort((a, b) => b.saved_at - a.saved_at)[0] || null;
}

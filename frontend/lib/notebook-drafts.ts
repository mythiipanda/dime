import type { Notebook } from "./notebooks";

const KEY = "dime_notebook_drafts_v1";
interface Draft { notebook: Notebook; base_version: number; saved_at: number }
let memory: Record<string, Draft> = {};

function read(): Record<string, Draft> {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(KEY) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, Draft> : {};
  } catch { return memory; }
}
function write(value: Record<string, Draft>) {
  memory = value;
  try { window.localStorage.setItem(KEY, JSON.stringify(value)); } catch {}
}
export function writeNotebookDraft(notebook: Notebook, base_version: number) {
  write({ ...read(), [`${notebook.id}:${base_version}`]: { notebook, base_version, saved_at: Date.now() } });
}
export function clearNotebookDraft(id: string, base_version: number) {
  const drafts = { ...read() };
  delete drafts[`${id}:${base_version}`];
  write(drafts);
}
export function findNotebookDraft(notebook: Notebook): Draft | null {
  return Object.values(read()).filter((draft) => {
    const doc = draft?.notebook;
    return doc?.id === notebook.id && Number.isInteger(draft.base_version) && draft.base_version > 0 &&
      Number.isFinite(draft.saved_at) && draft.saved_at > Date.parse(notebook.updated_at) &&
      typeof doc.title === "string" && Array.isArray(doc.cells) && doc.cells.length <= 100 &&
      doc.cells.every((cell) => cell && typeof cell.id === "string" && typeof cell.source === "string" && ["markdown", "sql", "python"].includes(cell.kind));
  }).sort((a, b) => b.saved_at - a.saved_at)[0] || null;
}

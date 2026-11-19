import { BACKEND } from "./chat";
import type { Notebook, NotebookCapabilities, NotebookDraft, PythonResult, SQLResult } from "./notebooks";

export class NotebookError extends Error { constructor(message: string, public status: number) { super(message); } }
async function request<T>(path: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BACKEND}/api/notebooks${path}`, { method, signal, ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new NotebookError(typeof data?.detail === "string" ? data.detail : `Notebook request failed (${response.status}).`, response.status);
  return data as T;
}
export const listNotebooks = (signal?: AbortSignal) => request<{ notebooks: Notebook[] }>("", "GET", undefined, signal).then((d) => d.notebooks);
export const getNotebook = (id: string, signal?: AbortSignal) => request<Notebook>(`/${encodeURIComponent(id)}`, "GET", undefined, signal);
export const createNotebook = (draft: NotebookDraft) => request<Notebook>("", "POST", draft);
export const saveNotebook = (notebook: Notebook) => request<Notebook>(`/${encodeURIComponent(notebook.id)}`, "PUT", { title: notebook.title.trim() || "Untitled notebook", cells: notebook.cells, origin: notebook.origin, version: notebook.version });
export const deleteNotebook = (id: string) => request<void>(`/${encodeURIComponent(id)}`, "DELETE");
export const notebookCapabilities = (signal?: AbortSignal) => request<NotebookCapabilities>("/capabilities", "GET", undefined, signal);
export const runNotebookSQL = (sql: string, page = 0, signal?: AbortSignal) => request<SQLResult>("/sql", "POST", { sql, page, page_size: 100 }, signal);
export const runNotebookPython = (source: string, theme: "dark" | "light", signal?: AbortSignal) => request<PythonResult>("/python", "POST", { source, timeout_s: 30, theme }, signal);
export const exportNotebook = (id: string, fmt: "ipynb" | "json") => request<unknown>(`/${encodeURIComponent(id)}/export?fmt=${fmt}`);

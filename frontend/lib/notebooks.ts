export type CellKind = "markdown" | "sql" | "python";
export interface NotebookCell { id: string; kind: CellKind; source: string; outputs?: unknown; executed_at?: string | null }
export interface Notebook { id: string; title: string; version: number; created_at: string; updated_at: string; cells: NotebookCell[]; origin?: { kind: "chat" | "board"; ref: string } | null }
export interface NotebookDraft { title: string; cells: NotebookCell[]; origin?: Notebook["origin"] }
export interface TypedColumn { name: string; type: string }
export interface SQLResult { columns: TypedColumn[]; rows: Record<string, unknown>[]; page: number; page_size: number; has_more: boolean; ms: number; truncated: boolean }
export interface PythonResult { ok: boolean; stdout: string; stderr: string; error?: string; warnings?: string[]; tables: { columns: TypedColumn[]; rows: Record<string, unknown>[]; row_count: number; truncated: boolean }[]; figures: { mime_type: string; data: string }[] }
export interface NotebookCapabilities { python: { enabled: boolean; message: string; trusted_local_only: boolean } }
export type CellOutput = { kind: "snapshot"; data: Pick<SQLResult, "columns" | "rows" | "truncated"> } | { kind: "sql"; data: SQLResult } | { kind: "python"; data: PythonResult } | { kind: "error"; message: string };
export type SaveState = "saved" | "dirty" | "saving" | "conflict" | "error";
export const saveStateLabel = (state: SaveState) => ({ saved: "Saved", dirty: "Unsaved changes", saving: "Saving…", conflict: "Conflict, reload", error: "Not saved · retry" })[state];

export function newCell(kind: CellKind = "sql", source = ""): NotebookCell { return { id: crypto.randomUUID().replaceAll("-", ""), kind, source }; }
export function updateCell(cells: NotebookCell[], id: string, changes: Partial<Pick<NotebookCell, "source" | "kind" | "outputs" | "executed_at">>): NotebookCell[] {
  return cells.map((cell) => cell.id !== id ? cell : { ...cell, ...("source" in changes && cell.kind !== "markdown" || "kind" in changes ? { outputs: undefined, executed_at: null } : {}), ...changes });
}
export function addCell(cells: NotebookCell[], after: string | null, kind: CellKind = "sql"): NotebookCell[] {
  if (cells.length >= 100) return cells;
  const index = after === null ? cells.length : cells.findIndex((c) => c.id === after) + 1;
  return [...cells.slice(0, index), newCell(kind), ...cells.slice(index)];
}
export function removeCell(cells: NotebookCell[], id: string): NotebookCell[] { return cells.filter((c) => c.id !== id); }
export function moveCell(cells: NotebookCell[], id: string, offset: number): NotebookCell[] {
  const from = cells.findIndex((c) => c.id === id), to = from + offset;
  if (from < 0 || to < 0 || to >= cells.length) return cells;
  const next = [...cells]; next.splice(to, 0, next.splice(from, 1)[0]); return next;
}
export function chartable(rows: Record<string, unknown>[]): boolean {
  const first = rows[0]; return !!first && (("GAME_DATE" in first && "PTS" in first) || ("PLAYER" in first && "PTS" in first) || ("zone" in first && "FG_PCT" in first));
}

const shotSQL = `WITH season_shots AS (
  SELECT * FROM silver_shots WHERE _season = '2025-26'
)
SELECT SHOT_ZONE_BASIC AS zone,
       COUNT(*) AS attempts,
       ROUND(100.0 * SUM(SHOT_MADE_FLAG) / NULLIF(COUNT(*), 0), 1) AS FG_PCT
FROM season_shots
WHERE PLAYER_ID = 2544
GROUP BY SHOT_ZONE_BASIC
ORDER BY attempts DESC`;

export const notebookStarters = [
  { id: "four-factors", title: "Team four factors", tag: "Team evaluation", description: "Shooting, ball security, rebounding and free throws. Start from recorded team games.", cells: [
    { kind: "markdown" as const, source: "## The four-factor lens\nCompare team shooting efficiency, turnover rate, offensive rebound share and free-throw rate. This query uses recorded 2025–26 team games, not a guarantee of complete season coverage. Edit the season to explore another sample." },
    { kind: "sql" as const, source: `WITH games AS (
  SELECT *, SUBSTR(MATCHUP, 1, 3) AS team
  FROM silver_team_games WHERE _season = '2025-26'
)
SELECT g.team AS Team, COUNT(*) AS Games,
  ROUND(100.0 * SUM(g.FGM + 0.5 * g.FG3M) / NULLIF(SUM(g.FGA), 0), 1) AS "eFG%",
  ROUND(100.0 * SUM(g.TOV) / NULLIF(SUM(g.FGA + 0.44 * g.FTA + g.TOV), 0), 1) AS "TOV%",
  ROUND(100.0 * SUM(g.OREB) / NULLIF(SUM(g.OREB + opp.DREB), 0), 1) AS "OREB%",
  ROUND(100.0 * SUM(g.FTA) / NULLIF(SUM(g.FGA), 0), 1) AS "FTr%"
FROM games g JOIN games opp ON g.Game_ID = opp.Game_ID
WHERE g.Team_ID <> opp.Team_ID
GROUP BY g.team ORDER BY "eFG%" DESC` },
  ] },
  { id: "shot-profile", title: "Player shot profile", tag: "Scouting", description: "Explore LeBron James’s shot mix, then turn the same warehouse query into a Python chart.", cells: [
    { kind: "markdown" as const, source: "## Where does the offense come from?\nLeBron James · 2025–26. These are warehouse shot records, not a live feed. Change the player ID in both code cells to compare another player. Python cells are independent: each repeats its data query." },
    { kind: "sql" as const, source: shotSQL },
    { kind: "python" as const, source: `import matplotlib.pyplot as plt\n\ndf = sql("""${shotSQL}""")\nif df.is_empty():\n    raise ValueError("No recorded shots for this player and season. Try another sample.")\nfig, ax = plt.subplots(figsize=(8, 3.5))\nax.barh(df["zone"].to_list()[::-1], df["attempts"].to_list()[::-1], color="#59a69a")\nax.set_xlabel("Recorded attempts")\nax.set_title("LeBron James · Shot profile · 2025–26", loc="left", pad=16)\nax.spines[["top", "right"]].set_visible(False)\nfig.tight_layout()\nshow(df)` },
  ] },
] as const;
export function notebookDraft(starterId?: string): NotebookDraft {
  const starter = notebookStarters.find((s) => s.id === starterId);
  return { title: starter?.title || "Untitled notebook", cells: starter ? starter.cells.map((c) => newCell(c.kind, c.source)) : [newCell("sql", "SELECT PLAYER, TEAM, PPG AS PTS\nFROM silver_player_season\nWHERE _season = '2025-26'\nORDER BY PPG DESC\nLIMIT 10")] };
}
=======
import type { DimeArtifact, TableArtifactPayload, ChartSeriesPayload } from "./dime-stream";
import type { MemoArtifactPayload } from "./stream/types";

export type NotebookCellKind = "sql" | "ask";
export type NotebookCellRow = (string | number | null)[];
export interface NotebookCellResult {
  columns?: string[];
  rows?: NotebookCellRow[];
  ms?: number;
  capped?: boolean;
  answer?: string;
}
export interface NotebookCell {
  id: string;
  kind: NotebookCellKind;
  source: string;
  result?: NotebookCellResult;
  error?: string;
  ran_at?: string;
}
export interface Notebook {
  id: string;
  title: string;
  cells: NotebookCell[];
  created_at: string;
  updated_at: string;
}

export const MAX_CELLS = 40;
export const MAX_STORED_ROWS = 100;
export const MAX_CONTEXT_ROWS = 10;

const KEY = "dime_notebooks_v1";
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string";
const date = (value: unknown) => text(value) && Number.isFinite(Date.parse(value));

function validResult(value: unknown, kind: NotebookCellKind): value is NotebookCellResult {
  if (!object(value)) return false;
  if (value.ms !== undefined && !(typeof value.ms === "number" && Number.isFinite(value.ms))) return false;
  if (value.capped !== undefined && typeof value.capped !== "boolean") return false;
  if (value.answer !== undefined && !text(value.answer)) return false;
  if (value.columns !== undefined && (!Array.isArray(value.columns) || value.columns.length > 60 || !value.columns.every(text))) return false;
  if (value.rows !== undefined) {
    if (!Array.isArray(value.rows) || value.rows.length > MAX_STORED_ROWS) return false;
    for (const row of value.rows)
      if (!Array.isArray(row) || row.length > 60 || !row.every(v => v === null || typeof v === "string" || (typeof v === "number" && Number.isFinite(v)))) return false;
  }
  if (kind === "sql" && value.answer !== undefined) return false;
  if (kind === "ask" && (value.columns !== undefined || value.rows !== undefined)) return false;
  return true;
}

export function validNotebook(value: unknown): value is Notebook {
  if (!object(value) || !text(value.id) || !value.id || !text(value.title) || value.title.length > 160 || !date(value.created_at) || !date(value.updated_at)) return false;
  if (!Array.isArray(value.cells) || value.cells.length > MAX_CELLS) return false;
  const ids = new Set<string>();
  for (const cell of value.cells) {
    if (!object(cell) || !text(cell.id) || !cell.id || ids.has(cell.id) || (cell.kind !== "sql" && cell.kind !== "ask") || !text(cell.source) || cell.source.length > 8000) return false;
    if (cell.error !== undefined && !text(cell.error)) return false;
    if (cell.ran_at !== undefined && !date(cell.ran_at)) return false;
    if (cell.result !== undefined && !validResult(cell.result, cell.kind)) return false;
    ids.add(cell.id);
  }
  return true;
}

let memory: string | null = null;
let failedStorage: Storage | null = null;
let memoryStorage: Storage | null = null;
let persistedSnapshot: string | null = null;
function storage(): Storage | null { try { return typeof window === "undefined" ? null : window.localStorage; } catch { return null; } }
function read(): Notebook[] {
  const store = storage();
  let raw = memory;
  if (store) { try { const persisted = store.getItem(KEY); raw = store === memoryStorage && persisted === persistedSnapshot ? memory : persisted; } catch {} }
  try {
    const parsed: unknown = JSON.parse(raw || "null");
    if (!object(parsed) || parsed.version !== 1 || !Array.isArray(parsed.notebooks)) return [];
    return parsed.notebooks.filter(validNotebook).filter((nb, i, all) => all.findIndex((n) => n.id === nb.id) === i);
  } catch { return []; }
}
function write(notebooks: Notebook[]) {
  memory = JSON.stringify({ version: 1, notebooks });
  const store = storage();
  memoryStorage = null;
  if (store) {
    try { persistedSnapshot = store.getItem(KEY); memoryStorage = store; } catch {}
    try { store.setItem(KEY, memory); persistedSnapshot = memory; memoryStorage = store; failedStorage = null; } catch { failedStorage = store; }
  }
  if (typeof window !== "undefined") window.dispatchEvent(new window.Event("dime:notebooks"));
}
export function notebooksArePersistent(): boolean { const store = storage(); return !!store && store !== failedStorage; }
export function listNotebooks(): Notebook[] { return read().sort((a, b) => b.updated_at.localeCompare(a.updated_at)); }
export function getNotebook(id: string): Notebook | null { return read().find((n) => n.id === id) || null; }
export function saveNotebook(notebook: Notebook): Notebook {
  const saved = { ...notebook, title: notebook.title.trim() || "Untitled notebook", updated_at: new Date().toISOString() };
  if (!validNotebook(saved)) throw new Error("This notebook could not be saved: invalid document.");
  write([saved, ...read().filter((n) => n.id !== saved.id)]);
  return saved;
}
export function deleteNotebook(id: string) { write(read().filter((n) => n.id !== id)); }
export function newNotebook(title = "Untitled notebook"): Notebook {
  const now = new Date().toISOString();
  return { id: `notebook-${globalThis.crypto.randomUUID()}`, title, cells: [], created_at: now, updated_at: now };
}
export function duplicateNotebook(notebook: Notebook): Notebook {
  const copy = newNotebook();
  return { ...notebook, id: copy.id, title: `${notebook.title.slice(0, 150)} · copy`, cells: notebook.cells.map(cell => ({ ...cell, id: `cell-${globalThis.crypto.randomUUID()}` })), created_at: copy.created_at, updated_at: copy.updated_at };
}
export function addCell(notebook: Notebook, kind: NotebookCellKind, source = ""): { notebook: Notebook; cell: NotebookCell } {
  if (notebook.cells.length >= MAX_CELLS) return { notebook, cell: notebook.cells[notebook.cells.length - 1] };
  const cell: NotebookCell = { id: `cell-${globalThis.crypto.randomUUID()}`, kind, source };
  return { notebook: { ...notebook, cells: [...notebook.cells, cell] }, cell };
}
export function updateCell(notebook: Notebook, cellId: string, patch: Partial<Omit<NotebookCell, "id" | "kind">>): Notebook {
  return { ...notebook, cells: notebook.cells.map(cell => cell.id === cellId ? { ...cell, ...patch } : cell) };
}
export function removeCell(notebook: Notebook, cellId: string): Notebook {
  return { ...notebook, cells: notebook.cells.filter(cell => cell.id !== cellId) };
}
export function moveCell(notebook: Notebook, from: number, to: number): Notebook {
  if (from < 0 || to < 0 || from >= notebook.cells.length || to >= notebook.cells.length) return notebook;
  const cells = [...notebook.cells];
  cells.splice(to, 0, cells.splice(from, 1)[0]);
  return { ...notebook, cells };
}
export function cellLabel(index: number, kind: NotebookCellKind): string {
  return `Cell ${index + 1} · ${kind === "sql" ? "SQL" : "Ask"}`;
}

function sqlResultTable(result: NotebookCellResult, limit: number): NotebookCellRow[] {
  return (result.rows ?? []).slice(0, limit);
}
export function notebookContext(notebook: Notebook, beforeCellId: string): string {
  const blocks: string[] = [];
  for (const [index, cell] of notebook.cells.entries()) {
    if (cell.id === beforeCellId) break;
    const label = `[${cellLabel(index, cell.kind)}]`;
    if (cell.kind === "sql") {
      const result = cell.result;
      const rows = result ? sqlResultTable(result, MAX_CONTEXT_ROWS) : [];
      const more = result?.rows && result.rows.length > rows.length ? ` (${result.rows.length - rows.length} more rows)` : "";
      blocks.push(`${label}\nSQL:\n${cell.source}\nResult: ${result ? `${(result.rows ?? []).length} rows, ${result.ms ?? "?"}ms${result.capped ? ", capped" : ""}${more}\n${(result.columns ?? []).join(" | ")}\n${rows.map(row => row.map(v => v === null ? "NULL" : String(v)).join(" | ")).join("\n")}` : `not run${cell.error ? ` (error: ${cell.error})` : ""}`}`);
    } else {
      blocks.push(`${label}\nQuestion: ${cell.source}\nAnswer: ${cell.result?.answer ?? `not run${cell.error ? ` (error: ${cell.error})` : ""}`}`);
    }
  }
  return blocks.join("\n\n");
}
export function askCellPrompt(notebook: Notebook, cell: NotebookCell): string {
  const context = notebookContext(notebook, cell.id);
  return [
    context ? `You are answering a question inside an analyst notebook. Earlier cells provide context:\n\n${context}\n\n` : "You are answering a question inside an analyst notebook.\n\n",
    `Question: ${cell.source}\nAnswer it; the warehouse is the source of record for any new data, and note when the notebook's earlier cells already contain what you need.`,
  ].join("");
}

export function sqlCellChart(result: NotebookCellResult): { series: ChartSeriesPayload[]; xLabels: string[] } | null {
  const columns = result.columns ?? [], rows = result.rows ?? [];
  if (!columns.length || !rows.length) return null;
  const numeric = columns.map((name, i) => ({ name, i, numeric: rows.some(row => typeof row[i] === "number") })).filter(col => col.numeric).slice(0, 4);
  if (!numeric.length) return null;
  const labelIndex = columns.findIndex((name, i) => !numeric.some(col => col.i === i) && rows.some(row => typeof row[i] === "string"));
  const xLabels = rows.slice(0, 40).map((row, i) => labelIndex >= 0 && typeof row[labelIndex] === "string" ? String(row[labelIndex]) : `Row ${i + 1}`);
  const series: ChartSeriesPayload[] = numeric.map((col, i) => ({ name: col.name, values: rows.slice(0, 40).map(row => typeof row[col.i] === "number" ? row[col.i] as number : null), ...(i ? { tone: "muted" as const } : {}) }));
  return { series, xLabels };
}

export function cellArtifact(notebook: Notebook, cell: NotebookCell, index: number): DimeArtifact | null {
  if (cell.kind === "sql" && cell.result?.columns) {
    const artifact: TableArtifactPayload = {
      kind: "table",
      title: `${notebook.title} · ${cellLabel(index, "sql")}`,
      columns: cell.result.columns.map(name => ({ key: name, label: name, numeric: cell.result?.rows?.some(row => typeof row[cell.result!.columns!.indexOf(name)] === "number") || undefined })),
      rows: (cell.result.rows ?? []).map(row => row.map(v => v === null ? "" : v)),
      provenance: { origin: "warehouse", capability: "sql_rerun", sql: cell.source, as_of: cell.ran_at, liveSources: [] },
    };
    return artifact;
  }
  if (cell.kind === "ask" && cell.result?.answer) {
    const artifact: MemoArtifactPayload = {
      kind: "memo",
      title: `${notebook.title} · ${cellLabel(index, "ask")}`,
      text: `Q: ${cell.source}\n\n${cell.result.answer}`,
      provenance: { origin: "warehouse", capability: "analyst", as_of: cell.ran_at, liveSources: [] },
    };
    return artifact;
  }
  return null;
}
export function notebookArtifact(notebook: Notebook): DimeArtifact {
  const artifact: MemoArtifactPayload = {
    kind: "memo",
    title: `${notebook.title} (notebook)`,
    text: notebookMarkdown(notebook),
    provenance: { origin: "warehouse", capability: "notebook", as_of: notebook.updated_at, liveSources: [] },
  };
  return artifact;
}

const day = (iso?: string) => iso ? new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "never";
export function notebookMarkdown(notebook: Notebook): string {
  const lines: string[] = [`# ${notebook.title}`, "", `Notebook · ${notebook.cells.length} cells · updated ${day(notebook.updated_at)}`, ""];
  notebook.cells.forEach((cell, index) => {
    lines.push(`## ${cellLabel(index, cell.kind)}`, "");
    if (cell.kind === "sql") {
      lines.push("```sql", cell.source, "```", "");
      const result = cell.result;
      if (result?.columns) {
        lines.push(`| ${result.columns.join(" | ")} |`, `| ${result.columns.map(() => "---").join(" | ")} |`);
        for (const row of sqlResultTable(result, 20)) lines.push(`| ${row.map(v => v === null ? "—" : String(v)).join(" | ")} |`);
        if ((result.rows ?? []).length > 20) lines.push("", `_${(result.rows ?? []).length - 20} more rows not shown._`);
        lines.push("", `Source: sql_rerun · ran ${day(cell.ran_at)} · ${result.ms ?? "?"}ms${result.capped ? " · row cap applied" : ""}`);
      } else {
        lines.push(`Not run${cell.error ? `: ${cell.error}` : "."}`);
      }
    } else {
      lines.push(`**Question:** ${cell.source}`, "");
      lines.push(cell.result?.answer ?? `Not run${cell.error ? `: ${cell.error}` : "."}`, "", `Source: Dime answer · ran ${day(cell.ran_at)}`);
    }
    lines.push("");
  });
  return lines.join("\n");
}
>>>>>>> origin/dev

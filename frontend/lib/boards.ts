export type MetricCategory = "Scoring" | "Efficiency" | "Playmaking" | "Rebounding" | "Defense" | "Impact" | "Contract";
export interface BoardMetric {
  id: string; label: string; category: MetricCategory;
  unit: "per_game" | "pct" | "rating" | "usd" | "count";
  table: string; column: string; higher_is_better: boolean; definition: string;
}
export interface BoardPresentation {
  label: string; unit: BoardMetric["unit"]; format: "currency" | "percent" | "integer" | "decimal";
}
export interface BoardColumn { metric_id: string; presentation?: BoardPresentation }
export function metricPresentation(metric: BoardMetric): BoardPresentation {
  return { label: metric.label, unit: metric.unit, format: metric.unit === "usd" ? "currency" : metric.unit === "pct" ? "percent" : metric.unit === "count" ? "integer" : "decimal" };
}
export interface BoardCitation {
  table: string | null; column: string | null; season: string;
  sql: string | null; params: unknown[]; source: string | null; fetched_at: string | null;
  row_key: Record<string, unknown>; salary_vintage?: { season: string; fetched_at: string | null };
  identity_resolution?: Record<string, unknown>;
}
export interface BoardCell { value: number | null; reason?: string; citation: BoardCitation }
export type BoardCells = Record<string, Record<string, BoardCell>>;
export interface BoardRow { player_id: number; name: string; team: string }
export interface Board {
  id: string; title: string; season: string; rows: BoardRow[]; columns: BoardColumn[];
  cells: BoardCells; created_at: string; updated_at: string; template_id?: string;
}
export interface BoardFill {
  ok: boolean; cells: BoardCells; players: Record<string, { name: string | null; team: string | null }>;
}
export interface BoardSeed extends BoardFill { player_ids: number[] }
export interface BoardTemplate {
  id: string; title: string; summary: string; tag: string; columns: string[];
  seed?: { metric_id: string; n: number; min_mpg?: number; min_gp?: number };
}
export const boardTemplates: readonly BoardTemplate[] = [
  { id: "scoring-guards", title: "Scoring guards", summary: "Scoring volume, shot efficiency and creation. A starting pool to refine, not a position filter.", tag: "Scoring & creation", seed: { metric_id: "ppg", n: 10, min_mpg: 20 }, columns: ["ppg", "ts_pct", "usg_pct", "ast_pct", "fg3_pct", "salary_2026_27"] },
  { id: "rim-protectors", title: "Rim protectors", summary: "Start with shot blockers. Compare rebounding share and defensive impact.", tag: "Defense", seed: { metric_id: "bpg", n: 10, min_mpg: 15 }, columns: ["bpg", "reb_pct", "def_rating", "mpg", "salary_2026_27"] },
  { id: "playmakers", title: "Playmakers", summary: "Find the creators. Put assist volume, usage and ball security side by side.", tag: "Player evaluation", seed: { metric_id: "apg", n: 10, min_mpg: 20 }, columns: ["apg", "ast_pct", "ast_to", "tov_pct", "usg_pct"] },
  { id: "value-contracts", title: "Value contracts", summary: "An affordable starting pool. Weigh salary against on-court impact and opportunity.", tag: "Roster planning", seed: { metric_id: "salary_2026_27", n: 10 }, columns: ["salary_2026_27", "net_rating", "pie", "gp", "mpg"] },
  { id: "blank", title: "Blank board", summary: "Your question, your shortlist. Choose players and the metrics that matter.", tag: "Start from scratch", columns: [] },
];

const KEY = "dime_boards_v1";
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string";
const nullableText = (value: unknown) => value === null || text(value);
const season = (value: unknown) => text(value) && /^\d{4}-\d{2}$/.test(value);
const date = (value: unknown) => text(value) && Number.isFinite(Date.parse(value));
export function validBoard(value: unknown): value is Board {
  if (!object(value) || !text(value.id) || !value.id || !text(value.title) || value.title.length > 160 || !season(value.season) || !date(value.created_at) || !date(value.updated_at) || (value.template_id !== undefined && !text(value.template_id))) return false;
  if (!Array.isArray(value.rows) || value.rows.length > 50 || !Array.isArray(value.columns) || value.columns.length > 30 || !object(value.cells)) return false;
  const rowIds = new Set<string>(), columnIds = new Set<string>();
  for (const row of value.rows) {
    if (!object(row) || !Number.isSafeInteger(row.player_id) || Number(row.player_id) <= 0 || !text(row.name) || !text(row.team) || rowIds.has(String(row.player_id))) return false;
    rowIds.add(String(row.player_id));
  }
  for (const col of value.columns) {
    if (!object(col) || !text(col.metric_id) || !col.metric_id || columnIds.has(col.metric_id)) return false;
    if (col.presentation !== undefined && (!object(col.presentation) || !text(col.presentation.label) || !["per_game", "pct", "rating", "usd", "count"].includes(String(col.presentation.unit)) || !["currency", "percent", "integer", "decimal"].includes(String(col.presentation.format)))) return false;
    columnIds.add(col.metric_id);
  }
  for (const [pid, cells] of Object.entries(value.cells)) {
    if (!rowIds.has(pid) || !object(cells)) return false;
    for (const [metric, cell] of Object.entries(cells)) {
      if (!columnIds.has(metric) || !object(cell) || !(cell.value === null || (typeof cell.value === "number" && Number.isFinite(cell.value))) || (cell.reason !== undefined && !text(cell.reason)) || !object(cell.citation)) return false;
      const c = cell.citation;
      if (!nullableText(c.table) || !nullableText(c.column) || !season(c.season) || !nullableText(c.sql) || !Array.isArray(c.params) || !nullableText(c.source) || !nullableText(c.fetched_at) || !object(c.row_key)) return false;
      if (c.salary_vintage !== undefined && (!object(c.salary_vintage) || !season(c.salary_vintage.season) || !nullableText(c.salary_vintage.fetched_at))) return false;
      if (c.identity_resolution !== undefined && !object(c.identity_resolution)) return false;
    }
  }
  return true;
}

let memory: string | null = null;
let failedStorage: Storage | null = null;
let memoryStorage: Storage | null = null;
let persistedSnapshot: string | null = null;
function storage(): Storage | null { try { return typeof window === "undefined" ? null : window.localStorage; } catch { return null; } }
function read(): Board[] {
  const store = storage();
  let raw = memory;
  if (store) { try { const persisted = store.getItem(KEY); raw = store === memoryStorage && persisted === persistedSnapshot ? memory : persisted; } catch {} }
  try {
    const parsed: unknown = JSON.parse(raw || "null");
    if (!object(parsed) || parsed.version !== 1 || !Array.isArray(parsed.boards)) return [];
    return parsed.boards.filter(validBoard).filter((board, i, all) => all.findIndex((b) => b.id === board.id) === i);
  } catch { return []; }
}
function write(boards: Board[]) {
  memory = JSON.stringify({ version: 1, boards });
  const store = storage();
  memoryStorage = null;
  if (store) {
    try { persistedSnapshot = store.getItem(KEY); memoryStorage = store; } catch {}
    try { store.setItem(KEY, memory); persistedSnapshot = memory; memoryStorage = store; failedStorage = null; } catch { failedStorage = store; }
  }
  if (typeof window !== "undefined") window.dispatchEvent(new window.Event("dime:boards"));
}
export function boardsArePersistent(): boolean { const store = storage(); return !!store && store !== failedStorage; }
export function listBoards(): Board[] { return read().sort((a, b) => b.updated_at.localeCompare(a.updated_at)); }
export function getBoard(id: string): Board | null { return read().find((b) => b.id === id) || null; }
export function saveBoard(board: Board, metrics: BoardMetric[] = []): Board {
  const columns = board.columns.map(column => { const metric = metrics.find(item => item.id === column.metric_id); return metric ? { ...column, presentation: metricPresentation(metric) } : column; });
  const saved = { ...board, columns, title: board.title.trim() || "Untitled board", updated_at: new Date().toISOString() };
  if (!validBoard(saved)) throw new Error("This board could not be saved: invalid document.");
  write([saved, ...read().filter((b) => b.id !== saved.id)]);
  return saved;
}
export function deleteBoard(id: string) { write(read().filter((b) => b.id !== id)); }
export function newBoard(template: BoardTemplate = boardTemplates[4]): Board {
  const now = new Date().toISOString();
  return { id: `board-${globalThis.crypto.randomUUID()}`, title: template.title, season: "2025-26", rows: [], columns: template.columns.map((metric_id) => ({ metric_id })), cells: {}, created_at: now, updated_at: now, template_id: template.id };
}
export function duplicateBoard(board: Board): Board { const copy = newBoard(); return { ...board, id: copy.id, title: `${board.title.slice(0, 150)} · copy`, created_at: copy.created_at, updated_at: copy.updated_at }; }
export function addRow(board: Board, row: BoardRow): Board { return board.rows.length >= 50 || board.rows.some((r) => r.player_id === row.player_id) ? board : { ...board, rows: [...board.rows, row] }; }
export function removeRow(board: Board, id: number): Board { return { ...board, rows: board.rows.filter((r) => r.player_id !== id), cells: Object.fromEntries(Object.entries(board.cells).filter(([pid]) => pid !== String(id))) }; }
export function addColumn(board: Board, id: string): Board { return board.columns.length >= 30 || board.columns.some((c) => c.metric_id === id) ? board : { ...board, columns: [...board.columns, { metric_id: id }] }; }
export function removeColumn(board: Board, id: string): Board { return { ...board, columns: board.columns.filter((c) => c.metric_id !== id), cells: Object.fromEntries(Object.entries(board.cells).map(([pid, cells]) => [pid, Object.fromEntries(Object.entries(cells).filter(([key]) => key !== id))])) }; }
function move<T>(items: T[], from: number, to: number): T[] { if (from < 0 || to < 0 || from >= items.length || to >= items.length) return items; const copy = [...items]; copy.splice(to, 0, copy.splice(from, 1)[0]); return copy; }
export const reorderRows = (b: Board, from: number, to: number): Board => ({ ...b, rows: move(b.rows, from, to) });
export const reorderColumns = (b: Board, from: number, to: number): Board => ({ ...b, columns: move(b.columns, from, to) });
export function sortByColumn(board: Board, metric: BoardMetric, bestFirst = true): Board {
  return { ...board, rows: [...board.rows].sort((a, b) => {
    const av = board.cells[a.player_id]?.[metric.id]?.value, bv = board.cells[b.player_id]?.[metric.id]?.value;
    if (av == null) return bv == null ? 0 : 1;
    if (bv == null) return -1;
    return (av - bv) * (metric.higher_is_better === bestFirst ? -1 : 1);
  }) };
}
export function columnPercentiles(board: Board, metric: BoardMetric): Record<string, number> {
  const values = board.rows.map((r) => ({ id: r.player_id, value: board.cells[r.player_id]?.[metric.id]?.value })).filter((r): r is { id: number; value: number } => r.value != null);
  return Object.fromEntries(values.map(({ id, value }) => {
    const worse = values.filter((r) => metric.higher_is_better ? r.value < value : r.value > value).length;
    const ties = values.filter((r) => r.value === value).length;
    return [id, values.length === 1 ? .5 : (worse + (ties - 1) / 2) / (values.length - 1)];
  }));
}
export function boardCsv(board: Board, metrics: BoardMetric[]): string {
  const quote = (v: unknown) => { let s = String(v ?? ""); if (typeof v === "string" && /^[=+@\-\t\r]/.test(s)) s = `'${s}`; return `"${s.replaceAll('"', '""')}"`; };
  const headers = ["Player", "Team", ...board.columns.flatMap((c) => [metrics.find((m) => m.id === c.metric_id)?.label || c.metric_id, `${c.metric_id} citation`])];
  const rows = board.rows.map((r) => [r.name, r.team, ...board.columns.flatMap((c) => { const cell = board.cells[r.player_id]?.[c.metric_id]; return [cell?.value ?? "", cell ? JSON.stringify({ ...cell.citation, ...(cell.reason ? { reason: cell.reason } : {}) }) : "Not filled"]; })]);
  return [headers, ...rows].map((row) => row.map(quote).join(",")).join("\r\n");
}
export function boardPrompt(board: Board, metrics: BoardMetric[]): string {
  return `Analyze my board "${board.title}" for ${board.season}.\nPlayers: ${board.rows.map((r) => `${r.name} (${r.team || "team unknown"}, player_id ${r.player_id})`).join("; ") || "None selected"}.\nMetrics: ${board.columns.map((c) => metrics.find((m) => m.id === c.metric_id)?.label || c.metric_id).join(", ") || "None selected"}.\nCompare trade-offs and identify the most promising targets. Source numbers from the warehouse with citations; state when data is missing. Salary, if requested, is the 2026-27 vintage.`;
}

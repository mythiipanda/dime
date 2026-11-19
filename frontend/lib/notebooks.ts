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

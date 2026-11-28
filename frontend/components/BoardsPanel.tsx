"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowUpRight, Copy, Download, Plus, RefreshCw, Share2, X } from "lucide-react";
import { resolvePlayers, rerunSql, type PlayerHit } from "../lib/api";
import { fillBoardCells, getBoardMetrics, seedBoardRows } from "../lib/boards-api";
import { boardShareToken, startBoardSync } from "../lib/board-objects";
import { shareLink as objectShareLink } from "../lib/objects-client";
import { MintedLink, copyToClipboard } from "./dime/MintedLink";
import { addColumn, addRow, boardCsv, boardPrompt, boardTemplates, boardsArePersistent, duplicateBoard, getBoard, newBoard, removeColumn, removeRow, reorderColumns, reorderRows, saveBoard, sortByColumn, type Board, type BoardMetric, type BoardTemplate } from "../lib/boards";
import { boardReportHtml, boardReportMarkdown, buildBoardReport, refreshBoardPins } from "../lib/board-report";
import { BoardsTable } from "./BoardsTable";
import { SavedBoards } from "./SavedBoards";
import BoardPins from "./BoardPins";
import { Button } from "./ds/Button";
import { Panel, PageHeader } from "./ds/Panel";
import { SegmentedControl } from "./ds/SegmentedControl";
import { StatusPill } from "./ds/StatusPill";
import { TextField } from "./ds/TextField";
import { Dialog, DialogTrigger, DialogContent, DialogTitle, DialogDescription, DialogClose } from "./ui/dialog";
import { Popover, PopoverTrigger, PopoverContent } from "./ui/popover";

function boardShape(board: Board): string {
  return JSON.stringify([board.id, board.season, board.rows.map(row => row.player_id).sort(), board.columns.map(column => column.metric_id).sort()]);
}

function AddPlayer({ board, onAdd }: { board: Board; onAdd: (player: PlayerHit) => void }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<PlayerHit[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (query.trim().length < 2) return;
    let active = true;
    const timeout = setTimeout(() => { setLoading(true); void resolvePlayers(query, 6).then(rows => { if (active) { setHits(rows); setLoading(false); } }); }, 200);
    return () => { active = false; clearTimeout(timeout); };
  }, [query]);
  return <Popover><PopoverTrigger asChild><Button size="sm" disabled={board.rows.length >= 50}><Plus size={14} />Add player</Button></PopoverTrigger>
    <PopoverContent align="start" aria-label="Add a player" className="w-80 bg-surface text-ink">
      <TextField autoFocus aria-label="Find a player" placeholder="Search player names…" value={query} onChange={event => { setQuery(event.target.value); setHits([]); setLoading(event.target.value.trim().length >= 2); }} />
      <div aria-live="polite" className="max-h-64 overflow-auto">{query.trim().length < 2 ? <p className="p-3 text-xs text-ink-3">Type at least two characters.</p> : loading ? <p className="p-3 text-xs text-ink-3">Searching players…</p> : hits.length ? hits.map(hit => <Button key={hit.id} variant="quiet" className="w-full justify-start" disabled={board.rows.some(row => row.player_id === hit.id)} onClick={() => { onAdd(hit); setQuery(""); setHits([]); }}>{hit.name}</Button>) : <p className="p-3 text-xs text-ink-3">No players found. Try a full name.</p>}</div>
    </PopoverContent>
  </Popover>;
}

function MetricPicker({ metrics, board, onAdd }: { metrics: BoardMetric[]; board: Board; onAdd: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const filtered = metrics.filter(metric => `${metric.label} ${metric.definition}`.toLowerCase().includes(query.toLowerCase()));
  return <Dialog><DialogTrigger asChild><Button size="sm" disabled={board.columns.length >= 30}><Plus size={14} />Add metric</Button></DialogTrigger>
    <DialogContent className="max-w-lg p-6"><div className="flex items-start justify-between gap-4"><div><DialogTitle className="text-lg font-medium">Choose a metric</DialogTitle><DialogDescription className="mt-2 text-xs text-ink-3">Warehouse-backed definitions. Salary uses the single 2026–27 vintage.</DialogDescription></div><DialogClose asChild><Button size="icon" variant="quiet" aria-label="Close metric picker"><X size={16} /></Button></DialogClose></div>
      <TextField className="my-4" aria-label="Search metrics" placeholder="Search metrics…" value={query} onChange={event => setQuery(event.target.value)} />
      <div className="max-h-[55vh] overflow-auto">{[...new Set(filtered.map(metric => metric.category))].map(category => <section key={category}><h3 className="sticky top-0 bg-surface py-3 text-xs text-ink-3">{category}</h3>{filtered.filter(metric => metric.category === category).map(metric => <div key={metric.id} className="flex items-center gap-3 border-t border-line py-3"><div className="min-w-0 flex-1"><p className="text-sm font-medium">{metric.label}</p><p className="mt-1 text-xs leading-relaxed text-ink-3">{metric.definition}</p></div><Button size="sm" disabled={board.columns.some(column => column.metric_id === metric.id)} onClick={() => onAdd(metric.id)}>{board.columns.some(column => column.metric_id === metric.id) ? "Added" : "Add"}<span className="sr-only"> {metric.label}</span></Button></div>)}</section>)}{!filtered.length && <p role="status" className="py-6 text-sm text-ink-3">No matching metrics.</p>}</div>
    </DialogContent>
  </Dialog>;
}

export function BoardsPanel({ boardId, onOpen, onAsk }: { boardId: string | null; onOpen: (id: string | null) => void; onAsk: (prompt: string, context?: import("../lib/view-context").ViewContext) => void }) {
  const [board, setBoard] = useState<Board | null>(null);
  const [metrics, setMetrics] = useState<BoardMetric[]>([]);
  const [catalogError, setCatalogError] = useState("");
  const [catalogAttempt, setCatalogAttempt] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [retry, setRetry] = useState(0);
  const [sort, setSort] = useState<{ id: string; best: boolean } | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const [exporting, setExporting] = useState(false);
  const latest = useRef<Board | null>(null);
  const seedAbort = useRef<AbortController | null>(null);
  const commit = useCallback((next: Board) => { const saved = saveBoard(next, metrics); latest.current = saved; setBoard(saved); }, [metrics]);
  useEffect(() => { if (latest.current?.id !== boardId) { seedAbort.current?.abort(); setSeeding(false); setError(""); } const next = boardId ? getBoard(boardId) : null; latest.current = next; setBoard(next); setTitleDraft(next?.title || ""); setSort(null); }, [boardId]);
  useEffect(() => { const ctrl = new AbortController(); setCatalogError(""); getBoardMetrics(ctrl.signal).then(setMetrics).catch((e) => { if (!ctrl.signal.aborted) setCatalogError(e instanceof Error ? e.message : "Metric catalog unavailable."); }); return () => ctrl.abort(); }, [catalogAttempt]);
  useEffect(() => () => seedAbort.current?.abort(), []);
  useEffect(() => { if (latest.current && metrics.length) commit(latest.current); }, [metrics, boardId, commit]);
  const signature = board ? boardShape(board) : "";
  useEffect(() => {
    const current = latest.current;
    if (!current?.rows.length || !current.columns.length) { setBusy(false); return; }
    const ctrl = new AbortController(); setBusy(true); setError("");
    fillBoardCells(current.season, current.rows.map((r) => r.player_id), current.columns.map((c) => c.metric_id), ctrl.signal).then((data) => {
      if (ctrl.signal.aborted || !latest.current || boardShape(latest.current) !== boardShape(current)) return;
      const active = latest.current;
      commit({ ...active, cells: data.cells, rows: active.rows.map((r) => ({ ...r, name: data.players[r.player_id]?.name || r.name, team: data.players[r.player_id]?.team || "" })) });
    }).catch((e) => { if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : "Could not fill this board."); }).finally(() => { if (!ctrl.signal.aborted) setBusy(false); });
    return () => ctrl.abort();
  }, [signature, retry, commit]);
  async function populate(current: Board, template: BoardTemplate) {
    if (!template.seed) return;
    seedAbort.current?.abort(); const ctrl = new AbortController(); seedAbort.current = ctrl;
    setSeeding(true); setError("");
    try {
      const result = await seedBoardRows(current.season, template.seed, ctrl.signal);
      if (ctrl.signal.aborted || latest.current?.id !== current.id || latest.current.season !== current.season) return;
      const active = latest.current;
      const seeded = result.player_ids.filter((id) => !active.rows.some((r) => r.player_id === id)).map((id) => ({ player_id: id, name: result.players[id]?.name || `Player ${id}`, team: result.players[id]?.team || "" }));
      commit({ ...active, rows: [...active.rows, ...seeded].slice(0, 50), cells: {} });
      if (!result.player_ids.length) setError("No players matched this template in the selected season. Try another season or add players manually.");
    } catch (e) { if (!ctrl.signal.aborted && latest.current?.id === current.id) setError(e instanceof Error ? e.message : "Could not populate this template."); }
    finally { if (!ctrl.signal.aborted) setSeeding(false); }
  }
  function create(template: BoardTemplate) { const next = saveBoard(newBoard(template), metrics); latest.current = next; setBoard(next); setError(""); onOpen(next.id); if (template.seed) void populate(next, template); }
  const template = boardTemplates.find((t) => t.id === board?.template_id);
  function refresh() { if (board && !board.rows.length && template?.seed) void populate(board, template); else setRetry((n) => n + 1); }
  function exportCsv() { if (!board) return; const url = URL.createObjectURL(new Blob([boardCsv(board, metrics)], { type: "text/csv;charset=utf-8;" })); const a = document.createElement("a"); a.href = url; a.download = `${board.title.replace(/[^a-z0-9-]/gi, "-")}.csv`; a.click(); URL.revokeObjectURL(url); }
  async function exportReport(pdf: boolean) {
    const current = latest.current;
    if (!current) return;
    setExporting(true); setError("");
    try {
      const { board: refreshed, failed } = await refreshBoardPins(current, sql => rerunSql(sql));
      if (refreshed !== current) commit(refreshed);
      if (failed.length) setError(`Re-run failed for ${failed.join(", ")}; pinned values exported.`);
      const report = buildBoardReport(refreshed, metrics);
      const base = current.title.replace(/[^a-z0-9-]/gi, "-");
      if (pdf) {
        const win = window.open("", "_blank");
        if (!win) { setError("Pop-up blocked. Allow pop-ups to export the PDF report."); return; }
        win.document.write(boardReportHtml(report)); win.document.close(); win.print();
      } else {
        const url = URL.createObjectURL(new Blob([boardReportMarkdown(report)], { type: "text/markdown;charset=utf-8;" }));
        const a = document.createElement("a"); a.href = url; a.download = `${base}-report.md`; a.click(); URL.revokeObjectURL(url);
      }
    } finally { setExporting(false); }
  }
  const [share, setShare] = useState<{ phase: "idle" } | { phase: "minting" } | { phase: "minted"; link: string; copied: boolean } | { phase: "error" }>({ phase: "idle" });
  useEffect(() => { startBoardSync(); }, []);
  useEffect(() => { setShare({ phase: "idle" }); }, [boardId]);
  function mintBoardShare() {
    const current = latest.current;
    if (!current || share.phase === "minting") return;
    setShare({ phase: "minting" });
    boardShareToken(current)
      .then((result) => {
        if (!result) throw new Error("share failed");
        setShare({ phase: "minted", link: objectShareLink(result.readToken), copied: false });
      })
      .catch(() => setShare({ phase: "error" }));
  }
  function copyBoardShareLink(link: string) {
    copyToClipboard(link, () => setShare((current) => current.phase === "minted" ? { ...current, copied: true } : current));
  }
  const notice = catalogError || error;
  if (!boardId) return <div className="workspace-page">
    <PageHeader eyebrow="Your shortlist, with evidence" title="Boards" description="Compare players, inspect every source, and keep the work that moves a decision forward." actions={<Button variant="primary" onClick={() => create(boardTemplates[4])}><Plus size={14} />New board</Button>} />
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><h2 className="text-sm font-medium">Start with a template</h2><StatusPill dot={false}>Warehouse-backed · No model required</StatusPill></div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{boardTemplates.map(template => <Panel key={template.id} title={template.title} description={template.summary}><p className="mb-5 text-xs text-ink-3">{template.seed ? `${template.seed.n} players · ${template.columns.length} metrics` : "An open canvas"}</p><Button size="sm" onClick={() => create(template)}>Use {template.title}<ArrowUpRight size={13} /></Button></Panel>)}</div>
    <SavedBoards onOpen={onOpen} />
    {notice && <p role="alert" className="mt-5 text-sm text-red">{notice}<Button size="sm" className="ml-3" onClick={() => setCatalogAttempt(value => value + 1)}>Retry</Button></p>}
    <p className="mt-6 text-xs leading-relaxed text-ink-3">Backed up server-side as you edit — edit access lives in this browser. Missing data stays visible. CSV exports keep the source citations.</p>
  </div>;
  if (!board) return <div className="workspace-page"><PageHeader eyebrow="Local research" title="Board not found" description="This board may have been deleted, or saved in another browser." actions={<Button onClick={() => onOpen(null)}>All boards</Button>} /></div>;
  return <div className="workspace-page">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><Button size="sm" variant="quiet" onClick={() => onOpen(null)}><ArrowLeft size={14} />All boards</Button><StatusPill dot={false}>{boardsArePersistent() ? "Synced server-side" : "Storage unavailable · session only"}</StatusPill></div>
    <PageHeader eyebrow="Player board" title={board.title} description={`${board.rows.length} players · ${board.columns.length} metrics · Evidence attached to every filled value`} />
    <div className="mb-6 flex flex-wrap items-end justify-between gap-5"><div className="w-full max-w-sm"><label htmlFor="board-title" className="mb-2 block text-xs text-ink-3">Board title</label><TextField id="board-title" value={titleDraft} maxLength={160} onChange={event => setTitleDraft(event.target.value)} onBlur={() => { const title = titleDraft.trim() || "Untitled board"; setTitleDraft(title); commit({ ...board, title }); }} onKeyDown={event => { if (event.key === "Enter") event.currentTarget.blur(); }} /></div>
      <div><p className="mb-2 text-xs text-ink-3">Season</p><SegmentedControl label="Board season" options={[...new Set([board.season, "2025-26", "2024-25", "2023-24"])]} value={board.season} onChange={season => { seedAbort.current?.abort(); setSeeding(false); setError(""); commit({ ...board, season, cells: {} }); }} /></div>
    </div>
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div className="flex flex-wrap gap-2"><AddPlayer board={board} onAdd={player => commit(addRow(board, { player_id: player.id, name: player.name, team: "" }))} /><MetricPicker metrics={metrics} board={board} onAdd={id => commit(addColumn(board, id))} /></div><div className="flex flex-wrap gap-2">{board.rows.length > 0 && board.columns.length > 0 && share.phase !== "minted" && <Button size="sm" loading={share.phase === "minting"} onClick={mintBoardShare}><Share2 size={13} />Share</Button>}<Button size="sm" loading={busy || seeding} onClick={refresh}><RefreshCw size={13} />Refresh</Button><Button size="sm" onClick={exportCsv}><Download size={13} />Export CSV</Button><Button size="sm" loading={exporting} onClick={() => void exportReport(false)}>Report (.md)</Button><Button size="sm" loading={exporting} onClick={() => void exportReport(true)}>Report (PDF)</Button><Button size="sm" onClick={() => onOpen(saveBoard(duplicateBoard(board)).id)}><Copy size={13} />Duplicate</Button></div></div>
    {share.phase === "minted" && (
      <div className="mb-5 max-w-xl">
        <MintedLink
          link={share.link}
          copied={share.copied}
          onCopy={copyBoardShareLink}
          note="Live link minted; recipients see this board re-evaluated from the warehouse at open time. Edits you make here keep flowing to the same link."
        />
      </div>
    )}
    {share.phase === "error" && <p role="alert" className="mb-5 text-sm text-red">The share link could not be created. The board itself is unchanged — try again.</p>}
    {notice && <div role="alert" className="mb-5 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-red">{notice}{board.rows.length > 0 && " Cached values have not been refreshed."}</p><Button size="sm" onClick={() => catalogError ? setCatalogAttempt(value => value + 1) : refresh()}>Retry</Button></div>}
    {(busy || seeding) && <p role="status" className="mb-4 text-xs text-ink-3">{seeding ? "Finding the starting player pool…" : "Filling from the warehouse…"}</p>}
    {board.rows.length && board.columns.length ? <BoardsTable board={board} metrics={metrics} loading={busy} sort={sort} onSort={metric => { const best = sort?.id === metric.id ? !sort.best : true; setSort({ id: metric.id, best }); commit(sortByColumn(board, metric, best)); }} onRemoveRow={id => commit(removeRow(board, id))} onRemoveColumn={id => commit(removeColumn(board, id))} onMoveRow={(from, to) => { setSort(null); commit(reorderRows(board, from, to)); }} onMoveColumn={(from, to) => commit(reorderColumns(board, from, to))} /> : <Panel title={seeding ? "Building your starting pool" : !board.rows.length ? "Make room for a better decision." : "Choose what to compare."} description={!board.rows.length ? "Add a player, then choose your metrics. Dime fills the grid from the warehouse." : "Add a metric to see warehouse-backed values."}>{!seeding && !board.rows.length && template?.seed && <Button onClick={() => void populate(board, template)}>Populate template</Button>}</Panel>}
    <BoardPins board={board} onCommit={commit} />
    <div className="mt-5 flex flex-wrap items-start justify-between gap-4"><p className="max-w-lg text-xs leading-relaxed text-ink-3">Click a value to inspect its source. Best marks the strongest rank in this board; defensive rating and salary favor lower values. Salary uses 2026–27 data.</p><Button onClick={() => onAsk(boardPrompt(board, metrics), { kind: "board", summary: `${board.title} · ${board.rows.length} players · ${board.columns.length} metrics`, entities: { title: board.title, season: board.season, players: board.rows.map((row) => ({ player_id: row.player_id, name: row.name })), metrics: board.columns.map((column) => column.metric_id) } })}>Ask Dime about this board<ArrowUpRight size={13} /></Button></div>
  </div>;
}

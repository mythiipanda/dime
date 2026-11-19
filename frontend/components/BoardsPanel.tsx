"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowUpRight, Check, Copy, Database, Download, Plus, Refresh, Search, ViewGrid } from "iconoir-react";
import { getBoardMetrics, fillBoardCells, seedBoardRows, resolvePlayers, type PlayerHit } from "../lib/api";
import { addColumn, addRow, boardCsv, boardPrompt, boardTemplates, boardsArePersistent, duplicateBoard, getBoard, newBoard, removeColumn, removeRow, reorderColumns, reorderRows, saveBoard, sortByColumn, type Board, type BoardMetric, type BoardTemplate } from "../lib/boards";
import { BoardGrid } from "./ds/BoardGrid";
import { Button } from "./ds/Button";
import { Chip } from "./ds/Chip";
import { PageHeader } from "./ds/Panel";
import { TextField } from "./ds/TextField";
import { Shimmer } from "./ds/Shimmer";
import { Popover, PopoverTrigger, PopoverContent } from "./ui/popover";
import { SavedBoards } from "./SavedBoards";

function boardShape(board: Board): string {
  return JSON.stringify([board.id, board.season, board.rows.map((r) => r.player_id).sort(), board.columns.map((c) => c.metric_id).sort()]);
}

function AddPlayer({ board, onAdd }: { board: Board; onAdd: (player: PlayerHit) => void }) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<PlayerHit[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let live = true;
    if (query.trim().length < 2) return;
    const timeout = setTimeout(() => { setLoading(true); resolvePlayers(query, 6).then((rows) => { if (live) { setHits(rows); setLoading(false); } }); }, 200);
    return () => { live = false; clearTimeout(timeout); };
  }, [query]);
  return <Popover><PopoverTrigger className="board-add-button" disabled={board.rows.length >= 50}><Plus width={13} />Add player</PopoverTrigger>
    <PopoverContent align="start" className="w-72 gap-0 border border-line bg-surface p-2 text-ink shadow-overlay ring-0">
      <label className="relative block"><Search width={14} className="absolute left-3 top-3 text-ink-3" /><TextField autoFocus className="w-full pl-9" aria-label="Find a player" placeholder="Search player names…" value={query} onChange={(e) => { setQuery(e.target.value); setHits([]); setLoading(e.target.value.trim().length >= 2); }} /></label>
      <div className="mt-2 max-h-64 overflow-y-auto" aria-live="polite">{query.trim().length < 2 ? <p className="p-3 text-[11px] text-ink-3">Type at least two characters to search.</p> : loading ? <p className="p-3 text-[11px] text-ink-3">Searching players…</p> : hits.length ? hits.map((hit) => { const added = board.rows.some((r) => r.player_id === hit.id); return <button key={hit.id} disabled={added} className="flex w-full items-center justify-between rounded-md px-3 py-2.5 text-left text-[12px] hover:bg-hover disabled:text-ink-3" onClick={() => { onAdd(hit); setQuery(""); setHits([]); }}>{hit.name}{added ? <Check width={13} /> : <Plus width={13} />}</button>; }) : <p className="p-3 text-[11px] text-ink-3">No players found. Try a full name.</p>}</div>
    </PopoverContent>
  </Popover>;
}

function MetricPicker({ metrics, board, onAdd }: { metrics: BoardMetric[]; board: Board; onAdd: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const filtered = metrics.filter((m) => `${m.label} ${m.definition}`.toLowerCase().includes(query.toLowerCase()));
  return <Popover><PopoverTrigger className="board-add-button" disabled={board.columns.length >= 30}><Plus width={13} />Add metric</PopoverTrigger>
    <PopoverContent align="start" className="w-[min(360px,calc(100vw-32px))] gap-0 border border-line bg-surface p-2 text-ink shadow-overlay ring-0">
      <TextField autoFocus aria-label="Search metrics" placeholder="Search metrics…" value={query} onChange={(e) => setQuery(e.target.value)} />
      <div className="mt-2 max-h-[420px] overflow-y-auto">{[...new Set(filtered.map((m) => m.category))].map((category) => <section key={category}><h3 className="sticky top-0 bg-surface px-3 py-2 text-[10px] uppercase tracking-widest text-ink-3">{category}</h3>{filtered.filter((m) => m.category === category).map((metric) => { const selected = board.columns.some((c) => c.metric_id === metric.id); return <button key={metric.id} disabled={selected} onClick={() => onAdd(metric.id)} className="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-hover disabled:opacity-45"><span className="flex-1"><span className="block text-[12px] font-medium">{metric.label}</span><span className="mt-1 block text-[11px] leading-relaxed text-ink-3">{metric.definition}</span></span>{selected ? <Check width={13} className="mt-1" /> : <Plus width={13} className="mt-1" />}</button>; })}</section>)}{!filtered.length && <p className="p-3 text-[12px] text-ink-3">No matching metrics.</p>}</div>
    </PopoverContent>
  </Popover>;
}

export function BoardsPanel({ boardId, onOpen, onAsk }: { boardId: string | null; onOpen: (id: string | null) => void; onAsk: (prompt: string) => void }) {
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
  const latest = useRef<Board | null>(null);
  const seedAbort = useRef<AbortController | null>(null);
  const commit = useCallback((next: Board) => { const saved = saveBoard(next); latest.current = saved; setBoard(saved); }, []);
  useEffect(() => { if (latest.current?.id !== boardId) { seedAbort.current?.abort(); setSeeding(false); setError(""); } const next = boardId ? getBoard(boardId) : null; latest.current = next; setBoard(next); setTitleDraft(next?.title || ""); setSort(null); }, [boardId]);
  useEffect(() => { const ctrl = new AbortController(); setCatalogError(""); getBoardMetrics(ctrl.signal).then(setMetrics).catch((e) => { if (!ctrl.signal.aborted) setCatalogError(e instanceof Error ? e.message : "Metric catalog unavailable."); }); return () => ctrl.abort(); }, [catalogAttempt]);
  useEffect(() => () => seedAbort.current?.abort(), []);
  const signature = board ? boardShape(board) : "";
  useEffect(() => {
    const current = latest.current;
    if (!current?.rows.length || !current.columns.length) { setBusy(false); return; }
    const ctrl = new AbortController(); setBusy(true); setError("");
    fillBoardCells(current.season, current.rows.map((r) => r.player_id), current.columns.map((c) => c.metric_id), ctrl.signal).then((data) => {
      if (ctrl.signal.aborted || !latest.current || boardShape(latest.current) !== boardShape(current)) return;
      const active = latest.current;
      commit({ ...active, cells: data.cells, rows: active.rows.map((r) => ({ ...r, name: data.players[r.player_id]?.name || r.name, team: data.players[r.player_id]?.team || r.team })) });
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
  function create(template: BoardTemplate) { const next = saveBoard(newBoard(template)); latest.current = next; setBoard(next); setError(""); onOpen(next.id); if (template.seed) void populate(next, template); }
  const template = boardTemplates.find((t) => t.id === board?.template_id);
  function refresh() { if (board && !board.rows.length && template?.seed) void populate(board, template); else setRetry((n) => n + 1); }
  function exportCsv() { if (!board) return; const url = URL.createObjectURL(new Blob([boardCsv(board, metrics)], { type: "text/csv;charset=utf-8;" })); const a = document.createElement("a"); a.href = url; a.download = `${board.title.replace(/[^a-z0-9-]/gi, "-")}.csv`; a.click(); URL.revokeObjectURL(url); }
  const notice = catalogError || error;
  if (!boardId) return <div className="boards-page">
    <PageHeader eyebrow="A clearer view of your shortlist" title="Boards" description="Build a player grid. Compare the numbers, inspect every source, and keep the work that moves a decision forward." actions={<Button size="sm" variant="primary" onClick={() => create(boardTemplates[4])}><Plus width={14} />New board</Button>} />
    <div className="mb-4 flex items-center justify-between"><h2 className="text-[13px] font-medium">Start with a template</h2><span className="text-[11px] text-ink-3">Warehouse-backed · No model required</span></div>
    <div className="board-templates">{boardTemplates.map((t, index) => <button key={t.id} className="board-template" onClick={() => create(t)}><span className="mb-6 flex items-center justify-between"><span className="board-template-icon"><ViewGrid width={17} /></span><ArrowUpRight width={15} className="text-ink-3" /></span><span className="mb-2 block text-[10px] uppercase tracking-widest text-ink-3">{t.tag}</span><h3 className="text-[14px] font-medium tracking-tight">{t.title}</h3><p className="mt-2 min-h-14 text-[12px] leading-relaxed text-ink-2">{t.summary}</p><span className="mt-5 block border-t border-line pt-3 text-[10px] text-ink-3">{t.seed ? `${t.seed.n} players · ${t.columns.length} metrics` : "An open canvas"}<span className="float-right font-mono">0{index + 1}</span></span></button>)}</div>
    <SavedBoards onOpen={onOpen} />
    <div className="mt-8 flex items-start gap-2 text-[11px] leading-relaxed text-ink-3"><Database width={13} className="mt-0.5 shrink-0" /><p>Every filled value is linked to a warehouse row. Missing data stays visible. Boards are saved in this browser; CSV exports include source citations.</p></div>
  </div>;
  if (!board) return <div className="boards-page"><Button size="sm" variant="quiet" onClick={() => onOpen(null)}><ArrowLeft width={13} />All boards</Button><h1 className="mt-8 text-xl">Board not found</h1><p className="mt-2 text-[13px] text-ink-3">This board may have been deleted, or saved in another browser.</p></div>;
  return <div className="boards-page board-editor">
    <div className="mb-5 flex items-center justify-between"><Button size="xs" variant="quiet" className="-ml-2 text-ink-3" onClick={() => onOpen(null)}><ArrowLeft width={13} />All boards</Button><span className="flex items-center gap-1.5 text-[10px] text-ink-3"><Check width={12} />{boardsArePersistent() ? "Saved on this device" : "Storage unavailable · saved for this session only"}</span></div>
    <div className="flex flex-wrap items-center justify-between gap-4"><div className="min-w-0 flex-1"><p className="mb-2 text-[10px] uppercase tracking-widest text-ink-3">Player board</p><input aria-label="Board title" value={titleDraft} maxLength={160} className="board-title" onChange={(e) => setTitleDraft(e.target.value)} onBlur={() => { const title = titleDraft.trim() || "Untitled board"; setTitleDraft(title); commit({ ...board, title }); }} onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }} /><p className="mt-2 text-[12px] text-ink-3">{board.rows.length} players <span className="mx-1.5">·</span>{board.columns.length} metrics <span className="mx-1.5">·</span>Every value has a source</p></div><label className="flex items-center gap-2 text-[11px] text-ink-3">Season<select aria-label="Board season" value={board.season} className="rounded-lg border border-line bg-surface px-3 py-2 text-[12px] text-ink" onChange={(e) => { seedAbort.current?.abort(); setSeeding(false); setError(""); commit({ ...board, season: e.target.value, cells: {} }); }}>{[...new Set([board.season, "2025-26", "2024-25", "2023-24", "2022-23"])].map((s) => <option key={s}>{s}</option>)}</select></label></div>
    <div className="board-toolbar"><div className="flex items-center gap-2"><AddPlayer board={board} onAdd={(p) => commit(addRow(board, { player_id: p.id, name: p.name, team: "" }))} /><MetricPicker metrics={metrics} board={board} onAdd={(id) => commit(addColumn(board, id))} /></div><div className="flex flex-wrap items-center gap-1"><Button size="xs" variant="quiet" disabled={busy || seeding} onClick={refresh}><Refresh width={12} />Refresh</Button><Button size="xs" variant="quiet" onClick={exportCsv}><Download width={12} />Export CSV</Button><Button size="xs" variant="quiet" onClick={() => { const copy = saveBoard(duplicateBoard(board)); onOpen(copy.id); }}><Copy width={12} />Duplicate</Button></div></div>
    {notice && <div role="alert" className="mb-4 flex items-center justify-between gap-4 rounded-lg border border-line-strong bg-orange-tint px-4 py-3 text-[12px] text-ink"><span>{notice}{board.rows.length > 0 && " Cached values, if shown, have not been refreshed."}</span><Button size="xs" onClick={() => catalogError ? setCatalogAttempt((n) => n + 1) : refresh()}>Retry</Button></div>}
    {(busy || seeding) && <div role="status" className="mb-3 text-[11px]"><Shimmer>{seeding ? "Finding the starting player pool…" : "Filling from the warehouse…"}</Shimmer></div>}
    {board.rows.length > 0 && board.columns.length > 0 ? <BoardGrid board={board} metrics={metrics} loading={busy} sort={sort} onSort={(m) => { const best = sort?.id === m.id ? !sort.best : true; setSort({ id: m.id, best }); commit(sortByColumn(board, m, best)); }} onRemoveRow={(id) => commit(removeRow(board, id))} onRemoveColumn={(id) => commit(removeColumn(board, id))} onMoveRow={(from, to) => { setSort(null); commit(reorderRows(board, from, to)); }} onMoveColumn={(from, to) => commit(reorderColumns(board, from, to))} /> : <div className="board-empty"><span className="board-template-icon mx-auto mb-5"><ViewGrid width={22} /></span><h2 className="text-[17px] font-medium tracking-tight">{seeding ? "Building your starting pool" : !board.rows.length ? "Make room for a better decision." : "Choose what to compare."}</h2><p className="mx-auto mt-3 max-w-sm text-[12px] leading-relaxed text-ink-3">{!board.rows.length ? "Add a player, then choose your metrics. Dime fills the grid from the warehouse and keeps the sources close." : "Add a metric to see warehouse-backed values for your players."}</p>{!seeding && !board.rows.length && template?.seed && <Button size="sm" className="mt-5" onClick={() => void populate(board, template)}>Populate template <ArrowUpRight width={12} /></Button>}</div>}
    <div className="mt-4 flex flex-wrap items-start justify-between gap-4"><div className="flex items-start gap-2 text-[10px] leading-relaxed text-ink-3"><Database width={12} className="mt-0.5 shrink-0" /><p>Click any value to inspect its source. Shading shows relative rank within this board.<br />Higher tint = stronger rank; defensive rating and salary favor lower values. Salary uses 2026–27 data.</p></div><Button size="sm" variant="secondary" onClick={() => onAsk(boardPrompt(board, metrics))}>Ask Dime about this board <ArrowUpRight width={12} /></Button></div>
    <div className="mt-5 flex gap-2"><Chip>Warehouse only</Chip><Chip>No model required</Chip></div>
  </div>;
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowUp, Copy, Download, FilePlus2, MessageCircleQuestion, Play, Plus, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { postChatStream, rerunSql } from "../lib/api";
import { addCell, askCellPrompt, cellArtifact, cellLabel, deleteNotebook, duplicateNotebook, getNotebook, listNotebooks, moveCell, newNotebook, notebookArtifact, notebookMarkdown, notebooksArePersistent, removeCell, saveNotebook, sqlCellChart, updateCell, MAX_STORED_ROWS, type Notebook, type NotebookCell } from "../lib/notebooks";
import type { DimeArtifact } from "../lib/dime-stream";
import ArtifactChart from "./dime/ArtifactChart";
import ArtifactTable from "./dime/ArtifactTable";
import PinButton from "./dime/PinButton";
import { Button } from "./ds/Button";
import { Panel, PageHeader } from "./ds/Panel";
import { StatusPill } from "./ds/StatusPill";
import { TextField } from "./ds/TextField";

const day = (iso?: string) => iso ? new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "never";

function CellView({ notebook, cell, index, onCommit, onBusy }: {
  notebook: Notebook;
  cell: NotebookCell;
  index: number;
  onCommit: (next: Notebook) => void;
  onBusy: (label: string | null) => void;
}) {
  const [draft, setDraft] = useState(cell.source);
  const [running, setRunning] = useState(false);
  useEffect(() => { setDraft(cell.source); }, [cell.id, cell.source]);
  const patch = (value: Partial<Omit<NotebookCell, "id" | "kind">>) => onCommit(updateCell(notebook, cell.id, value));
  const chart = cell.kind === "sql" && cell.result ? sqlCellChart(cell.result) : null;
  const artifact = cellArtifact(notebook, cell, index);

  async function runSql() {
    setRunning(true); onBusy(cellLabel(index, cell.kind));
    try {
      const out = await rerunSql(draft.trim());
      const rows = out.rows.map(row => out.columns.map(col => (row[col] === undefined ? null : row[col]) as string | number | null)).slice(0, MAX_STORED_ROWS);
      patch({ source: draft.trim(), result: { columns: out.columns, rows, ms: out.ms, capped: out.capped || out.rows.length > MAX_STORED_ROWS }, error: undefined, ran_at: new Date().toISOString() });
    } catch (e) {
      patch({ source: draft.trim(), error: e instanceof Error ? e.message : "Query failed.", ran_at: new Date().toISOString() });
    } finally { setRunning(false); onBusy(null); }
  }

  function runAsk() {
    setRunning(true); onBusy(cellLabel(index, cell.kind));
    const prompt = askCellPrompt(notebook, { ...cell, source: draft.trim() });
    let answer = "";
    const ctrl = new AbortController();
    postChatStream(prompt, null, {
      onEvent: (type, data) => { if (type === "final_answer") answer = (data as { text?: string })?.text ?? answer; },
      onDone: () => { patch({ source: draft.trim(), result: { answer }, error: answer ? undefined : "No answer returned.", ran_at: new Date().toISOString() }); setRunning(false); onBusy(null); },
      onError: (message) => { patch({ source: draft.trim(), error: message, ran_at: new Date().toISOString() }); setRunning(false); onBusy(null); },
    }, ctrl.signal, null);
  }

  return <article className="border-b border-line py-5" aria-label={cellLabel(index, cell.kind)}>
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2"><span className="text-xs font-medium text-ink-2">{cellLabel(index, cell.kind)}</span>{cell.ran_at && <span className="text-[11px] text-ink-3">ran {day(cell.ran_at)}</span>}</div>
      <div className="flex items-center gap-1">
        {artifact && <PinButton artifact={artifact} />}
        <Button size="icon" variant="quiet" aria-label={`Move ${cellLabel(index, cell.kind)} up`} disabled={index === 0} onClick={() => onCommit(moveCell(notebook, index, index - 1))}><ArrowUp size={13} /></Button>
        <Button size="icon" variant="quiet" aria-label={`Move ${cellLabel(index, cell.kind)} down`} disabled={index === notebook.cells.length - 1} onClick={() => onCommit(moveCell(notebook, index, index + 1))}><ArrowDown size={13} /></Button>
        <Button size="icon" variant="quiet" aria-label={`Delete ${cellLabel(index, cell.kind)}`} onClick={() => onCommit(removeCell(notebook, cell.id))}><Trash2 size={13} /></Button>
      </div>
    </div>
    <textarea aria-label={cell.kind === "sql" ? "SQL query" : "Question for Dime"} value={draft} rows={Math.min(10, Math.max(3, draft.split("\n").length))} onChange={event => setDraft(event.target.value)} onBlur={() => { if (draft !== cell.source) patch({ source: draft }); }} placeholder={cell.kind === "sql" ? "SELECT … FROM silver_…" : "Ask a question; earlier cells are included as context."} className={`w-full resize-y rounded-md border border-line bg-inset px-3 py-2 text-[13px] leading-relaxed text-ink placeholder:text-ink-3 focus:outline-none focus-visible:outline-2 focus-visible:outline-accent ${cell.kind === "sql" ? "font-mono" : ""}`} />
    <div className="mt-2 flex items-center gap-2">
      <Button size="sm" variant="primary" loading={running} disabled={!draft.trim()} onClick={() => void (cell.kind === "sql" ? runSql() : runAsk())}><Play size={13} />{cell.kind === "sql" ? "Run SQL" : "Ask Dime"}</Button>
      {cell.error && <p role="alert" className="text-xs text-red">{cell.error}</p>}
    </div>
    {cell.kind === "sql" && cell.result?.columns && <div className="mt-3">
      <ArtifactTable title={`${cellLabel(index, "sql")} results`} columns={cell.result.columns.map(name => ({ key: name, label: name, numeric: cell.result?.rows?.some(row => typeof row[(cell.result?.columns ?? []).indexOf(name)] === "number") }))} rows={cell.result.rows ?? []} />
      {chart && <div className="mt-2 rounded-md border border-line"><ArtifactChart title={`${cellLabel(index, "sql")} chart`} series={chart.series} xLabels={chart.xLabels} footnote="Quick chart from the first numeric columns." /></div>}
      <p className="mt-2 text-[11px] text-ink-3">Source: warehouse sql · {(cell.result.rows ?? []).length} rows · {cell.result.ms ?? "?"}ms{cell.result.capped ? " · row cap applied" : ""} · as of {day(cell.ran_at)}</p>
    </div>}
    {cell.kind === "ask" && cell.result?.answer && <div className="mt-3">
      <div className="rounded-md border border-line px-4 py-3 text-[13px] leading-[1.8]"><ReactMarkdown remarkPlugins={[remarkGfm]}>{cell.result.answer}</ReactMarkdown></div>
      <p className="mt-2 text-[11px] text-ink-3">Source: Dime answer · earlier cells included as context · as of {day(cell.ran_at)}</p>
    </div>}
  </article>;
}

export function NotebooksPanel({ notebookId, onOpen }: { notebookId: string | null; onOpen: (id: string | null) => void }) {
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [titleDraft, setTitleDraft] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const latest = useRef<Notebook | null>(null);
  const commit = useCallback((next: Notebook) => { const saved = saveNotebook(next); latest.current = saved; setNotebook(saved); setNotebooks(listNotebooks()); }, []);
  useEffect(() => { setNotebooks(listNotebooks()); }, []);
  useEffect(() => { const update = () => setNotebooks(listNotebooks()); window.addEventListener("dime:notebooks", update); window.addEventListener("storage", update); return () => { window.removeEventListener("dime:notebooks", update); window.removeEventListener("storage", update); }; }, []);
  useEffect(() => { const next = notebookId ? getNotebook(notebookId) : null; latest.current = next; setNotebook(next); setTitleDraft(next?.title || ""); setError(""); }, [notebookId]);

  function create() { const next = saveNotebook(newNotebook()); onOpen(next.id); }
  function add(kind: "sql" | "ask") {
    const current = latest.current;
    if (!current) return;
    const { notebook: next } = addCell(current, kind);
    commit(next);
  }
  function exportMarkdown() {
    const current = latest.current;
    if (!current) return;
    const url = URL.createObjectURL(new Blob([notebookMarkdown(current)], { type: "text/markdown;charset=utf-8;" }));
    const a = document.createElement("a"); a.href = url; a.download = `${current.title.replace(/[^a-z0-9-]/gi, "-")}.md`; a.click(); URL.revokeObjectURL(url);
  }
  const nbArtifact = notebook ? notebookArtifact(notebook) : null;

  if (!notebookId) return <div className="workspace-page">
    <PageHeader eyebrow="Warehouse scratchpad" title="Notebooks" description="SQL cells and Dime questions in one place; every cell keeps its provenance." actions={<Button variant="primary" onClick={create}><Plus size={14} />New notebook</Button>} />
    <section aria-label="Saved notebooks" className="mt-8"><h2 className="mb-4 text-sm font-medium">Saved notebooks <span className="ml-2 text-ink-3">{notebooks.length}</span></h2>
      {notebooks.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{notebooks.map(nb => <Panel key={nb.id} title={nb.title} description={`${nb.cells.length} cells · updated ${day(nb.updated_at)}`}><div className="flex gap-2"><Button size="sm" onClick={() => onOpen(nb.id)}>Open<span className="sr-only"> {nb.title}</span></Button><Button size="sm" variant="quiet" onClick={() => deleteNotebook(nb.id)}>Delete<span className="sr-only"> {nb.title}</span></Button></div></Panel>)}</div> : <p className="text-xs text-ink-3">Notebooks you create will appear here. They stay in this browser.</p>}
    </section>
    <p className="mt-6 text-xs leading-relaxed text-ink-3">SQL cells run against the warehouse. Ask cells send your question to Dime with earlier cells as context.</p>
  </div>;

  if (!notebook) return <div className="workspace-page"><PageHeader eyebrow="Local research" title="Notebook not found" description="This notebook may have been deleted, or saved in another browser." actions={<Button onClick={() => onOpen(null)}>All notebooks</Button>} /></div>;

  return <div className="workspace-page">
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><Button size="sm" variant="quiet" onClick={() => onOpen(null)}><ArrowLeft size={14} />All notebooks</Button><StatusPill dot={false}>{notebooksArePersistent() ? "Saved on this device" : "Storage unavailable · session only"}</StatusPill></div>
    <PageHeader eyebrow="Notebook" title={notebook.title} description={`${notebook.cells.length} cells · provenance on every cell`} />
    <div className="mb-6 flex flex-wrap items-end justify-between gap-5">
      <div className="w-full max-w-sm"><label htmlFor="notebook-title" className="mb-2 block text-xs text-ink-3">Notebook title</label><TextField id="notebook-title" value={titleDraft} maxLength={160} onChange={event => setTitleDraft(event.target.value)} onBlur={() => { const title = titleDraft.trim() || "Untitled notebook"; setTitleDraft(title); commit({ ...notebook, title }); }} onKeyDown={event => { if (event.key === "Enter") event.currentTarget.blur(); }} /></div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => add("sql")}><FilePlus2 size={13} />SQL cell</Button>
        <Button size="sm" onClick={() => add("ask")}><MessageCircleQuestion size={13} />Ask Dime cell</Button>
        <Button size="sm" onClick={exportMarkdown}><Download size={13} />Export (.md)</Button>
        {nbArtifact && <PinButton artifact={nbArtifact} />}
        <Button size="sm" onClick={() => onOpen(saveNotebook(duplicateNotebook(notebook)).id)}><Copy size={13} />Duplicate</Button>
      </div>
    </div>
    {error && <p role="alert" className="mb-4 text-sm text-red">{error}</p>}
    {busy && <p role="status" className="mb-4 text-xs text-ink-3">Running {busy}…</p>}
    {notebook.cells.length ? <div>{notebook.cells.map((cell, index) => <CellView key={cell.id} notebook={notebook} cell={cell} index={index} onCommit={commit} onBusy={setBusy} />)}</div>
      : <Panel title="Start with a cell" description="SQL cells run against the warehouse and keep their rows. Ask cells answer with earlier cells as context. Pin cells or the whole notebook to a board."><div className="flex gap-2"><Button size="sm" onClick={() => add("sql")}><FilePlus2 size={13} />SQL cell</Button><Button size="sm" onClick={() => add("ask")}><MessageCircleQuestion size={13} />Ask Dime cell</Button></div></Panel>}
    <p className="mt-6 max-w-lg text-xs leading-relaxed text-ink-3">Cell outputs are stored locally up to {MAX_STORED_ROWS} rows. Ask cells include earlier cell sources and results as context.</p>
  </div>;
}

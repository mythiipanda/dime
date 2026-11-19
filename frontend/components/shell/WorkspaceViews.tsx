"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Book, ChatBubble, Search } from "iconoir-react";
import TonightView from "../dime/views/TonightView";
import WarehouseView from "../dime/views/WarehouseView";
import { Button } from "../ds/Button";
import { Chip } from "../ds/Chip";
import { PageHeader } from "../ds/Panel";
import { BACKEND } from "../../lib/chat";
import { getClientId, getThreads, type ThreadInfo } from "../../lib/api";

export function HomeView({ onAsk }: { onAsk: () => void }) {
  return <div className="workspace-page">
    <PageHeader eyebrow="Your daily read" title="Around the league" description="The slate, the movement, and the players on your radar. Start with the evidence; build your next decision from here." actions={<Chip>2025–26 season</Chip>} />
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-line bg-inset px-5 py-4"><div><p className="text-[13px] font-medium">Turn a question into a decision.</p><p className="mt-1 text-[12px] text-ink-3">Scouting, matchup analysis, and roster evaluation — start with a question.</p></div><Button size="sm" onClick={onAsk}>Ask Dime <ArrowRight width={13} height={13} /></Button></div>
    <div className="workspace-embedded overflow-hidden rounded-xl border border-line"><TonightView /></div>
  </div>;
}

type LibraryItem = { id: string; title: string; updated: string; meta: string; kind: "thread" | "project" };
type Project = { id: string; goal: string; status: string; updated_at: string };
export function LibraryView({ onThread }: { onThread: (id: string) => void }) {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(false);
    const projectsUrl = `${BACKEND}/api/projects?client=${encodeURIComponent(getClientId())}`;
    Promise.all([getThreads(), fetch(projectsUrl).then(response => { if (!response.ok) throw new Error("Could not load projects"); return response.json() as Promise<{ projects: Project[] }>; })])
      .then(([threads, data]) => {
        if (cancelled) return;
        setItems([
          ...threads.map((item: ThreadInfo): LibraryItem => ({ id: item.id, title: item.title || "Untitled conversation", updated: item.updated, meta: `${item.turns} ${item.turns === 1 ? "turn" : "turns"}`, kind: "thread" })),
          ...(data.projects ?? []).map((item): LibraryItem => ({ id: item.id, title: item.goal || "Untitled project", updated: item.updated_at, meta: item.status, kind: "project" })),
        ].sort((a, b) => b.updated.localeCompare(a.updated)));
      }).catch(() => { if (!cancelled) setError(true); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [attempt]);
  const visible = useMemo(() => items.filter(item => (filter === "all" || item.kind === filter) && `${item.title} ${item.meta}`.toLowerCase().includes(query.toLowerCase())), [items, query, filter]);
  return <div className="workspace-page">
    <PageHeader eyebrow="Your research, organized" title="Library" description="Saved conversations and analyst projects. Pick up a question where you left off." actions={<Chip>{items.length} saved</Chip>} />
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div className="flex gap-1 rounded-lg border border-line bg-inset p-1" aria-label="Library filters">{[["all", "All research"], ["thread", "Conversations"], ["project", "Projects"]].map(([id, label]) => <button key={id} onClick={() => setFilter(id)} aria-pressed={filter === id} className={`rounded-md px-3 py-1.5 text-[12px] ${filter === id ? "bg-surface text-ink shadow-sm" : "text-ink-3 hover:text-ink"}`}>{label}</button>)}</div>
      <label className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2"><Search width={14} height={14} className="text-ink-3" /><input aria-label="Search library" placeholder="Search your research…" value={query} onChange={event => setQuery(event.target.value)} className="min-w-0 bg-transparent text-[12px] outline-none" /></label>
    </div>
    {loading ? <p role="status" className="py-16 text-center text-[13px] text-ink-3">Loading your library…</p> : error ? <div role="alert" className="rounded-xl border border-line bg-surface p-8"><p className="mb-4 text-[13px] text-red">Could not load your library.</p><Button size="sm" onClick={() => setAttempt(value => value + 1)}>Try again</Button></div> : !visible.length ? <div className="rounded-xl border border-dashed border-line-strong bg-surface px-6 py-20 text-center"><Book width={24} height={24} className="mx-auto mb-4 text-ink-3" /><h2 className="mb-2 text-[16px] font-medium">{items.length ? "No matching research" : "Your research starts here"}</h2><p className="text-[13px] text-ink-3">{items.length ? "Try a different search or filter." : "Conversations and projects will appear here as you work with Dime."}</p></div> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{visible.map(item => <article key={`${item.kind}-${item.id}`} className="flex flex-col rounded-xl border border-line bg-surface p-5">
      <div className="mb-5 flex items-center justify-between">{item.kind === "thread" ? <ChatBubble width={19} height={19} className="text-ink-3" /> : <Book width={19} height={19} className="text-ink-3" />}<Chip>{item.kind === "thread" ? "Conversation" : "Project"}</Chip></div>
      <h2 className="mb-2 text-[14px] font-medium leading-relaxed">{item.title}</h2><p className="mb-5 text-[11px] text-ink-3">{item.meta} · {new Date(item.updated).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</p>
      {item.kind === "thread" && <button className="mt-auto flex items-center justify-between border-t border-line pt-3 text-[12px] text-ink-2 hover:text-ink" onClick={() => onThread(item.id)}>Open conversation <ArrowRight width={13} height={13} /></button>}
    </article>)}</div>}
  </div>;
}

export function DataView() {
  return <div className="workspace-page">
    <PageHeader eyebrow="The evidence layer" title="Data" description="Explore the warehouse behind your analysis. Check dataset coverage, freshness, and source rows before drawing a conclusion." actions={<Chip>Warehouse</Chip>} />
    <div className="workspace-embedded overflow-hidden rounded-xl border border-line"><WarehouseView /></div>
  </div>;
}

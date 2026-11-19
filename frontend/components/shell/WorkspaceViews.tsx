"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Book, ChatBubble, Search } from "iconoir-react";
import WarehouseView from "../dime/views/WarehouseView";
import { Button } from "../ds/Button";
import { Chip } from "../ds/Chip";
import { PageHeader } from "../ds/Panel";
import { BACKEND } from "../../lib/chat";
import { getClientId, getThreads, type ThreadInfo } from "../../lib/api";
import { getHomeSnapshot, type HomeSnapshot } from "../../lib/warehouse";

export function HomeContent({ data }: { data: HomeSnapshot }) {
  const { schedule, snapshot } = data;
  return <div className="grid items-start gap-5 lg:grid-cols-2">
    <section className="rounded-xl border border-line bg-surface p-6">
      <div className="mb-6 flex items-center justify-between"><h2 className="text-[15px] font-medium">Today’s schedule</h2><Chip>{data.date} · ET</Chip></div>
      {schedule.games.length ? <div className="divide-y divide-line">{schedule.games.map((game, index) => <div key={String(game.GAME_ID ?? game.id ?? index)} className="py-4"><p className="text-[14px] font-medium">{game.name ? String(game.name) : `${game.VISITOR_TEAM_ABBREVIATION ?? game.VISITOR_TEAM_ID ?? "Away team unavailable"} at ${game.HOME_TEAM_ABBREVIATION ?? game.HOME_TEAM_ID ?? "Home team unavailable"}`}</p><p className="mt-1 text-[12px] text-ink-2">{String(game.GAME_STATUS_TEXT ?? (game.date && Number.isFinite(Date.parse(String(game.date))) ? `${new Date(String(game.date)).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" })} ET` : "Status unavailable"))}{game.HOME_TEAM_PTS != null && game.VISITOR_TEAM_PTS != null ? ` · ${game.VISITOR_TEAM_PTS} – ${game.HOME_TEAM_PTS}` : ""}</p><p className="mt-2 font-mono text-[10px] text-ink-3">{schedule.table} · {String(game._season ?? "Season unavailable")}</p></div>)}</div> : <div className="rounded-lg border border-dashed border-line-strong bg-inset px-5 py-10"><h3 className="text-[17px] font-medium">No games today</h3><p className="mt-2 text-[12px] leading-relaxed text-ink-2">{!schedule.available ? "No schedule source is available in this warehouse." : "No games are cached for today; this is not a live schedule feed."}</p><p className="mt-2 text-[12px] text-ink-3">{schedule.next_date ? `Next scheduled date in the warehouse: ${schedule.next_date}.` : "No future scheduled date is available in the warehouse."}</p></div>}
      <p className="mt-5 font-mono text-[10px] leading-relaxed text-ink-3">Source: {schedule.table} · {schedule.seasons.join(", ") || "No season rows for today"}<br />Fetched: {schedule.last_fetch || "No current schedule timestamp"}</p>
    </section>
    <section className="rounded-xl border border-line bg-surface p-6">
      <div className="mb-5 flex items-center justify-between"><h2 className="text-[15px] font-medium">Team ratings snapshot</h2><Chip>{snapshot.season || "No season"}</Chip></div>
      <p className="mb-4 text-[12px] text-ink-3">Top teams by net rating · latest cached season</p>
      {snapshot.rows.length ? <table className="w-full text-left text-[12px]"><thead className="border-b border-line text-[10px] text-ink-3"><tr><th className="pb-3 font-normal">TEAM</th><th className="pb-3 text-right font-normal">GP</th><th className="pb-3 text-right font-normal">NET RTG</th></tr></thead><tbody className="divide-y divide-line">{snapshot.rows.map(row => <tr key={row.TEAM_NAME}><td className="py-3 text-ink-2">{row.TEAM_NAME}</td><td className="text-right font-mono tabular-nums">{row.GP ?? "—"}</td><td className="text-right font-mono tabular-nums">{row.NET_RATING == null ? "—" : `${row.NET_RATING > 0 ? "+" : ""}${row.NET_RATING.toFixed(1)}`}</td></tr>)}</tbody></table> : <p className="py-8 text-[13px] text-ink-3">No team ratings are cached.</p>}
      <p className="mt-5 border-t border-line pt-4 font-mono text-[10px] leading-relaxed text-ink-3">Source: {snapshot.table} · {snapshot.season || "Season unavailable"}<br />Fetched: {snapshot.last_fetch || "Timestamp unavailable"}</p>
    </section>
  </div>;
}

export function HomeView({ onAsk }: { onAsk: () => void }) {
  const [data, setData] = useState<HomeSnapshot | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setError(false);
    getHomeSnapshot().then(value => { if (active) setData(value); }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [attempt]);
  return <div className="workspace-page">
    <PageHeader eyebrow="Your daily read" title="Around the league" description="The cached schedule and a warehouse-backed league snapshot. Evidence first, with coverage and freshness in view." actions={<Chip>Warehouse snapshot</Chip>} />
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-line bg-inset px-5 py-4"><div><p className="text-[13px] font-medium">Turn a question into a decision.</p><p className="mt-1 text-[12px] text-ink-3">Scouting, matchup analysis, and roster evaluation — start with a guided workflow.</p></div><Button size="sm" onClick={onAsk}>Explore workflows <ArrowRight width={13} height={13} /></Button></div>
    {error ? <div role="alert" className="rounded-xl border border-line p-6"><p className="mb-4 text-[13px] text-red">Could not load the warehouse snapshot. No sample data is substituted.</p><Button size="sm" onClick={() => setAttempt(value => value + 1)}>Try again</Button></div> : data ? <HomeContent data={data} /> : <p role="status" className="py-12 text-[13px] text-ink-3">Loading the warehouse snapshot…</p>}
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
  const [projectsError, setProjectsError] = useState(false);
  const [threadsError, setThreadsError] = useState(false);
  const [cachedThreads, setCachedThreads] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(false); setProjectsError(false); setThreadsError(false);
    const projectsUrl = `${BACKEND}/api/projects?client=${encodeURIComponent(getClientId())}`;
    Promise.allSettled([getThreads({ withStatus: true }), fetch(projectsUrl).then(response => { if (!response.ok) throw new Error("Could not load projects"); return response.json() as Promise<{ projects: Project[] }>; })])
      .then(([threadResult, projectResult]) => {
        if (cancelled) return;
        setProjectsError(projectResult.status === "rejected");
        const threadsFailed = threadResult.status === "rejected" || !!threadResult.value.error;
        setThreadsError(threadsFailed);
        const threads = threadResult.status === "fulfilled" ? threadResult.value.rows : [];
        const projects = projectResult.status === "fulfilled" ? projectResult.value.projects ?? [] : [];
        setCachedThreads(threadResult.status === "fulfilled" && threadResult.value.fromCache && threads.length > 0);
        setError((threadsFailed || projectResult.status === "rejected") && !threads.length && !projects.length);
        setItems([
          ...threads.map((item: ThreadInfo): LibraryItem => ({ id: item.id, title: item.title || "Untitled conversation", updated: item.updated, meta: `${item.turns} ${item.turns === 1 ? "turn" : "turns"}`, kind: "thread" })),
          ...projects.map((item): LibraryItem => ({ id: item.id, title: item.goal || "Untitled project", updated: item.updated_at, meta: item.status, kind: "project" })),
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
    {!loading && !error && projectsError && <p role="status" className="mb-4 text-[12px] text-ink-3">Projects could not be loaded. Conversations are still available. <button className="underline" onClick={() => setAttempt(value => value + 1)}>Retry projects</button></p>}
    {!loading && !error && threadsError && <p role="status" className="mb-4 text-[12px] text-ink-3">Conversations could not be loaded from the server.{cachedThreads ? " Showing cached conversations." : ""} <button className="underline" onClick={() => setAttempt(value => value + 1)}>Retry conversations</button></p>}
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

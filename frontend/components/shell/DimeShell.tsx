"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { HomeSimple, ChatBubble, ViewGrid, Sparks, Book, Database, SunLight, HalfMoon, Search, Xmark } from "iconoir-react";
import { SidebarNav } from "../ds/SidebarNav";
import { Chip } from "../ds/Chip";
import { ChatView } from "./ChatView";
import { getThreads, type ThreadInfo } from "../../lib/api";
import { replayName } from "../../lib/replay";
import WorkflowsPanel from "../WorkflowsPanel";
import ExploreWorkspace from "../ExploreWorkspace";
import { HomeView } from "./HomeView";
import { BriefsLibrary } from "../BriefsLibrary";
import CommandPalette from "../CommandPalette";
import DebateCardModal from "../DebateCardModal";
import { BoardsPanel } from "../BoardsPanel";

const NotebooksPanel = dynamic(() => import("../notebooks/NotebooksPanel"), { ssr: false });

export type ShellTab = "today" | "chat" | "boards" | "notebooks" | "workflows" | "briefs" | "data";
export const shellNavigation = [
  { id: "today", label: "Home", icon: <HomeSimple width={17} height={17} /> },
  { id: "chat", label: "Ask", icon: <ChatBubble width={17} height={17} /> },
  { id: "boards", label: "Boards", icon: <ViewGrid width={17} height={17} /> },
  { id: "notebooks", label: "Notebooks", icon: <Book width={17} height={17} /> },
  { id: "workflows", label: "Workflows", icon: <Sparks width={17} height={17} /> },
  { id: "briefs", label: "Library", icon: <Book width={17} height={17} /> },
  { id: "data", label: "Data", icon: <Database width={17} height={17} /> },
];
export function parseShellTab(value: string | null): ShellTab {
  return shellNavigation.some((n) => n.id === value) ? value as ShellTab : "chat";
}
const newId = () => `t-${crypto.randomUUID().slice(0, 12)}`;

export function DimeShell() {
  const [tab, setTab] = useState<ShellTab>("chat");
  const [thread, setThread] = useState("");
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [preset, setPreset] = useState<string | null>(null);
  const [autoSend, setAutoSend] = useState<{ thread: string; text: string } | null>(null);
  const [replay, setReplay] = useState<string | null>(null);
  const [dark, setDark] = useState(true);
  const [paletteKey, setPaletteKey] = useState(0);
  const [debate, setDebate] = useState(false);
  const [exploreKey, setExploreKey] = useState(0);
  const [boardId, setBoardId] = useState<string | null>(null);
  const [notebookId, setNotebookId] = useState<string | null>(null);
  const syncUrl = (nextTab: ShellTab, nextThread: string, push = true) => {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", nextTab); url.searchParams.set("thread", nextThread);
    url.searchParams.delete("replay");
    url.searchParams.delete("board");
    url.searchParams.delete("notebook");
    window.history[push ? "pushState" : "replaceState"]({}, "", url);
  };
  useEffect(() => {
    const read = () => {
      const params = new URLSearchParams(window.location.search);
      setTab(parseShellTab(params.get("tab")));
      setBoardId(params.get("board"));
      setNotebookId(params.get("notebook"));
      const id = params.get("thread");
      const selected = id && /^[A-Za-z0-9-]{1,64}$/.test(id) ? id : newId();
      setThread(selected); setReplay(replayName(window.location.search));
      if (!id) { const url = new URL(window.location.href); url.searchParams.set("thread", selected); window.history.replaceState({}, "", url); }
      setExploreKey((k) => k + 1);
    };
    read(); setDark(document.documentElement.classList.contains("dark"));
    window.addEventListener("popstate", read);
    return () => window.removeEventListener("popstate", read);
  }, []);
  const reload = useCallback(() => { getThreads().then((server) => setThreads((current) => {
    const merged = new Map(current.map((t) => [t.id, t]));
    server.forEach((t) => merged.set(t.id, t));
    return [...merged.values()].sort((a, b) => b.updated.localeCompare(a.updated));
  })).catch(() => {}); }, []);
  useEffect(() => { reload(); }, [reload]);
  const navigate = (value: string) => { const next = parseShellTab(value); setTab(next); if (next === "boards") setBoardId(null); if (next === "notebooks") setNotebookId(null); setReplay(null); syncUrl(next, thread); };
  const startChat = (text?: string) => {
    const id = newId(); setThread(id); setPreset(null); setTab("chat"); setReplay(null);
    setAutoSend(text ? { thread: id, text } : null);
    if (text) setThreads((current) => [{ id, title: text.split("\n")[0], updated: new Date().toISOString(), turns: 0 }, ...current]);
    syncUrl("chat", id);
  };
  const openBoard = (id: string | null) => {
    setBoardId(id); setTab("boards");
    const url = new URL(window.location.href); url.searchParams.set("tab", "boards");
    if (id) url.searchParams.set("board", id); else url.searchParams.delete("board");
    window.history.pushState({}, "", url);
  };
  const openNotebook = (id: string | null) => {
    setNotebookId(id); setTab("notebooks"); setReplay(null);
    const url = new URL(window.location.href); url.searchParams.set("tab", "notebooks");
    url.searchParams.delete("board"); url.searchParams.delete("replay");
    if (id) url.searchParams.set("notebook", id); else url.searchParams.delete("notebook");
    window.history.pushState({}, "", url);
  };
  const title = tab === "chat" ? threads.find((t) => t.id === thread)?.title || "New chat" : shellNavigation.find((n) => n.id === tab)!.label;
  return <div className="dime-shell">
    <SidebarNav workspace="Dime" items={shellNavigation} activeNav={tab} activeThread={thread} recents={threads.map((t) => ({ id: t.id, label: t.title }))} onNavigate={navigate} onNewChat={() => startChat()} onPick={(id) => { setThread(id); setTab("chat"); setReplay(null); setPreset(null); syncUrl("chat", id); }} footer={<div className="flex items-center justify-between"><span className="text-[11px] text-ink-3">Basketball intelligence</span><Chip>2025–26</Chip></div>} />
    <main className="dime-main">
      <header className="dime-header">
        <div className="dime-top-tab"><span className="max-w-60 truncate">{title}</span><button aria-label="New chat" className="text-ink-3 hover:text-ink" onClick={() => startChat()}><Xmark width={12} height={12} /></button></div>
        <div className="flex items-center gap-1"><button className="icon-button" aria-label="Search commands" onClick={() => setPaletteKey((k) => k + 1)}><Search width={15} height={15} /></button><button className="icon-button" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => { const next = !dark; setDark(next); document.documentElement.classList.toggle("dark", next); try { localStorage.setItem("dime_theme", next ? "dark" : "light"); } catch {} }}>{dark ? <SunLight width={16} height={16} /> : <HalfMoon width={16} height={16} />}</button></div>
      </header>
      <div className="dime-content">
        {tab === "chat" && thread && <ChatView key={`${thread}-${replay || "live"}`} thread={thread} preset={preset} autoSend={autoSend?.thread === thread ? autoSend : null} replay={replay} onConsumed={() => setAutoSend(null)} onRunDone={reload} onOpenNotebook={openNotebook} />}
        {tab === "workflows" && <WorkflowsPanel onRun={startChat} />}
        {tab === "data" && <ExploreWorkspace exploreKey={exploreKey} onAsk={(q) => { setPreset(q); navigate("chat"); }} />}
        {tab === "today" && <HomeView onWorkflows={() => navigate("workflows")} />}
        {tab === "briefs" && <BriefsLibrary onOpenBoard={openBoard} />}
        {tab === "boards" && <BoardsPanel boardId={boardId} onOpen={openBoard} onAsk={(q) => { startChat(); setPreset(q); }} onOpenNotebook={openNotebook} />}
        {tab === "notebooks" && <NotebooksPanel notebookId={notebookId} onOpen={openNotebook} />}
      </div>
    </main>
    <CommandPalette openKey={paletteKey} onAsk={(q) => { setPreset(q); navigate("chat"); }} onTab={navigate} onDebate={() => setDebate(true)} />
    {debate && <DebateCardModal onClose={() => setDebate(false)} />}
  </div>;
}
=======
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Award, BookOpen, ClipboardList, Columns3, Command, Database, Home, MessageCircle, Moon, NotebookText, Search, Sun, Swords, ArrowLeftRight, Workflow, Table2 } from "lucide-react";
import { SidebarNav } from "../ds/SidebarNav";
import DimeCommandPalette, { type PaletteEntry } from "../site/DimeCommandPalette";
import TradesView from "../dime/views/TradesView";
import CompareView from "../dime/views/CompareView";
import DraftView from "../dime/views/DraftView";
import MatchupsView from "../dime/views/MatchupsView";
import AwardsView from "../dime/views/AwardsView";
import { ChatView } from "./ChatView";
import { DataView, HomeView, LibraryView } from "./WorkspaceViews";
import { getThreads, type ThreadInfo } from "../../lib/api";
import WorkflowsPanel from "../WorkflowsPanel";
import { BoardsPanel } from "../BoardsPanel";
import { NotebooksPanel } from "../NotebooksPanel";
import { parseShellTab, shellNavigation, shellUrl, validThread, type ShellTab } from "../../lib/shell-navigation";
import { replayName } from "../../lib/replay";
import { createWorkflowDraft, saveWorkflowDraft } from "../../lib/workflow-drafts";

export { parseShellTab, shellNavigation } from "../../lib/shell-navigation";
const icons = { today: Home, chat: MessageCircle, workflows: Workflow, boards: Table2, notebooks: NotebookText, briefs: BookOpen, data: Database, trades: ArrowLeftRight, compare: Columns3, draft: ClipboardList, matchups: Swords, awards: Award };
const navigation = shellNavigation.map(item => { const Icon = icons[item.id]; return { ...item, icon: <Icon size={17} strokeWidth={1.5} /> }; });

export function DimeShell() {
  const [tab, setTab] = useState<ShellTab>("chat");
  const [thread, setThread] = useState("");
  const [boardId, setBoardId] = useState<string | null>(null);
  const [notebookId, setNotebookId] = useState<string | null>(null);
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [replay, setReplay] = useState<string | null>(null);
  const [palette, setPalette] = useState(false);
  const [dark, setDark] = useState(true);
  const [workflowRequest, setWorkflowRequest] = useState<{ thread: string; text: string } | null>(null);
  const workflowStarting = useRef(false);
  useEffect(() => {
    const read = () => {
      const url = new URL(window.location.href);
      const nextTab = parseShellTab(url.searchParams.get("tab"));
      const candidate = url.searchParams.get("thread");
      const selected = validThread(candidate) ? candidate : crypto.randomUUID();
      setTab(nextTab); setThread(selected); setReplay(replayName(url.search));
      setBoardId(nextTab === "boards" && validThread(url.searchParams.get("board")) ? url.searchParams.get("board") : null);
      setNotebookId(nextTab === "notebooks" && validThread(url.searchParams.get("nb")) ? url.searchParams.get("nb") : null);
      url.searchParams.set("tab", nextTab); url.searchParams.set("thread", selected);
      window.history.replaceState({}, "", url);
    };
    read(); setDark(document.documentElement.classList.contains("dark"));
    window.addEventListener("popstate", read);
    const key = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPalette(true); } };
    window.addEventListener("keydown", key);
    return () => { window.removeEventListener("popstate", read); window.removeEventListener("keydown", key); };
  }, []);
  const reload = useCallback(() => { void getThreads().then(items => setThreads(items.sort((a, b) => b.updated.localeCompare(a.updated)))); }, []);
  useEffect(() => { reload(); }, [reload]);
  const navigate = (nextTab: ShellTab, nextThread = thread) => {
    setTab(nextTab); setThread(nextThread); setReplay(null);
    if (nextTab !== "boards") setBoardId(null);
    if (nextTab !== "notebooks") setNotebookId(null);
    window.history.pushState({}, "", shellUrl(window.location.href, nextTab, nextThread));
  };
  const newChat = () => navigate("chat", crypto.randomUUID());
  const openBoard = (id: string | null) => {
    navigate("boards"); setBoardId(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("board", id); else url.searchParams.delete("board");
    window.history.replaceState({}, "", url);
  };
  const openNotebook = (id: string | null) => {
    navigate("notebooks"); setNotebookId(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("nb", id); else url.searchParams.delete("nb");
    window.history.replaceState({}, "", url);
  };
  const askBoard = (text: string) => {
    const id = crypto.randomUUID();
    saveWorkflowDraft({ ...createWorkflowDraft(id, text), edited: true });
    setWorkflowRequest(null); navigate("chat", id);
  };
  const runWorkflow = (text: string) => {
    if (workflowStarting.current) return;
    workflowStarting.current = true;
    const nextThread = crypto.randomUUID();
    createWorkflowDraft(nextThread, text);
    setWorkflowRequest({ thread: nextThread, text });
    navigate("chat", nextThread);
    queueMicrotask(() => { workflowStarting.current = false; });
  };
  const pick = (id: string) => { if (validThread(id)) navigate("chat", id); };
  const toggleTheme = () => {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next); setDark(next);
    try { window.localStorage.setItem("bui-theme", next ? "dark" : "light"); } catch {  }
  };
  const onRunDone = useCallback((question: string) => {
    setThreads(current => [{ id: thread, title: current.find(item => item.id === thread)?.title || question.slice(0, 80), turns: (current.find(item => item.id === thread)?.turns ?? 0) + 1, updated: new Date().toISOString() }, ...current.filter(item => item.id !== thread)]);
    reload();
  }, [thread, reload]);
  const entries: PaletteEntry[] = [
    ...shellNavigation.map(item => ({ id: item.id, label: item.label, kind: "view" as const, run: () => navigate(item.id) })),
    ...threads.map(item => ({ id: `thread-${item.id}`, label: item.title || "Untitled conversation", kind: "view" as const, run: () => pick(item.id) })),
    { id: "new", label: "New chat", kind: "action", run: newChat },
    { id: "theme", label: "Toggle theme", kind: "action", run: toggleTheme },
  ];
  const label = shellNavigation.find(item => item.id === tab)?.label;
  return <div className="dime-shell">
    <SidebarNav workspace="Dime" items={navigation} activeNav={tab} recents={threads.map(item => ({ id: item.id, label: item.title || "Untitled conversation" }))} activeThread={tab === "chat" ? thread : null} onNavigate={id => navigate(parseShellTab(id))} onNewChat={newChat} onPick={pick} footer={<div className="sidebar-copy mt-4 px-2 pb-2 text-[10px] leading-relaxed text-ink-3"><p className="mb-1 text-ink-2">Your front office, on demand.</p><p>NBA intelligence · Dime</p><button className="mt-3 flex items-center gap-2 hover:text-ink" onClick={() => setPalette(true)}><Command size={12} />Command menu <kbd className="ml-auto">⌘ K</kbd></button></div>} />
    <main className="dime-main">
      <header className="dime-header"><div className="dime-top-tab"><span>{label}</span>{tab === "chat" && <span className="max-w-48 truncate text-ink-3">{threads.find(item => item.id === thread)?.title || "New conversation"}</span>}</div><div className="flex items-center gap-1"><button className="icon-button" aria-label="Open command palette" onClick={() => setPalette(true)}><Search size={15} /></button><button className="icon-button" aria-label="Toggle theme" onClick={toggleTheme}>{dark ? <Sun size={15} /> : <Moon size={15} />}</button></div></header>
      <div className="dime-content">
        {tab === "chat" && thread && <ChatView key={`${thread}-${replay ?? "live"}`} thread={thread} replay={replay} onRunDone={onRunDone} workflowRequest={workflowRequest?.thread === thread ? workflowRequest : null} onWorkflowConsumed={() => { workflowStarting.current = false; setWorkflowRequest(null); }} />}
        {tab === "workflows" && <WorkflowsPanel onRun={runWorkflow} />}
        {tab === "boards" && <BoardsPanel boardId={boardId} onOpen={openBoard} onAsk={askBoard} />}
        {tab === "notebooks" && <NotebooksPanel notebookId={notebookId} onOpen={openNotebook} />}
        {tab === "today" && <HomeView onAsk={() => navigate("workflows")} />}
        {tab === "briefs" && <LibraryView onThread={pick} onBoard={openBoard} />}
        {tab === "data" && <DataView />}
        {tab === "trades" && <div className="tools-view"><TradesView onAsk={askBoard} /></div>}
        {tab === "compare" && <div className="tools-view"><CompareView onAsk={askBoard} /></div>}
        {tab === "draft" && <div className="tools-view"><DraftView onAsk={askBoard} /></div>}
        {tab === "matchups" && <div className="tools-view"><MatchupsView /></div>}
        {tab === "awards" && <div className="tools-view"><AwardsView /></div>}
      </div>
    </main>
    <DimeCommandPalette open={palette} entries={entries} onClose={() => setPalette(false)} />
  </div>;
}
>>>>>>> origin/dev

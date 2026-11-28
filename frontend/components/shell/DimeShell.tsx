"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Award, BookOpen, ClipboardList, Columns3, Command, Database, Home, MessageCircle, Moon, NotebookText, Search, Sun, Swords, Target, Landmark, History, ArrowLeftRight, Workflow, Table2, CalendarRange } from "lucide-react";
import { SidebarNav } from "../ds/SidebarNav";
import DimeCommandPalette, { type PaletteEntry } from "../site/DimeCommandPalette";
import TradesView from "../dime/views/TradesView";
import CompareView from "../dime/views/CompareView";
import DraftView from "../dime/views/DraftView";
import MatchupsView from "../dime/views/MatchupsView";
import ScoutView from "../dime/views/ScoutView";
import CapSheetView from "../dime/views/CapSheetView";
import PlannerView from "../dime/views/PlannerView";
import HistoryView from "../dime/views/HistoryView";
import AwardsView from "../dime/views/AwardsView";
import { ChatView } from "./ChatView";
import { DataView, HomeView, LibraryView } from "./WorkspaceViews";
import { getThreads, type ThreadInfo } from "../../lib/api";
import WorkflowsPanel from "../WorkflowsPanel";
import { BoardsPanel } from "../BoardsPanel";
import { NotebooksPanel } from "../NotebooksPanel";
import { parseShellTab, shellNavigation, shellUrl, validThread, type ShellTab } from "../../lib/shell-navigation";
import { WORKBENCH_EVENT, type CapScenarioSeed, type TradeConstructionSeed, type WorkbenchSeed } from "../../lib/workbench-navigation";
import { replayName } from "../../lib/replay";
import { createWorkflowDraft, saveWorkflowDraft } from "../../lib/workflow-drafts";

export { parseShellTab, shellNavigation } from "../../lib/shell-navigation";
const icons = { today: Home, chat: MessageCircle, workflows: Workflow, boards: Table2, notebooks: NotebookText, briefs: BookOpen, data: Database, trades: ArrowLeftRight, compare: Columns3, draft: ClipboardList, matchups: Swords, scout: Target, cap: Landmark, planner: CalendarRange, history: History, awards: Award };
const navigation = shellNavigation.map(item => { const Icon = icons[item.id]; return { ...item, icon: <Icon size={17} strokeWidth={1.5} /> }; });

export function DimeShell() {
  const [tab, setTab] = useState<ShellTab>("chat");
  const [thread, setThread] = useState("");
  const [boardId, setBoardId] = useState<string | null>(null);
  const [notebookId, setNotebookId] = useState<string | null>(null);
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [replay, setReplay] = useState<string | null>(null);
  const [palette, setPalette] = useState(false);
  const navigateRef = useRef<(nextTab: ShellTab) => void>(() => {});
  const [dark, setDark] = useState(true);
  const [workflowRequest, setWorkflowRequest] = useState<{ thread: string; text: string } | null>(null);
  const [tradeSeed, setTradeSeed] = useState<TradeConstructionSeed | null>(null);
  const [capSeed, setCapSeed] = useState<CapScenarioSeed | null>(null);
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
    const external = (event: Event) => {
      const detail = (event as CustomEvent<{ tab?: string }>).detail;
      if (detail?.tab) navigateRef.current(parseShellTab(detail.tab));
    };
    const workbench = (event: Event) => {
      const detail = (event as CustomEvent<WorkbenchSeed>).detail;
      if (detail?.kind === "trade" && detail.construction?.legs?.length) {
        setTradeSeed(detail.construction);
        navigateRef.current("trades");
      }
      if (detail?.kind === "cap_scenario" && detail.construction?.team) {
        setCapSeed(detail.construction);
        navigateRef.current("cap");
      }
    };
    window.addEventListener("dime:navigate", external);
    window.addEventListener(WORKBENCH_EVENT, workbench);
    return () => { window.removeEventListener("popstate", read); window.removeEventListener("keydown", key); window.removeEventListener("dime:navigate", external); window.removeEventListener(WORKBENCH_EVENT, workbench); };
  }, []);
  const reload = useCallback(() => { void getThreads().then(items => setThreads(items.sort((a, b) => b.updated.localeCompare(a.updated)))); }, []);
  useEffect(() => { reload(); }, [reload]);
  navigateRef.current = (nextTab: ShellTab) => navigate(nextTab);
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
  const askBoard = (text: string, context?: import("../../lib/view-context").ViewContext) => {
    const id = crypto.randomUUID();
    saveWorkflowDraft({ ...createWorkflowDraft(id, text, context), edited: true });
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
    <a href="#dime-main-content" className="skip-to-content">Skip to content</a>
    <SidebarNav workspace="Dime" items={navigation} activeNav={tab} recents={threads.map(item => ({ id: item.id, label: item.title || "Untitled conversation" }))} activeThread={tab === "chat" ? thread : null} onNavigate={id => navigate(parseShellTab(id))} onNewChat={newChat} onPick={pick} footer={<div className="sidebar-copy mt-4 px-2 pb-2 text-[10px] leading-relaxed text-ink-3"><p>NBA intelligence · Dime</p><button className="mt-3 flex items-center gap-2 hover:text-ink" onClick={() => setPalette(true)}><Command size={12} />Command menu <kbd className="ml-auto">⌘ K</kbd></button></div>} />
    <main className="dime-main" id="dime-main-content" tabIndex={-1}>
      <header className="dime-header"><div className="dime-top-tab"><span>{label}</span>{tab === "chat" && <span className="max-w-48 truncate text-ink-3">{threads.find(item => item.id === thread)?.title || "New conversation"}</span>}</div><div className="flex items-center gap-1"><button className="icon-button" aria-label="Open command palette" onClick={() => setPalette(true)}><Search size={15} /></button><button className="icon-button" aria-label="Toggle theme" onClick={toggleTheme}>{dark ? <Sun size={15} /> : <Moon size={15} />}</button></div></header>
      <div className="dime-content">
        {tab === "chat" && thread && <ChatView key={`${thread}-${replay ?? "live"}`} thread={thread} replay={replay} onRunDone={onRunDone} workflowRequest={workflowRequest?.thread === thread ? workflowRequest : null} onWorkflowConsumed={() => { workflowStarting.current = false; setWorkflowRequest(null); }} />}
        {tab === "workflows" && <WorkflowsPanel onRun={runWorkflow} />}
        {tab === "boards" && <BoardsPanel boardId={boardId} onOpen={openBoard} onAsk={askBoard} />}
        {tab === "notebooks" && <NotebooksPanel notebookId={notebookId} onOpen={openNotebook} />}
        {tab === "today" && <HomeView onAsk={() => navigate("workflows")} onMorningAsk={askBoard} />}
        {tab === "briefs" && <LibraryView onThread={pick} onBoard={openBoard} />}
        {tab === "data" && <DataView />}
        {tab === "trades" && <div className="tools-view"><TradesView onAsk={askBoard} seed={tradeSeed} /></div>}
        {tab === "compare" && <div className="tools-view"><CompareView onAsk={askBoard} /></div>}
        {tab === "draft" && <div className="tools-view"><DraftView onAsk={askBoard} /></div>}
        {tab === "matchups" && <div className="tools-view"><MatchupsView onAsk={askBoard} /></div>}
        {tab === "scout" && <div className="tools-view"><ScoutView onAsk={askBoard} /></div>}
        {tab === "cap" && <div className="tools-view"><CapSheetView onAsk={askBoard}  seed={capSeed} /></div>}
        {tab === "planner" && <div className="tools-view"><PlannerView /></div>}
        {tab === "history" && <div className="tools-view"><HistoryView onAsk={askBoard} /></div>}
        {tab === "awards" && <div className="tools-view"><AwardsView onAsk={askBoard} /></div>}
      </div>
    </main>
    <DimeCommandPalette open={palette} entries={entries} onClose={() => setPalette(false)} />
  </div>;
}

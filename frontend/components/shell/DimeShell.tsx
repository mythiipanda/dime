"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Award, BookOpen, Command, Database, Home, MessageCircle, Moon, Search, Sun, Swords, ArrowLeftRight, Workflow } from "lucide-react";
import { SidebarNav } from "../ds/SidebarNav";
import DimeCommandPalette, { type PaletteEntry } from "../site/DimeCommandPalette";
import TradesView from "../dime/views/TradesView";
import MatchupsView from "../dime/views/MatchupsView";
import AwardsView from "../dime/views/AwardsView";
import { ChatView } from "./ChatView";
import { DataView, HomeView, LibraryView } from "./WorkspaceViews";
import { getThreads, type ThreadInfo } from "../../lib/api";
import WorkflowsPanel from "../WorkflowsPanel";
import { parseShellTab, shellNavigation, shellUrl, validThread, type ShellTab } from "../../lib/shell-navigation";
import { replayName } from "../../lib/replay";
import { saveWorkflowDraft } from "../../lib/workflow-drafts";

export { parseShellTab, shellNavigation } from "../../lib/shell-navigation";
const icons = { today: Home, chat: MessageCircle, workflows: Workflow, briefs: BookOpen, data: Database, trades: ArrowLeftRight, matchups: Swords, awards: Award };
const navigation = shellNavigation.map(item => { const Icon = icons[item.id]; return { ...item, icon: <Icon size={17} strokeWidth={1.5} /> }; });

export function DimeShell() {
  const [tab, setTab] = useState<ShellTab>("chat");
  const [thread, setThread] = useState("");
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
    window.history.pushState({}, "", shellUrl(window.location.href, nextTab, nextThread));
  };
  const newChat = () => navigate("chat", crypto.randomUUID());
  const runWorkflow = (text: string) => {
    if (workflowStarting.current) return;
    workflowStarting.current = true;
    const nextThread = crypto.randomUUID();
    saveWorkflowDraft(nextThread, text);
    setWorkflowRequest({ thread: nextThread, text });
    navigate("chat", nextThread);
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
        {tab === "today" && <HomeView onAsk={() => navigate("workflows")} />}
        {tab === "briefs" && <LibraryView onThread={pick} />}
        {tab === "data" && <DataView />}
        {tab === "trades" && <div className="tools-view"><TradesView /></div>}
        {tab === "matchups" && <div className="tools-view"><MatchupsView /></div>}
        {tab === "awards" && <div className="tools-view"><AwardsView /></div>}
      </div>
    </main>
    <DimeCommandPalette open={palette} entries={entries} onClose={() => setPalette(false)} />
  </div>;
}

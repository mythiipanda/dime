"use client";

import { useCallback, useEffect, useState } from "react";
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

export type ShellTab = "today" | "chat" | "boards" | "workflows" | "briefs" | "data";
export const shellNavigation = [
  { id: "today", label: "Home", icon: <HomeSimple width={17} height={17} /> },
  { id: "chat", label: "Ask", icon: <ChatBubble width={17} height={17} /> },
  { id: "boards", label: "Boards", icon: <ViewGrid width={17} height={17} /> },
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
  const syncUrl = (nextTab: ShellTab, nextThread: string, push = true) => {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", nextTab); url.searchParams.set("thread", nextThread);
    url.searchParams.delete("replay");
    url.searchParams.delete("board");
    window.history[push ? "pushState" : "replaceState"]({}, "", url);
  };
  useEffect(() => {
    const read = () => {
      const params = new URLSearchParams(window.location.search);
      setTab(parseShellTab(params.get("tab")));
      setBoardId(params.get("board"));
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
  const navigate = (value: string) => { const next = parseShellTab(value); setTab(next); if (next === "boards") setBoardId(null); setReplay(null); syncUrl(next, thread); };
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
  const title = tab === "chat" ? threads.find((t) => t.id === thread)?.title || "New chat" : shellNavigation.find((n) => n.id === tab)!.label;
  return <div className="dime-shell">
    <SidebarNav workspace="Dime" items={shellNavigation} activeNav={tab} activeThread={thread} recents={threads.map((t) => ({ id: t.id, label: t.title }))} onNavigate={navigate} onNewChat={() => startChat()} onPick={(id) => { setThread(id); setTab("chat"); setReplay(null); setPreset(null); syncUrl("chat", id); }} footer={<div className="flex items-center justify-between"><span className="text-[11px] text-ink-3">Basketball intelligence</span><Chip>2025–26</Chip></div>} />
    <main className="dime-main">
      <header className="dime-header">
        <div className="dime-top-tab"><span className="max-w-60 truncate">{title}</span><button aria-label="New chat" className="text-ink-3 hover:text-ink" onClick={() => startChat()}><Xmark width={12} height={12} /></button></div>
        <div className="flex items-center gap-1"><button className="icon-button" aria-label="Search commands" onClick={() => setPaletteKey((k) => k + 1)}><Search width={15} height={15} /></button><button className="icon-button" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => { const next = !dark; setDark(next); document.documentElement.classList.toggle("dark", next); try { localStorage.setItem("dime_theme", next ? "dark" : "light"); } catch {} }}>{dark ? <SunLight width={16} height={16} /> : <HalfMoon width={16} height={16} />}</button></div>
      </header>
      <div className="dime-content">
        {tab === "chat" && thread && <ChatView key={`${thread}-${replay || "live"}`} thread={thread} preset={preset} autoSend={autoSend?.thread === thread ? autoSend : null} replay={replay} onConsumed={() => setAutoSend(null)} onRunDone={reload} />}
        {tab === "workflows" && <WorkflowsPanel onRun={startChat} />}
        {tab === "data" && <ExploreWorkspace exploreKey={exploreKey} onAsk={(q) => { setPreset(q); navigate("chat"); }} />}
        {tab === "today" && <HomeView onWorkflows={() => navigate("workflows")} />}
        {tab === "briefs" && <BriefsLibrary onOpenBoard={openBoard} />}
        {tab === "boards" && <BoardsPanel boardId={boardId} onOpen={openBoard} onAsk={(q) => { startChat(); setPreset(q); }} />}
      </div>
    </main>
    <CommandPalette openKey={paletteKey} onAsk={(q) => { setPreset(q); navigate("chat"); }} onTab={navigate} onDebate={() => setDebate(true)} />
    {debate && <DebateCardModal onClose={() => setDebate(false)} />}
  </div>;
}

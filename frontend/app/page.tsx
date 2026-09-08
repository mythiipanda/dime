"use client";

import { useCallback, useEffect, useState } from "react";import ChatPanel from "../components/ChatPanel";
import CommandPalette from "../components/CommandPalette";
import DatasetPanel from "../components/DatasetPanel";
import DraftPanel from "../components/DraftPanel";
import LineupPanel from "../components/LineupPanel";
import PlayoffPanel from "../components/PlayoffPanel";
import FreshnessPanel from "../components/FreshnessPanel";
import TradePanel from "../components/TradePanel";
import ScoreStrip from "../components/ScoreStrip";
import RunsPanel from "../components/RunsPanel";
import ThreadRail from "../components/ThreadRail";
import { ThreadInfo, getQueryParam, getThreads, setQueryParam } from "../lib/api";

function newThreadId() {
  return "t-" + Math.random().toString(36).slice(2, 8);
}

export default function Home() {
  const [tab, setTab] = useState<"chat" | "data">("chat");
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [preset, setPreset] = useState<string | null>(null);
  const [exploreKey, setExploreKey] = useState(0);
  const [paletteKey, setPaletteKey] = useState(0);

  useEffect(() => {
    const v = getQueryParam("tab");
    if (v === "chat" || v === "data") setTab(v);
    const t = getQueryParam("thread");
    if (t && /^[A-Za-z0-9-]{1,64}$/.test(t)) {
      setActive(t);
    } else {
      const id = newThreadId();
      setActive(id);
      setQueryParam("thread", id);
    }
  }, []);

  const selectTab = (t: "chat" | "data") => {
    setTab(t);
    setQueryParam("tab", t, true);
  };

  const selectThread = (id: string) => {
    setActive(id);
    setQueryParam("thread", id, true);
  };

  const newThread = () => {
    const id = newThreadId();
    setActive(id);
    setQueryParam("thread", id, true);
  };

  useEffect(() => {
    const onPop = () => {
      const v = getQueryParam("tab");
      if (v === "chat" || v === "data") setTab(v);
      const t = getQueryParam("thread");
      if (t && /^[A-Za-z0-9-]{1,64}$/.test(t)) setActive(t);
      setExploreKey((k) => k + 1);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const reload = useCallback(() => {
    getThreads().then(setThreads).catch(() => {});
    setRefreshKey((k) => k + 1);
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <main style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 16px 96px" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 32,
        }}
      >
        <div style={{ fontWeight: 500, fontSize: 14, color: "var(--color-ink-black)" }}>Dime</div>
        <nav style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={() => setPaletteKey((k) => k + 1)}
            className="pill-ghost"
            style={{ fontSize: 13 }}
          >
            Search
          </button>
          <button
            onClick={() => selectTab("chat")}
            className={tab === "chat" ? "tab-active" : "tab-idle"}
            style={{ fontSize: 14 }}
          >
            Analyst chat
          </button>
          <button
            onClick={() => selectTab("data")}
            className={tab === "data" ? "tab-active" : "tab-idle"}
            style={{ fontSize: 14 }}
          >
            Explore
          </button>
        </nav>
      </header>

      <ScoreStrip />

      <CommandPalette
        onAsk={(q) => setPreset(q)}
        onTab={selectTab}
      />
      {tab === "data" && (
        <nav aria-label="Explore sections" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
          {[
            ["leaders", "Leaders"],
            ["shots", "Shots"],
            ["trade", "Trade"],
            ["lineups", "Lineups"],
            ["playoffs", "Playoffs"],
          ].map(([id, label]) => (
            <a key={id} href={`#explore-${id}`} className="pill-ghost" style={{ fontSize: 12, textDecoration: "none" }}>
              {label}
            </a>
          ))}
        </nav>
      )}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        <aside style={{ width: 220, flexShrink: 0 }}>
          <ThreadRail
            threads={threads}
            active={active}
            onSelect={selectThread}
            onNew={newThread}
          />
        </aside>
        <div style={{ flex: 1, minWidth: 0 }}>
          {tab === "chat" ? (
            <div>
              {active ? (
                <div>
                  <ChatPanel thread={active} onRunDone={reload} preset={preset} />
                  <RunsPanel thread={active} refreshKey={refreshKey} />
                </div>
              ) : (
                <div className="card">Starting session...</div>
              )}
            </div>
          ) : (
            <div>
              <DatasetPanel key={exploreKey} />
              <div id="explore-trade" style={{ marginTop: 16, scrollMarginTop: 16 }}>
                <TradePanel />
              </div>
              <div style={{ marginTop: 16 }}>
                <DraftPanel />
              </div>
              <div id="explore-lineups" style={{ marginTop: 16, scrollMarginTop: 16 }}>
                <LineupPanel />
              </div>
              <div id="explore-playoffs" style={{ marginTop: 16, scrollMarginTop: 16 }}>
                <PlayoffPanel />
              </div>
              <FreshnessPanel />
            </div>
          )}
        </div>
      </div>

      <footer style={{ marginTop: 96, fontSize: 12, color: "var(--color-ash-gray)" }}>
        Anonymous workspace. Tables carry their source and fetch date.
      </footer>
    </main>
  );
}

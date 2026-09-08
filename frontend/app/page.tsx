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
    <div style={{ display: "flex", height: "100vh", width: "100vw", overflow: "hidden", background: "var(--color-stone-canvas)" }}>
      {/* ChatGPT-style Left Sidebar */}
      <aside style={{ width: 260, flexShrink: 0, height: "100vh" }}>
        <ThreadRail
          threads={threads}
          active={active}
          onSelect={selectThread}
          onNew={newThread}
          onSearch={() => setPaletteKey((k) => k + 1)}
        />
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, minWidth: 0, height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Top Header */}
        <header
          style={{
            height: 52,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 20px",
            borderBottom: "1px solid var(--color-stone-border)",
            background: "var(--color-pure-white)",
            flexShrink: 0,
            zIndex: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--color-ink-black)" }}>
              Dime Analyst
            </span>
          </div>

          {/* Centered Capsule Switcher (ChatGPT [Chat] [Work] style) */}
          <div
            style={{
              display: "inline-flex",
              background: "var(--color-stone-canvas)",
              padding: "3px",
              borderRadius: 9999,
              border: "1px solid var(--color-stone-border)",
            }}
          >
            <button
              onClick={() => selectTab("chat")}
              className={tab === "chat" ? "tab-active" : "pill-ghost"}
              style={{
                fontSize: 13,
                border: "none",
                padding: "4px 14px",
                cursor: "pointer",
              }}
            >
              Analyst chat
            </button>
            <button
              onClick={() => selectTab("data")}
              className={tab === "data" ? "tab-active" : "pill-ghost"}
              style={{
                fontSize: 13,
                border: "none",
                padding: "4px 14px",
                cursor: "pointer",
              }}
            >
              Explore
            </button>
          </div>

          {/* Right Status */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                fontSize: 12,
                color: "var(--color-warm-gray)",
                background: "var(--color-stone-canvas)",
                border: "1px solid var(--color-stone-border)",
                padding: "3px 10px",
                borderRadius: 9999,
              }}
            >
              2025-26 season
            </span>
          </div>
        </header>

        {/* Scrollable Viewport */}
        <div style={{ flex: 1, minHeight: 0, overflowY: "auto", position: "relative" }}>
          <CommandPalette onAsk={(q) => setPreset(q)} onTab={selectTab} />

          {tab === "chat" ? (
            <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
              {active ? (
                <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                  <ChatPanel thread={active} onRunDone={reload} preset={preset} />
                </div>
              ) : (
                <div className="card" style={{ margin: 24 }}>Starting session...</div>
              )}
            </div>
          ) : (
            <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 20px 80px" }}>
              <div style={{ marginBottom: 16 }}>
                <ScoreStrip />
              </div>

              <nav aria-label="Explore sections" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 20, background: "var(--color-pure-white)", padding: "10px 14px", borderRadius: 12, border: "1px solid var(--color-stone-border)" }}>
                {[
                  ["leaders", "Leaders"],
                  ["shots", "Shots"],
                  ["trade", "Trade"],
                  ["lineups", "Lineups"],
                  ["playoffs", "Playoffs"],
                ].map(([id, label]) => (
                  <a key={id} href={`#explore-${id}`} className="pill-ghost" style={{ fontSize: 12, textDecoration: "none", padding: "5px 12px" }}>
                    {label}
                  </a>
                ))}
              </nav>

              <DatasetPanel key={exploreKey} />
              <div id="explore-trade" style={{ marginTop: 24, scrollMarginTop: 24 }}>
                <TradePanel />
              </div>
              <div style={{ marginTop: 24 }}>
                <DraftPanel />
              </div>
              <div id="explore-lineups" style={{ marginTop: 24, scrollMarginTop: 24 }}>
                <LineupPanel />
              </div>
              <div id="explore-playoffs" style={{ marginTop: 24, scrollMarginTop: 24 }}>
                <PlayoffPanel />
              </div>
              <FreshnessPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

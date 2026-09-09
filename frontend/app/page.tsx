"use client";

import { useCallback, useEffect, useState } from "react";
import ArtifactCanvas, { ArtifactItem } from "../components/ArtifactCanvas";
import ChatPanel from "../components/ChatPanel";
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
  const [activeArtifact, setActiveArtifact] = useState<ArtifactItem | null>(null);
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
      {/* Left Sidebar */}
      <aside style={{ width: 260, flexShrink: 0, height: "100vh" }}>
        <ThreadRail
          threads={threads}
          active={active}
          onSelect={selectThread}
          onNew={newThread}
          onHomeClick={newThread}
          onSearch={() => setPaletteKey((k) => k + 1)}
        />
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, minWidth: 0, height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Top Header (shadcn / Linear style) */}
        <header
          style={{
            height: 44,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 16px",
            borderBottom: "1px solid var(--color-stone-border)",
            background: "var(--color-pure-white)",
            flexShrink: 0,
            zIndex: 10,
          }}
        >
          {/* Left: Active session context & Home link */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, maxWidth: "45%" }}>
            <button
              type="button"
              onClick={newThread}
              className="interactive-tactile"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                background: "transparent",
                border: "none",
                padding: "2px 6px",
                borderRadius: 6,
                cursor: "pointer",
                color: "var(--color-ink-black)",
              }}
              title="Return to home"
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: "var(--color-cyan-signal)",
                  display: "inline-block",
                }}
              />
              <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.015em" }}>Dime</span>
            </button>
            <span style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>/</span>
            <span
              style={{
                fontSize: 12,
                color: "var(--color-warm-gray)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {threads.find((t) => t.id === active)?.title || "Analyst"}
            </span>
          </div>

          {/* Centered Segmented Control (shadcn Tabs style) */}
          <div
            style={{
              display: "inline-flex",
              background: "rgba(0, 0, 0, 0.04)",
              padding: "2px",
              borderRadius: 8,
              border: "1px solid var(--color-stone-border)",
            }}
          >
            <button
              onClick={() => selectTab("chat")}
              className={tab === "chat" ? "tab-active" : "tab-idle"}
              style={{
                fontSize: 12,
                border: "none",
                padding: "3px 12px",
                borderRadius: 6,
                cursor: "pointer",
              }}
            >
              Analyst chat
            </button>
            <button
              onClick={() => selectTab("data")}
              className={tab === "data" ? "tab-active" : "tab-idle"}
              style={{
                fontSize: 12,
                border: "none",
                padding: "3px 12px",
                borderRadius: 6,
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
                fontSize: 11,
                color: "var(--color-warm-gray)",
                background: "var(--color-pure-white)",
                border: "1px solid var(--color-stone-border)",
                padding: "3px 8px",
                borderRadius: 6,
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
              }}
            >
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--color-cyan-signal)" }} />
              2025-26 season
            </span>
          </div>
        </header>

        {/* Viewport Content */}
        <div style={{ flex: 1, minHeight: 0, overflow: "hidden", position: "relative" }}>
          <CommandPalette onAsk={(q) => setPreset(q)} onTab={selectTab} />

          {tab === "chat" ? (
            <div style={{ height: "100%", display: "flex", overflow: "hidden" }}>
              {/* Chat Stream (expands to 100% when no artifact, 52% when artifact active) */}
              <div
                style={{
                  flex: activeArtifact ? "0 0 52%" : "1 1 100%",
                  height: "100%",
                  overflowY: "auto",
                  transition: "flex 240ms cubic-bezier(0.16, 1, 0.3, 1)",
                  boxSizing: "border-box",
                }}
              >
                {active ? (
                  <ChatPanel
                    thread={active}
                    onRunDone={reload}
                    preset={preset}
                    onOpenArtifact={(art) => setActiveArtifact(art)}
                    activeArtifactId={activeArtifact?.id}
                  />
                ) : (
                  <div className="card" style={{ margin: 24 }}>Starting session...</div>
                )}
              </div>

              {/* Right Artifact Canvas Pane (Claude / Manus Style) */}
              {activeArtifact && (
                <div
                  style={{
                    flex: "0 0 48%",
                    height: "100%",
                    overflow: "hidden",
                    borderLeft: "1px solid var(--color-stone-border)",
                    boxSizing: "border-box",
                  }}
                >
                  <ArtifactCanvas
                    artifact={activeArtifact}
                    onClose={() => setActiveArtifact(null)}
                    onAsk={(q) => setPreset(q)}
                  />
                </div>
              )}
            </div>
          ) : (
            <div style={{ height: "100%", overflowY: "auto" }}>
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
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

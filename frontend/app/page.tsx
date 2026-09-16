"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
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
import TodayPanel from "../components/TodayPanel";
import MoversPanel from "../components/MoversPanel";
import WatchlistPanel from "../components/WatchlistPanel";
import OnboardingModal from "../components/OnboardingModal";
import DebateCardModal from "../components/DebateCardModal";
import { ThreadInfo, getQueryParam, getThreads, setQueryParam } from "../lib/api";

type Tab = "chat" | "data" | "today";

function newThreadId() {
  return "t-" + Math.random().toString(36).slice(2, 8);
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("chat");
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [debateOpen, setDebateOpen] = useState(false);
  const [activeArtifact, setActiveArtifact] = useState<ArtifactItem | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [preset, setPreset] = useState<string | null>(null);
  const [exploreKey, setExploreKey] = useState(0);
  const [themeTick, setThemeTick] = useState(0);
  useEffect(() => {
    try {
      const t = localStorage.getItem("dime_theme") || "dark";
      document.documentElement.classList.toggle("dark", t === "dark");
    } catch {}
  }, []);
  const themeDark = typeof window !== "undefined" &&
    (themeTick >= 0) &&
    document.documentElement.classList.contains("dark");
  const [paletteKey, setPaletteKey] = useState(0);
  const [activeSection, setActiveSection] = useState("leaders");
  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    const v = getQueryParam("tab");
    if (v === "chat" || v === "data" || v === "today") setTab(v);
    const t = getQueryParam("thread");
    if (t && /^[A-Za-z0-9-]{1,64}$/.test(t)) {
      setActive(t);
    } else {
      const id = newThreadId();
      setActive(id);
      setQueryParam("thread", id);
    }
  }, []);

  useEffect(() => {
    try {
      if (!localStorage.getItem("dime_onboarded")) setShowOnboarding(true);
    } catch {
      setShowOnboarding(false);
    }
  }, []);

  const finishOnboarding = () => {
    try {
      localStorage.setItem("dime_onboarded", "1");
    } catch {}
    setShowOnboarding(false);
  };

  const startFromOnboarding = (q: string) => {
    setPreset(q);
    setTab("chat");
    setQueryParam("tab", "chat", true);
    finishOnboarding();
  };

  const tabsRef = useRef<HTMLDivElement | null>(null);
  const pillRef = useRef<HTMLSpanElement | null>(null);
  const tabBtnRefs = {
    today: useRef<HTMLButtonElement | null>(null),
    chat: useRef<HTMLButtonElement | null>(null),
    data: useRef<HTMLButtonElement | null>(null),
  };
  useLayoutEffect(() => {
    const btn = tabBtnRefs[tab].current;
    const pill = pillRef.current;
    if (!btn || !pill) return;
    // transitions.dev #16: first paint positions the pill without motion,
    // subsequent tab switches slide it.
    const prev = pill.style.transition;
    if (!pill.dataset.ready) {
      pill.style.transition = "none";
      pill.dataset.ready = "1";
    }
    pill.style.transform = `translateX(${btn.offsetLeft}px)`;
    pill.style.width = `${btn.offsetWidth}px`;
    if (prev !== undefined) requestAnimationFrame(() => { pill.style.transition = prev; });
  }, [tab]);

  const selectTab = (t: Tab) => {
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
      if (v === "chat" || v === "data" || v === "today") setTab(v);
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
      <aside className="sidebar-rail" style={{ width: 224, flexShrink: 0, height: "100vh" }}>
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
          className="top-header"
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
            ref={tabsRef}
            className="t-tabs"
            style={{
              display: "inline-flex",
              position: "relative",
              background: "var(--color-field)",
              padding: "2px",
              borderRadius: 8,
              border: "1px solid var(--color-stone-border)",
            }}
          >
            <span ref={pillRef} className="t-tabs-pill" aria-hidden="true" />
            <button
              ref={tabBtnRefs.today}
              onClick={() => selectTab("today")}
              className={tab === "today" ? "tab-active" : "tab-idle"}
              style={{
                fontSize: 12,
                border: "none",
                padding: "3px 12px",
                borderRadius: 6,
                cursor: "pointer",
                position: "relative",
                zIndex: 1,
                background: "transparent",
              }}
            >
              Today
            </button>
            <button
              ref={tabBtnRefs.chat}
              onClick={() => selectTab("chat")}
              className={tab === "chat" ? "tab-active" : "tab-idle"}
              style={{
                fontSize: 12,
                border: "none",
                padding: "3px 12px",
                borderRadius: 6,
                cursor: "pointer",
                position: "relative",
                zIndex: 1,
                background: "transparent",
              }}
            >
              Analyst chat
            </button>
            <button
              ref={tabBtnRefs.data}
              onClick={() => selectTab("data")}
              className={tab === "data" ? "tab-active" : "tab-idle"}
              style={{
                fontSize: 12,
                border: "none",
                padding: "3px 12px",
                borderRadius: 6,
                cursor: "pointer",
                position: "relative",
                zIndex: 1,
                background: "transparent",
              }}
            >
              Explore
            </button>
          </div>

          {/* Right Status */}
          <div className="season-badge" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              type="button"
              aria-label="Toggle dark mode"
              title="Toggle light/dark"
              onClick={() => {
                const el = document.documentElement;
                const dark = !el.classList.contains("dark");
                el.classList.toggle("dark", dark);
                try { localStorage.setItem("dime_theme", dark ? "dark" : "light"); } catch {}
                setThemeTick((n) => n + 1);
              }}
              className="pill-ghost interactive-tactile"
              style={{ fontSize: 11, padding: "3px 10px", lineHeight: 1.4 }}
            >
              {themeDark ? "\u263E Dark" : "\u2600 Light"}
            </button>
            <span
              style={{
                fontSize: 11,
                color: "var(--color-warm-gray)",
                background: "var(--color-pure-white)",
                border: "1px solid var(--color-stone-border)",
                padding: "3px 8px",
                borderRadius: 6,
              }}
            >
              2025-26 season
            </span>
          </div>
        </header>

        {/* Viewport Content */}
        <div style={{ flex: 1, minHeight: 0, overflow: "hidden", position: "relative" }}>
          <CommandPalette onAsk={(q) => setPreset(q)} onTab={selectTab} onDebate={() => setDebateOpen(true)} />
          {debateOpen && (
            <DebateCardModal onClose={() => setDebateOpen(false)} />
          )}

          {tab === "chat" ? (
            <div className="chat-split" style={{ height: "100%", display: "flex", overflow: "hidden" }}>
              {/* Chat stream */}
              <div
                className="chat-pane"
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

              {/* Full dataset panel */}
              {activeArtifact && (
                <div
                  className="artifact-pane"
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
          ) : tab === "today" ? (
            <div style={{ height: "100%", overflowY: "auto" }}>
              <div
                style={{
                  maxWidth: 1100,
                  margin: "0 auto",
                  padding: "24px 20px 80px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 16,
                }}
              >
                <TodayPanel />
                <MoversPanel />
                <WatchlistPanel />
              </div>
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
                    <button
                      key={id}
                      type="button"
                      className={activeSection === id ? "tab-active" : "pill-ghost"}
                      aria-selected={activeSection === id}
                      style={{ fontSize: 12, padding: "5px 12px", border: "1px solid transparent", borderRadius: 6, cursor: "pointer" }}
                      onClick={() => {
                        setActiveSection(id);
                        document.getElementById(`explore-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </nav>

                <DatasetPanel key={exploreKey} />
                <div id="explore-trade" style={{ marginTop: 24, scrollMarginTop: 24 }}>
                  <TradePanel onAskValue={startFromOnboarding} />
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
      {showOnboarding && (
        <OnboardingModal onFinish={finishOnboarding} onSelectPrompt={startFromOnboarding} />
      )}
    </div>
  );
}

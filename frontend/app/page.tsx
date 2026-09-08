"use client";

import { useCallback, useEffect, useState } from "react";import ChatPanel from "../components/ChatPanel";
import CommandPalette from "../components/CommandPalette";
import DatasetPanel from "../components/DatasetPanel";
import TradePanel from "../components/TradePanel";
import ScoreStrip from "../components/ScoreStrip";
import RunsPanel from "../components/RunsPanel";
import ThreadRail from "../components/ThreadRail";
import { ShotChartCard } from "../components/ShotChart";
import { ThreadInfo, getThreads } from "../lib/api";

function newThreadId() {
  return "t-" + Math.random().toString(36).slice(2, 8);
}

export default function Home() {
  const [tab, setTab] = useState<"chat" | "data">("chat");
  const [threads, setThreads] = useState<ThreadInfo[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [preset, setPreset] = useState<string | null>(null);

  useEffect(() => {
    setActive(newThreadId());
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
        <div style={{ fontWeight: 500, fontSize: 14 }}>Dime</div>
        <nav style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => setTab("chat")}
            className={tab === "chat" ? "tab-active" : "tab-idle"}
            style={{ fontSize: 14 }}
          >
            Analyst chat
          </button>
          <button
            onClick={() => setTab("data")}
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
        onTab={setTab}
      />
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        <aside style={{ width: 220, flexShrink: 0 }}>
          <ThreadRail
            threads={threads}
            active={active}
            onSelect={setActive}
            onNew={() => setActive(newThreadId())}
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
              <DatasetPanel />
              <ShotChartCard />
              <div style={{ marginTop: 16 }}>
                <TradePanel />
              </div>
            </div>
          )}
        </div>
      </div>

      <footer style={{ marginTop: 96, fontSize: 12, color: "#a8a29e" }}>
        Anonymous workspace. Tables carry their source and fetch date.
      </footer>
    </main>
  );
}

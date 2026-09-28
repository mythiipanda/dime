"use client";

import { useEffect, useRef, useState } from "react";
import DatasetPanel from "./DatasetPanel";
import DraftPanel from "./DraftPanel";
import ExploreIndex from "./ExploreIndex";
import LineupPanel from "./LineupPanel";
import PlayoffPanel from "./PlayoffPanel";
import ScoreStrip from "./ScoreStrip";
import TradePanel from "./TradePanel";
import { getFreshness } from "../lib/api";
import { updatedLine } from "../lib/freshness";

interface ExploreWorkspaceProps {
  exploreKey: number;
  onAsk: (question: string) => void;
}

function ArrowUpRight({ size = 12 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="7" y1="17" x2="17" y2="7" />
      <polyline points="7 7 17 7 17 17" />
    </svg>
  );
}

export default function ExploreWorkspace({
  exploreKey,
  onAsk,
}: ExploreWorkspaceProps) {
  const scrollRootRef = useRef<HTMLDivElement | null>(null);
  const [updated, setUpdated] = useState<string | null>(null);

  // Redesign Phase 1: the only residue of the old freshness UI is one
  // footer line ("Updated Oct 24"), rendered only when the endpoint has
  // data. No nav status, no system-status disclosure, no empty states.
  useEffect(() => {
    let live = true;
    getFreshness()
      .then((rows) => {
        if (live) setUpdated(updatedLine(rows ?? []));
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  const jumpTo = (id: string) => {
    document.getElementById(`explore-${id}`)?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };

  return (
    <div ref={scrollRootRef} className="explore-scroll">
      <main className="explore-shell">
        <section className="explore-overview" aria-labelledby="explore-title">
          <div className="explore-overview-head">
            <h1 id="explore-title">Explore</h1>
            <button className="explore-ask" onClick={() => onAsk("What is the most important NBA trend in the data right now?")}>Ask Dime <ArrowUpRight /></button>
          </div>

          <ExploreIndex onJump={jumpTo} />
        </section>

        <ScoreStrip />

        <div className="explore-content">
          <DatasetPanel key={exploreKey} />
          <TradePanel onAskValue={onAsk} />
          <DraftPanel />
          <LineupPanel />
          <PlayoffPanel />
        </div>

        {updated && <footer className="explore-footer">{updated}</footer>}
      </main>
    </div>
  );
}

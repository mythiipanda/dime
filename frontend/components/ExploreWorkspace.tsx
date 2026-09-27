"use client";

import { useEffect, useRef, type CSSProperties } from "react";
import DatasetPanel from "./DatasetPanel";
import DraftPanel from "./DraftPanel";
import LineupPanel from "./LineupPanel";
import PlayoffPanel from "./PlayoffPanel";
import ScoreStrip from "./ScoreStrip";
import SystemStatus from "./SystemStatus";
import TradePanel from "./TradePanel";

interface ExploreWorkspaceProps {
  activeSection: string;
  exploreKey: number;
  onActiveSection: (section: string) => void;
  onAsk: (question: string) => void;
}

const sections = [
  { id: "leaders", label: "Leaders" },
  { id: "shots", label: "Shots" },
  { id: "trade", label: "Trade" },
  { id: "draft", label: "Draft" },
  { id: "lineups", label: "Lineups" },
  { id: "playoffs", label: "Playoffs" },
];

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

const quickQuestions = [
  ["Player", "Compare Luka Dončić and Shai Gilgeous-Alexander this season"],
  ["Trade", "Evaluate a realistic high-impact NBA trade through value, fit, contracts, risk, and replaceability."],
  ["Lineup", "Which NBA lineups are outperforming expectations, and what explains it?"],
] as const;

export default function ExploreWorkspace({
  activeSection,
  exploreKey,
  onActiveSection,
  onAsk,
}: ExploreWorkspaceProps) {
  const scrollRootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const root = scrollRootRef.current;
    if (!root || !("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        const id = visible?.target.id.replace("explore-", "");
        if (id) onActiveSection(id);
      },
      { root, rootMargin: "-18% 0px -62%", threshold: [0.05, 0.25, 0.6] },
    );
    sections.forEach(({ id }) => {
      const target = document.getElementById(`explore-${id}`);
      if (target) observer.observe(target);
    });
    return () => observer.disconnect();
  }, [exploreKey, onActiveSection]);

  const jumpTo = (id: string) => {
    onActiveSection(id);
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

          <div className="explore-index" aria-label="Available analysis">
            {sections.map(({ id, label }, index) => (
              <button key={id} onClick={() => jumpTo(id)}>
                <span className="explore-index-number">0{index + 1}</span>
                <strong>{label}</strong>
              </button>
            ))}
          </div>

          <div className="explore-quick-ask">
            <span className="explore-quick-label">Start with a question</span>
            <div>
              {quickQuestions.map(([label, question]) => (
                <button key={label} onClick={() => onAsk(question)}><span>{label}</span>{question}<span className="explore-quick-go"><ArrowUpRight /></span></button>
              ))}
            </div>
          </div>
        </section>

        <ScoreStrip />

        <nav className="explore-nav" aria-label="Explore sections">
          <div className="explore-nav-track" style={{ "--active-index": sections.findIndex(({ id }) => id === activeSection) } as CSSProperties}>
            <span className="explore-nav-indicator" aria-hidden="true" />
            {sections.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                className={activeSection === id ? "is-active" : ""}
                aria-current={activeSection === id ? "page" : undefined}
                onClick={() => jumpTo(id)}
              >
                {label}
              </button>
            ))}
            <span className="explore-nav-status"><span className="status-mark" /> 2025-26</span>
          </div>
        </nav>

        <div className="explore-content">
          <DatasetPanel key={exploreKey} />
          <section id="explore-trade" className="explore-section-anchor">
            <TradePanel onAskValue={onAsk} />
          </section>
          <section id="explore-draft" className="explore-section-anchor">
            <DraftPanel />
          </section>
          <section id="explore-lineups" className="explore-section-anchor">
            <LineupPanel />
          </section>
          <section id="explore-playoffs" className="explore-section-anchor">
            <PlayoffPanel />
          </section>
          <SystemStatus />
        </div>
      </main>
    </div>
  );
}

"use client";

import { useEffect, useRef, type CSSProperties } from "react";
import DatasetPanel from "./DatasetPanel";
import DraftPanel from "./DraftPanel";
import FreshnessPanel from "./FreshnessPanel";
import LineupPanel from "./LineupPanel";
import PlayoffPanel from "./PlayoffPanel";
import ScoreStrip from "./ScoreStrip";
import TradePanel from "./TradePanel";

interface ExploreWorkspaceProps {
  activeSection: string;
  exploreKey: number;
  onActiveSection: (section: string) => void;
  onAsk: (question: string) => void;
}

const sections = [
  { id: "leaders", label: "Leaders", glyph: "↗" },
  { id: "shots", label: "Shots", glyph: "◎" },
  { id: "trade", label: "Trade", glyph: "⇄" },
  { id: "lineups", label: "Lineups", glyph: "⌁" },
  { id: "playoffs", label: "Playoffs", glyph: "◇" },
];

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
            <div>
              <div className="explore-kicker"><span className="status-mark" /> 2025-26 data workspace</div>
              <h1 id="explore-title">Explore</h1>
            </div>
            <button className="explore-ask" onClick={() => onAsk("What is the most important NBA trend in the data right now?")}>Ask Dime <span>↗</span></button>
          </div>

          <div className="explore-index" aria-label="Available analysis">
            {sections.map(({ id, label, glyph }, index) => (
              <button key={id} onClick={() => jumpTo(id)}>
                <span className="explore-index-number">0{index + 1}</span>
                <span className="explore-index-glyph">{glyph}</span>
                <strong>{label}</strong>
                <span className="explore-index-arrow">↘</span>
              </button>
            ))}
          </div>

          <div className="explore-quick-ask">
            <span className="explore-quick-label">Start with a question</span>
            <div>
              {quickQuestions.map(([label, question]) => (
                <button key={label} onClick={() => onAsk(question)}><span>{label}</span>{question}<b>↗</b></button>
              ))}
            </div>
          </div>
        </section>

        <ScoreStrip />

        <nav className="explore-nav" aria-label="Explore sections">
          <div className="explore-nav-track" style={{ "--active-index": sections.findIndex(({ id }) => id === activeSection) } as CSSProperties}>
            <span className="explore-nav-indicator" aria-hidden="true" />
            {sections.map(({ id, label, glyph }) => (
              <button
                key={id}
                type="button"
                className={activeSection === id ? "is-active" : ""}
                aria-current={activeSection === id ? "page" : undefined}
                onClick={() => jumpTo(id)}
              >
                <span>{glyph}</span>{label}
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
          <section className="explore-section-anchor">
            <DraftPanel />
          </section>
          <section id="explore-lineups" className="explore-section-anchor">
            <LineupPanel />
          </section>
          <section id="explore-playoffs" className="explore-section-anchor">
            <PlayoffPanel />
          </section>
          <FreshnessPanel />
        </div>
      </main>
    </div>
  );
}

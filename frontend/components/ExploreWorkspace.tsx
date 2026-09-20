"use client";

import { useEffect, useRef } from "react";
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

const prompts = [
  {
    eyebrow: "Player lens",
    title: "Find the signal behind a hot streak",
    body: "Separate a real role change from a short shooting run.",
    question: "Which NBA players have the strongest evidence of a sustainable breakout right now?",
    glyph: "↗",
  },
  {
    eyebrow: "Roster lens",
    title: "Pressure-test a trade before the headline",
    body: "Compare value, fit, contract, risk, and replaceability.",
    question: "Evaluate a realistic high-impact NBA trade through value, fit, contracts, risk, and replaceability.",
    glyph: "⇄",
  },
  {
    eyebrow: "Team lens",
    title: "Read the five-man story",
    body: "Move from lineup numbers to the basketball reason they work.",
    question: "Which NBA lineups are outperforming expectations, and what explains it?",
    glyph: "⌁",
  },
];

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
        <section className="explore-hero" aria-labelledby="explore-title">
          <div className="explore-hero-copy">
            <div className="explore-kicker"><span className="status-mark" /> Live basketball intelligence</div>
            <h1 id="explore-title">See the game from every angle.</h1>
            <p>
              Move from league-wide signal to the exact player, lineup, shot profile,
              or roster decision behind it.
            </p>
            <div className="explore-hero-actions">
              <button className="explore-primary" onClick={() => jumpTo("leaders")}>Explore the data <span>↓</span></button>
              <button className="explore-secondary" onClick={() => onAsk("What is the most important NBA trend in the data right now?")}>Ask Dime <span>↗</span></button>
            </div>
          </div>
          <div className="explore-orbit" aria-hidden="true">
            <div className="orbit-ring orbit-ring-one" />
            <div className="orbit-ring orbit-ring-two" />
            <div className="orbit-core">D</div>
            <div className="orbit-chip orbit-chip-top"><span>LIVE</span> League pulse</div>
            <div className="orbit-chip orbit-chip-bottom">Evidence, not noise</div>
          </div>
        </section>

        <section className="explore-prompts" aria-label="Start an analysis">
          {prompts.map((prompt, index) => (
            <button
              key={prompt.eyebrow}
              className="explore-prompt-card"
              style={{ "--card-delay": `${index * 60}ms` } as React.CSSProperties}
              onClick={() => onAsk(prompt.question)}
            >
              <span className="prompt-glyph">{prompt.glyph}</span>
              <span className="prompt-copy">
                <span className="prompt-eyebrow">{prompt.eyebrow}</span>
                <strong>{prompt.title}</strong>
                <span>{prompt.body}</span>
              </span>
              <span className="prompt-arrow">↗</span>
            </button>
          ))}
        </section>

        <ScoreStrip />

        <nav className="explore-nav" aria-label="Explore sections">
          <div className="explore-nav-track">
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

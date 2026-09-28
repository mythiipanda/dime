"use client";

import { useEffect, useState } from "react";
import { getDatasetJson, SEASON } from "../lib/api";
import { fetchIndexSummaries } from "../lib/exploreIndex";

// Explore redesign Phase 1: the overview index is the only navigation.
// A card renders only when its live summary arrived — no blurb fallbacks,
// nothing invented, nothing hardcoded about a player or team.
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

interface CardDef {
  id: string;
  label: string;
}

const CARDS: CardDef[] = [
  { id: "leaders", label: "Leaders" },
  { id: "shots", label: "Shots" },
  { id: "trade", label: "Trade" },
  { id: "draft", label: "Draft" },
  { id: "lineups", label: "Lineups" },
  { id: "playoffs", label: "Playoffs" },
];

export default function ExploreIndex({
  onJump,
}: {
  onJump: (id: string) => void;
}) {
  // Live summary lines keyed by card id. Each dataset fetch is isolated
  // (Promise.allSettled inside fetchIndexSummaries), so one failed request
  // never blanks the cards whose data arrived fine. Cards with no live
  // data don't render.
  const [summaries, setSummaries] = useState<Record<string, string[]>>({});

  useEffect(() => {
    let alive = true;
    (async () => {
      const next = await fetchIndexSummaries(
        (name, params) => getDatasetJson(name, params),
        SEASON,
      );
      if (alive) setSummaries(next);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const visible = CARDS.filter((card) => (summaries[card.id] ?? []).length > 0);

  return (
    <div className="explore-index" aria-label="Available analysis">
      {visible.map((card, index) => (
        <button
          key={card.id}
          type="button"
          className="explore-index-card"
          onClick={() => onJump(card.id)}
        >
          <span className="explore-index-top">
            <span className="explore-index-number">0{index + 1}</span>
            <span className="explore-index-go">
              <ArrowUpRight />
            </span>
          </span>
          <strong>{card.label}</strong>
          <span className="explore-index-lines">
            {summaries[card.id].map((line, i) => (
              <span className="explore-index-line" key={i} title={line}>
                {line}
              </span>
            ))}
          </span>
        </button>
      ))}
    </div>
  );
}

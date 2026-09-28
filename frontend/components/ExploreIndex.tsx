"use client";

import { useEffect, useState } from "react";
import { getDatasetJson, SEASON } from "../lib/api";
import {
  combineSummary,
  countPlayoffGames,
  playoffChampion,
  topLeaders,
} from "../lib/exploreIndex";

// Explore redesign Phase B: the overview index becomes the workspace.
// Each card carries a compact live summary from existing dataset endpoints
// (no new endpoints) and anchors to its panel on click. Sections with no
// generic live endpoint get a plain one-line description of the tool —
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
  blurb?: string;
}

const CARDS: CardDef[] = [
  { id: "leaders", label: "Leaders" },
  { id: "shots", label: "Shots", blurb: "Zone shot charts for any player" },
  { id: "trade", label: "Trade", blurb: "Simplified 2023 CBA salary matching" },
  { id: "draft", label: "Draft" },
  { id: "lineups", label: "Lineups", blurb: "Five-man units and on/off splits" },
  { id: "playoffs", label: "Playoffs" },
];

export default function ExploreIndex({
  onJump,
}: {
  onJump: (id: string) => void;
}) {
  // Live summary lines keyed by card id; a live card whose fetch failed
  // simply renders its label (same degrade pattern as the Today wrap).
  const [summaries, setSummaries] = useState<Record<string, string[]>>({});

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [ld, po, cb] = await Promise.all([
          getDatasetJson("leaders", { season: SEASON, stat: "PTS" }),
          getDatasetJson("playoffs", { season: SEASON }),
          getDatasetJson("combine", { season: "2025" }),
        ]);
        if (!alive) return;
        const next: Record<string, string[]> = {};
        if (ld.ok) {
          const lines = topLeaders(
            (ld.data || []) as Record<string, unknown>[],
            "PTS",
          ).map((l) => `${l.rank}. ${l.name} — ${l.value}`);
          if (lines.length) next.leaders = lines;
        }
        if (po.ok) {
          const prows = (po.data || []) as Record<string, unknown>[];
          const champ = playoffChampion(prows);
          if (champ) {
            next.playoffs = [
              `${champ.champion} · ${champ.series} over ${champ.runnerUp}`,
            ];
          } else {
            const n = countPlayoffGames(prows);
            if (n > 0) next.playoffs = [`${n} playoff games in the warehouse`];
          }
        }
        if (cb.ok) {
          const s = combineSummary(
            (cb.data || []) as Record<string, unknown>[],
            "2025",
          );
          if (s) next.draft = [s];
        }
        setSummaries(next);
      } catch {
        /* summaries stay empty; cards degrade to labels + blurbs */
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div className="explore-index" aria-label="Available analysis">
      {CARDS.map((card, index) => (
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
          {summaries[card.id] ? (
            <span className="explore-index-lines">
              {summaries[card.id].map((line, i) => (
                <span className="explore-index-line" key={i} title={line}>
                  {line}
                </span>
              ))}
            </span>
          ) : card.blurb ? (
            <span className="explore-index-blurb">{card.blurb}</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}

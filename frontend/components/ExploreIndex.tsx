"use client";

import { useEffect, useState } from "react";
import { getDatasetJson, resolveFirstPlayerId, SEASON } from "../lib/api";
import { BACKEND } from "../lib/chat";
import { apiPath } from "../lib/api";
import { fetchIndexSummaries } from "../lib/exploreIndex";
import type { ExplorePanelId } from "../lib/exploreSearch";
import { TEAM_IDS } from "../lib/teams";









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
  id: ExplorePanelId;
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

const DEFAULT_TEAM = "BOS";
const DEFAULT_TRADE_A = "LAL";
const DEFAULT_TRADE_B = "DEN";

export default function ExploreIndex({
  onSelect,
  active,
}: {
  onSelect: (id: ExplorePanelId) => void;
  active?: ExplorePanelId | null;
}) {
  
  
  
  




  const [summaries, setSummaries] = useState<Record<string, string[]>>({});

  useEffect(() => {
    let alive = true;
    (async () => {
      
      


      const next = await fetchIndexSummaries(
        (name, params) => getDatasetJson(name, params),
        SEASON,
        {
          topScorerShots: async () => {
            const ld = await getDatasetJson("leaders", { season: SEASON, stat: "PTS" });
            const rows = (ld.ok ? (ld.data || []) : []) as Record<string, unknown>[];
            const first = rows[0];
            const name = String(first?.PLAYER ?? first?.PLAYER_NAME ?? "").trim();
            if (!name) return null;
            const id = await resolveFirstPlayerId(name);
            if (!id) return null;
            const sh = await getDatasetJson("shots", { season: SEASON, player_id: String(id) });
            if (!sh.ok) return null;
            return { name, count: ((sh.data || []) as unknown[]).length };
          },
          tradeCheck: async () => {
            const res = await fetch(`${BACKEND}${apiPath("/trade/check")}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                team_a: DEFAULT_TRADE_A,
                players_a: "",
                team_b: DEFAULT_TRADE_B,
                players_b: "",
              }),
            });
            const data = (await res.json()) as { ok?: boolean; rows?: unknown };
            return data.ok ? (data.rows as { team_a?: { team?: string; payroll?: number }; team_b?: { team?: string; payroll?: number } }) : null;
          },
          defaultLineups: async () => {
            const id = TEAM_IDS[DEFAULT_TEAM];
            const res = await getDatasetJson("lineups", { team_id: String(id) });
            if (!res.ok) return null;
            return { team: DEFAULT_TEAM, rows: (res.data || []) as { GROUP_NAME?: unknown; MIN?: unknown }[] };
          },
        },
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
          className={`explore-index-card${active === card.id ? " is-open" : ""}`}
          onClick={() => onSelect(card.id)}
          aria-expanded={active === card.id}
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

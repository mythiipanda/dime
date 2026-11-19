"use client";

import { useEffect, useState } from "react";
import { getDatasetJson, resolveFirstPlayerId, SEASON } from "../lib/api";
import { BACKEND } from "../lib/chat";
import { apiPath } from "../lib/api";
import { fetchIndexSummaries } from "../lib/exploreIndex";
import type { ExplorePanelId } from "../lib/exploreSearch";
import { TEAM_IDS } from "../lib/teams";
import { Button } from "./ds/Button";
import { Chip } from "./ds/Chip";
import { Database } from "iconoir-react";









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
    <div className="my-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Available analysis">
      {visible.map((card, index) => (
        <Button
          key={card.id}
          type="button"
          variant="quiet"
          className={`min-h-44 flex-col items-stretch justify-start rounded-xl border p-5 text-left font-normal transition-colors hover:bg-hover ${active === card.id ? "border-ink-3 bg-hover-2" : "border-line bg-surface"}`}
          onClick={() => onSelect(card.id)}
          aria-expanded={active === card.id}
        >
          <span className="mb-4 flex items-center justify-between">
            <Chip><Database width={13} height={13} className="inline" /> 0{index + 1}</Chip>
            <span className="text-ink-3">
              <ArrowUpRight />
            </span>
          </span>
          <strong className="mb-2 text-[13px] font-medium">{card.label}</strong>
          <span className="flex flex-col gap-1 text-[11px] leading-relaxed text-ink-3">
            {summaries[card.id].map((line, i) => (
              <span className="truncate" key={i} title={line}>
                {line}
              </span>
            ))}
          </span>
        </Button>
      ))}
    </div>
  );
}

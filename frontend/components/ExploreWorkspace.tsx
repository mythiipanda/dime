"use client";

import { useEffect, useState } from "react";
import DraftPanel from "./DraftPanel";
import ExploreFeed from "./ExploreFeed";
import ExploreIndex from "./ExploreIndex";
import ExploreSearch from "./ExploreSearch";
import { LeadersPanel, ShotsPanel } from "./DatasetPanel";
import AdvancedStatsPanel from "./AdvancedStatsPanel";
import ZoneSplitsPanel from "./ZoneSplitsPanel";
import LineupPanel from "./LineupPanel";
import PlayoffPanel from "./PlayoffPanel";
import ScoreStrip from "./ScoreStrip";
import TradePanel from "./TradePanel";
import { getFreshness, getQueryParam, setQueryParam } from "../lib/api";
import { streakLine } from "../lib/exploreFeed";
import { updatedLine } from "../lib/freshness";
import { EXPANDABLE_PANELS, markMounted, toggleExpanded } from "../lib/explorePanels";
import { PageHeader } from "./ds/Panel";
import { Chip } from "./ds/Chip";
import type {
  ExploreContext,
  ExplorePanelId,
  SearchResult,
} from "../lib/exploreSearch";

interface ExploreWorkspaceProps {
  exploreKey: number;
  onAsk: (question: string) => void;
}

function isPanelId(v: string | null): v is ExplorePanelId {
  return v !== null && (EXPANDABLE_PANELS as string[]).includes(v);
}

export default function ExploreWorkspace({
  exploreKey,
  onAsk,
}: ExploreWorkspaceProps) {
  const [updated, setUpdated] = useState<string | null>(null);
  
  


  const [mounted, setMounted] = useState<ExplorePanelId[]>([]);
  const [expanded, setExpanded] = useState<ExplorePanelId | null>(null);
  const [ctx, setCtx] = useState<ExploreContext | null>(null);




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

  const scrollToActive = () => {
    setTimeout(() => {
      document.getElementById("explore-active")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 60);
  };

  const expand = (id: ExplorePanelId, context?: ExploreContext) => {
    const next = context ? id : toggleExpanded(expanded, id);
    setMounted((m) => markMounted(m, id));
    setExpanded(next);
    if (context) setCtx(context);
    setQueryParam("panel", next ?? "", true);
    if (next) scrollToActive();
  };
  
  



  useEffect(() => {
    const v = getQueryParam("panel");
    if (isPanelId(v)) {
      setMounted((m) => markMounted(m, v));
      setExpanded(v);
      scrollToActive();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearchSelect = (context: ExploreContext, _result?: SearchResult) => {
    expand(context.panel, context);
  };

  const handleIndexSelect = (id: ExplorePanelId) => {
    expand(id);
  };

  const handlePlayerSelect = (playerName: string) => {
    expand("shots", { panel: "shots", playerName });
  };
  
  



  const leadersKey = `leaders-${ctx?.panel === "leaders" ? (ctx.stat ?? "") : ""}`;
  const shotsKey = `shots-${ctx?.panel === "shots" ? (ctx.playerId ?? ctx.playerName ?? "") : ""}`;
  const zoneKey = `zone-${ctx?.panel === "shots" ? (ctx.playerId ?? ctx.playerName ?? "") : ""}`;
  const lineupsStreak = ctx?.panel === "lineups" ? ctx.streak : undefined;
  const lineupsKey = `lineups-${ctx?.panel === "lineups" ? (ctx.teamAbbr ?? "") : ""}-${lineupsStreak ? streakLine(lineupsStreak) : ""}`;

  return (
    <div className="min-h-full">
      <main className="mx-auto max-w-6xl px-6 py-10 lg:px-10">
        <section aria-label="Explore data">
          <PageHeader eyebrow="The evidence desk" title="Explore the game" description="Search the warehouse, follow a signal, or open a dataset. Every decision starts with a closer look." actions={<Chip>2025–26 season</Chip>} />

          <ExploreSearch onSelect={handleSearchSelect} onAsk={onAsk} />

          <ExploreIndex onSelect={handleIndexSelect} active={expanded} />

          <ExploreFeed onAsk={onAsk} onSelect={handleSearchSelect} />
        </section>

        <ScoreStrip />

        {expanded && (
          <section
            id="explore-active"
            className="mt-6 scroll-mt-6 space-y-5"
            aria-live="polite"
            key={exploreKey}
          >
            <div hidden={expanded !== "leaders"}>
              {mounted.includes("leaders") && (
                <LeadersPanel
                  key={leadersKey}
                  initialStat={ctx?.panel === "leaders" ? ctx.stat : undefined}
                  onPlayerSelect={handlePlayerSelect}
                />
              )}
              {mounted.includes("leaders") && (
                <AdvancedStatsPanel onPlayerSelect={handlePlayerSelect} />
              )}
            </div>
            <div hidden={expanded !== "shots"}>
              {mounted.includes("shots") && (
                <ShotsPanel
                  key={shotsKey}
                  initialPlayer={ctx?.panel === "shots" ? (ctx.playerId ?? ctx.playerName) : undefined}
                />
              )}
              {mounted.includes("shots") && (
                <ZoneSplitsPanel
                  key={zoneKey}
                  initialPlayerId={ctx?.panel === "shots" ? ctx.playerId : undefined}
                  initialPlayerName={ctx?.panel === "shots" ? ctx.playerName : undefined}
                />
              )}
            </div>
            <div hidden={expanded !== "trade"}>
              {mounted.includes("trade") && <TradePanel onAskValue={onAsk} />}
            </div>
            <div hidden={expanded !== "draft"}>
              {mounted.includes("draft") && <DraftPanel />}
            </div>
            <div hidden={expanded !== "lineups"}>
              {mounted.includes("lineups") && (
                <LineupPanel
                  key={lineupsKey}
                  initialTeam={ctx?.panel === "lineups" ? ctx.teamAbbr : undefined}
                  initialStreak={lineupsStreak}
                />
              )}
            </div>
            <div hidden={expanded !== "playoffs"}>
              {mounted.includes("playoffs") && <PlayoffPanel />}
            </div>
          </section>
        )}

        {updated && <footer className="mt-6 text-[11px] text-ink-3">{updated}</footer>}
      </main>
    </div>
  );
}

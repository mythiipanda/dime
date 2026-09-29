"use client";

import { useEffect, useState } from "react";
import DraftPanel from "./DraftPanel";
import ExploreFeed from "./ExploreFeed";
import ExploreIndex from "./ExploreIndex";
import ExploreSearch from "./ExploreSearch";
import { LeadersPanel, ShotsPanel } from "./DatasetPanel";
import LineupPanel from "./LineupPanel";
import PlayoffPanel from "./PlayoffPanel";
import ScoreStrip from "./ScoreStrip";
import TradePanel from "./TradePanel";
import { getFreshness, getQueryParam, setQueryParam } from "../lib/api";
import { updatedLine } from "../lib/freshness";
import { EXPANDABLE_PANELS, markMounted, toggleExpanded } from "../lib/explorePanels";
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
  const lineupsKey = `lineups-${ctx?.panel === "lineups" ? (ctx.teamAbbr ?? "") : ""}`;

  return (
    <div className="explore-scroll">
      <main className="explore-shell">
        <section className="explore-overview" aria-labelledby="explore-title">
          <div className="explore-overview-head">
            <h1 id="explore-title">Explore</h1>
          </div>

          <ExploreSearch onSelect={handleSearchSelect} onAsk={onAsk} />

          <ExploreIndex onSelect={handleIndexSelect} active={expanded} />

          <ExploreFeed onAsk={onAsk} onSelect={handleSearchSelect} />
        </section>

        <ScoreStrip />

        {expanded && (
          <section
            id="explore-active"
            className="explore-active"
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
            </div>
            <div hidden={expanded !== "shots"}>
              {mounted.includes("shots") && (
                <ShotsPanel
                  key={shotsKey}
                  initialPlayer={ctx?.panel === "shots" ? (ctx.playerId ?? ctx.playerName) : undefined}
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
                />
              )}
            </div>
            <div hidden={expanded !== "playoffs"}>
              {mounted.includes("playoffs") && <PlayoffPanel />}
            </div>
          </section>
        )}

        {updated && <footer className="explore-footer">{updated}</footer>}
      </main>
    </div>
  );
}

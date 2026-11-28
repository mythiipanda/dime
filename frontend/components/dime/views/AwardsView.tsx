"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ds/Skeleton";
import { Button } from "@/components/ds/Button";
import { DataState } from "@/components/ds/DataState";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";

type Driver = { stat: string; value: number; z: number };
type Candidate = {
  rank: number;
  player: string;
  team: string;
  score: number;
  drivers: Driver[];
  case_for: string;
  case_against: string;
};
type AwardBoard = {
  award: string;
  ok: boolean;
  error?: string | null;
  state?: string | null;
  season?: string | null;
  caveat?: string | null;
  candidates: Candidate[];
};
type AwardsResponse = {
  ok: boolean;
  season?: string;
  awards?: AwardBoard[];
  error?: string;
};

const AWARD_LABELS: Record<string, string> = {
  MVP: "MVP",
  DPOY: "DPOY",
  ROY: "Rookie of the Year",
  "6MOY": "Sixth Man",
  MIP: "Most Improved",
};

function driverValue(driver: Driver): string {
  const value = driver.stat.trimEnd().endsWith("%") && driver.value <= 1
    ? (driver.value * 100).toFixed(1)
    : String(driver.value);
  return `${value} ${driver.stat.toLowerCase()}`;
}

function driverLine(drivers: Driver[]): string {
  return drivers.slice(0, 3).map(driverValue).join(" · ");
}

function Board({ board }: { board: AwardBoard }) {
  if (!board.ok || board.candidates.length === 0) {
    return (
      <div className="rounded-card bg-surface px-5 py-8 text-center shadow-hairline">
        <DataState tone={board.error && board.state !== "empty" ? "error" : "absent"} label={board.error || "No projection available for this award yet."} detail="No substitute data is shown." />
      </div>
    );
  }
  return (
    <div>
      <div className="divide-y divide-line overflow-hidden rounded-card bg-surface shadow-hairline">
        <div className="flex items-center gap-3 px-4 py-1.5">
          <span className="w-5 shrink-0" />
          <span className="min-w-0 flex-1 font-mono text-[9.5px] uppercase tracking-wide text-ink-3">player</span>
          <span className="shrink-0 font-mono text-[9.5px] uppercase tracking-wide text-ink-3">score</span>
        </div>
        {board.candidates.map((c) => (
          <div key={c.player} className={`px-4 py-3 ${c.rank === 1 ? "bg-field/40" : ""}`}>
            <div className="flex items-center gap-3">
              <span className={`w-5 shrink-0 font-mono text-[12px] tabular-nums ${c.rank === 1 ? "font-semibold text-accent" : "text-ink-3"}`}>{c.rank}</span>
              <span className={`min-w-0 flex-1 truncate text-[13px] text-ink ${c.rank === 1 ? "font-semibold" : "font-medium"}`} title={`${c.player} · ${c.team}`}>
                {c.player}
                <span className="ml-2 font-mono text-[11px] font-normal text-ink-3">{c.team}</span>
              </span>
              <span className={`shrink-0 font-mono text-[12px] tabular-nums ${c.rank === 1 ? "font-semibold text-ink" : "text-ink-2"}`} title="projection score (z-weighted composite)">
                {c.score.toFixed(2)}
                {c.rank > 1 && board.candidates[0] && (
                  <span className="ml-1 text-[10px] text-ink-3" title="gap to the projection leader">
                    −{(board.candidates[0].score - c.score).toFixed(2)}
                  </span>
                )}
              </span>
            </div>
            <div className="mt-0.5 truncate pl-8 font-mono text-[11.5px] tabular-nums text-ink-3" title={driverLine(c.drivers)}>
              {driverLine(c.drivers)}
            </div>
            <div className="mt-1 pl-8 text-[12px] leading-[1.5] text-ink-3">
              {c.case_for}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 px-1 text-[11px] text-ink-2">
        Warehouse z-score projection over the qualified pool. Score is the weighted composite, not betting odds.
        {board.caveat ? ` ${board.caveat}.` : ""}
      </p>
    </div>
  );
}

export default function AwardsView({ onAsk }: { onAsk?: (text: string, context?: import("@/lib/view-context").ViewContext) => void }) {
  const [data, setData] = useState<AwardsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("MVP");

  useEffect(() => {
    let cancelled = false;
    fetch(`${BACKEND}${apiPath("/awards")}`)
      .then((response) => {
        if (!response.ok) throw new Error(`awards request failed (${response.status})`);
        return response.json();
      })
      .then((value: AwardsResponse) => {
        if (cancelled) return;
        if (value.ok === false) {
          setError(value.error || "awards unavailable");
          setData(null);
        } else {
          setData(value);
          setError(null);
          const first = value.awards?.find((a) => a.award === "MVP" && a.ok) ?? value.awards?.find((a) => a.ok);
          if (first) setTab((current) => current || first.award);
        }
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "awards unavailable");
        setData(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const AWARD_ORDER = ["MVP", "DPOY", "ROY", "MIP", "6MOY"];
  const boards = [...(data?.awards ?? [])].sort((a, b) => {
    const ai = AWARD_ORDER.indexOf(a.award);
    const bi = AWARD_ORDER.indexOf(b.award);
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
  });
  const active = boards.find((b) => b.award === tab) ?? boards.find((b) => b.ok) ?? boards[0];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-11 shrink-0 items-center border-b border-line px-4">
        <span className="text-[13px] font-semibold text-ink">
          Awards
          {data?.season && (
            <span className="ml-2 rounded-full border border-line px-2 py-0.5 align-middle font-mono text-[10.5px] font-normal uppercase tracking-wide text-ink-3">
              {data.season}
            </span>
          )}
        </span>
        {onAsk && active && (
          <span className="ml-auto">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onAsk(
                active.candidates.length > 0
                  ? `Break down the ${data?.season ?? ""} ${active.award} race: who leads, who is closing, and what the case against the favorite is.`
                  : `The ${data?.season ?? ""} ${active.award} race has no qualified candidates in the warehouse yet. When do players typically become eligible, and who would be the early favorites from last season\'s form?`,
                {
                  kind: "awards_race",
                  summary: `${active.award} race · ${data?.season ?? ""}`,
                  entities: {
                    award: active.award,
                    season: data?.season,
                    candidates: active.candidates.slice(0, 8).map((c) => ({ rank: c.rank, player: c.player, team: c.team, score: c.score })),
                  },
                },
              )}
            >
              Ask Dime about this race
            </Button>
          </span>
        )}
      </div>

      {loading && (
        <div className="px-4 pt-4">
  <div className="divide-y divide-line overflow-hidden rounded-card bg-surface shadow-hairline" aria-label="loading award projections">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-4 py-3">
                <div className="flex items-center gap-3">
                  <Skeleton className="h-3.5 w-5" />
                  <Skeleton className="h-3.5 w-44" />
                  <Skeleton className="ml-auto h-3.5 w-8" />
                </div>
                <Skeleton className="ml-8 mt-2 h-3 w-64" />
                <Skeleton className="ml-8 mt-1.5 h-3 w-52" />
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && error && (
        <div className="px-4 pt-4">
          <div role="alert" className="rounded-card border border-line bg-surface px-5 py-8 text-center shadow-hairline">
            <DataState tone="error" label={error} detail="No substitute data is shown." />
          </div>
        </div>
      )}

      {!loading && !error && boards.length > 0 && (
        <>
          <div className="flex shrink-0 items-center gap-1 overflow-x-auto px-4 pt-3">
            {boards.map((b) => (
              <button
                key={b.award}
                type="button"
                onClick={() => setTab(b.award)}
                aria-pressed={tab === b.award}
                className={`h-7 shrink-0 select-none rounded-[7px] px-2.5 text-[12.5px] font-medium transition-[background-color,color,transform] duration-150 active:scale-[0.96] ${
                  tab === b.award ? "bg-hover text-ink" : "text-ink-3 hover:text-ink-2"
                }`}
              >
                {AWARD_LABELS[b.award] ?? b.award}
              </button>
            ))}
          </div>

          <div className="mt-3 min-h-0 flex-1 overflow-y-auto px-4 pb-8">
            {active && (
              <div key={active.award} style={{ animation: "fade-up 180ms var(--ease-out-strong) both" }}>
                <Board board={active} />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

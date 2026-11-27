"use client";

import { useEffect, useState } from "react";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";
import { Button } from "@/components/ds/Button";
import ArtifactChart from "../ArtifactChart";

type ArcSeason = {
  season: string;
  end_year: number;
  pts: number | null;
  reb: number | null;
  ast: number | null;
  fg_pct: number | null;
  fg3_pct: number | null;
  min: number | null;
  gp: number | null;
  raptor: number | null;
  source?: string;
};

type CareerResponse = {
  ok: boolean;
  rows?: ArcSeason[];
  error?: string;
  meta?: { player_id?: number; player?: string };
};

type CompRow = {
  PLAYER: string;
  PLAYER_ID: number;
  TEAM: string;
  season: string;
  similarity: number;
  drivers?: string[];
  archetype?: string;
  shared_archetype?: boolean;
};

type CompsResponse = {
  ok: boolean;
  rows?: CompRow[];
  error?: string;
};

type LeaderRow = { rank: number; player_id: number; player: string; value: number; z: number };
type LeadersResponse = {
  ok: boolean;
  rows?: LeaderRow[];
  season?: string;
  error?: string;
  meta?: { source?: string; pool?: number; normalization?: string };
};

function currentSeasonEndYear(now = new Date()): number {
  return now.getMonth() >= 9 ? now.getFullYear() + 1 : now.getFullYear();
}

const SEASONS: string[] = [];
for (let end = currentSeasonEndYear(); end >= 1997; end -= 1) {
  SEASONS.push(`${end - 1}-${String(end).slice(2)}`);
}

const CATEGORIES = [
  ["pts", "points"], ["reb", "rebounds"], ["ast", "assists"], ["stl", "steals"],
  ["blk", "blocks"], ["min", "minutes"], ["ts_pct", "true shooting"], ["fg3_pct", "three-point %"],
] as const;

function fmt(value: number | null | undefined, digits = 1): string {
  if (value == null) return "–";
  return value.toFixed(digits);
}

export default function HistoryView() {
  const [query, setQuery] = useState("Jayson Tatum");
  const [player, setPlayer] = useState("Jayson Tatum");
  const [career, setCareer] = useState<CareerResponse | null>(null);
  const [careerError, setCareerError] = useState<string | null>(null);
  const [careerLoading, setCareerLoading] = useState(false);
  const [selectedSeason, setSelectedSeason] = useState<string | null>(null);
  const [comps, setComps] = useState<CompsResponse | null>(null);
  const [compsError, setCompsError] = useState<string | null>(null);
  const [compsLoading, setCompsLoading] = useState(false);
  const [leaderSeason, setLeaderSeason] = useState("1996-97");
  const [category, setCategory] = useState<string>("pts");
  const [leaders, setLeaders] = useState<LeadersResponse | null>(null);
  const [leadersError, setLeadersError] = useState<string | null>(null);
  const [leadersLoading, setLeadersLoading] = useState(false);

  useEffect(() => {
    if (!player) return;
    let cancelled = false;
    setCareerLoading(true);
    setCareerError(null);
    fetch(`${BACKEND}${apiPath(`/history/career?player=${encodeURIComponent(player)}`)}`)
      .then(async (response) => {
        const body = await response.json().catch(() => null);
        if (!response.ok) throw new Error(body?.error || `career request failed (${response.status})`);
        return body as CareerResponse;
      })
      .then((value) => {
        if (cancelled) return;
        if (!value || value.ok === false) {
          setCareerError(value?.error || "career arc unavailable");
          setCareer(null);
        } else {
          setCareer(value);
          setSelectedSeason(null);
          setComps(null);
        }
        setCareerLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setCareerError(err instanceof Error ? err.message : "career arc unavailable");
        setCareer(null);
        setCareerLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [player]);

  useEffect(() => {
    if (!selectedSeason || !player) return;
    let cancelled = false;
    setCompsLoading(true);
    setCompsError(null);
    fetch(`${BACKEND}${apiPath(`/history/era-comps?player=${encodeURIComponent(player)}&season=${encodeURIComponent(selectedSeason)}&k=8`)}`)
      .then(async (response) => {
        const body = await response.json().catch(() => null);
        if (!response.ok) throw new Error(body?.error || `era comps request failed (${response.status})`);
        return body as CompsResponse;
      })
      .then((value) => {
        if (cancelled) return;
        if (!value || value.ok === false) {
          setCompsError(value?.error || "era comps unavailable");
          setComps(null);
        } else {
          setComps(value);
        }
        setCompsLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setCompsError(err instanceof Error ? err.message : "era comps unavailable");
        setComps(null);
        setCompsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSeason, player]);

  useEffect(() => {
    let cancelled = false;
    setLeadersLoading(true);
    setLeadersError(null);
    fetch(`${BACKEND}${apiPath(`/history/leaders?season=${encodeURIComponent(leaderSeason)}&category=${encodeURIComponent(category)}`)}`)
      .then(async (response) => {
        const body = await response.json().catch(() => null);
        if (!response.ok) throw new Error(body?.error || `leaderboard request failed (${response.status})`);
        return body as LeadersResponse;
      })
      .then((value) => {
        if (cancelled) return;
        if (!value || value.ok === false) {
          setLeadersError(value?.error || "leaderboard unavailable");
          setLeaders(null);
        } else {
          setLeaders(value);
        }
        setLeadersLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setLeadersError(err instanceof Error ? err.message : "leaderboard unavailable");
        setLeaders(null);
        setLeadersLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [leaderSeason, category]);

  const arc = career?.rows ?? [];
  const chartSeasons = arc.map((s) => s.season);
  const series = [
    { name: "points per game", values: arc.map((s) => s.pts), tone: "accent" as const, unit: "ppg" },
    { name: "raptor", values: arc.map((s) => s.raptor), tone: "muted" as const, unit: "raptor" },
  ];

  return (
    <div className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-8">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-[15px] font-semibold text-ink">History</h1>
        <span className="font-mono text-[10px] text-ink-3">{`1996-97 → ${SEASONS[0]} · era-relative throughout`}</span>
      </div>

      <div className="mt-4 xl:grid xl:grid-cols-[minmax(0,1fr)_340px] xl:items-start xl:gap-4">
      <div>
      <section className="rounded-[10px] bg-surface p-4 shadow-hairline sm:p-5">
        <form
          className="flex items-center gap-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (query.trim()) setPlayer(query.trim());
          }}
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="player name"
            aria-label="player name"
            className="h-8 w-0 flex-1 rounded-[7px] border border-line bg-surface px-2.5 text-[13px] text-ink placeholder:text-ink-3"
          />
          <Button type="submit" variant="accent" size="sm">
            career arc
          </Button>
        </form>

        {careerLoading && <p className="mt-3 text-[12.5px] text-ink-3">Loading the arc…</p>}
        {careerError && !careerLoading && (
          <p role="alert" className="mt-3 text-[12.5px] text-red">{careerError}. No sample data is substituted.</p>
        )}

        {!careerLoading && !careerError && arc.length > 0 && (
          <div className="mt-3">
            <ArtifactChart
              series={series}
              xLabels={chartSeasons}
              title={`${player} career trajectory`}
              subtitle="per-game scoring and RAPTOR impact by season — open 'view chart data' for the table"
              height={200}
            />
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[560px] border-separate border-spacing-0 text-[12px]">
                <thead>
                  <tr>
                    {["season", "gp", "min", "pts", "reb", "ast", "fg%", "3p%", "raptor"].map((h) => (
                      <th key={h} className={`px-2 py-1 font-mono text-[10px] font-normal uppercase tracking-wide text-ink-3 ${h === "season" ? "text-left" : "text-right"}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {arc.map((row) => (
                    <tr
                      key={row.season}
                      className={`cursor-pointer hover:bg-field ${selectedSeason === row.season ? "bg-field" : ""}`}
                      onClick={() => setSelectedSeason(row.season)}
                      title="click for era comps of this season"
                    >
                      <td className="border-t border-line px-2 py-1 font-mono text-ink">{row.season}</td>
                      <td className="border-t border-line px-2 py-1 text-right font-mono tabular-nums text-ink-2">{row.gp ?? "–"}</td>
                      <td className="border-t border-line px-2 py-1 text-right font-mono tabular-nums text-ink-2">{fmt(row.min)}</td>
                      <td className="border-t border-line px-2 py-1 text-right font-mono tabular-nums text-ink">{fmt(row.pts)}</td>
                      <td className="border-t border-line px-2 py-1 text-right font-mono tabular-nums text-ink-2">{fmt(row.reb)}</td>
                      <td className="border-t border-line px-2 py-1 text-right font-mono tabular-nums text-ink-2">{fmt(row.ast)}</td>
                      <td className="border-t border-line px-2 py-1 text-right font-mono tabular-nums text-ink-2">{row.fg_pct != null ? `${(row.fg_pct * 100).toFixed(1)}` : "–"}</td>
                      <td className="border-t border-line px-2 py-1 text-right font-mono tabular-nums text-ink-2">{row.fg3_pct != null ? `${(row.fg3_pct * 100).toFixed(1)}` : "–"}</td>
                      <td className="border-t border-line px-2 py-1 text-right font-mono tabular-nums text-ink-2">{fmt(row.raptor)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 font-mono text-[10px] text-ink-3">click a season row for its era-relative neighbors · sources per row from the career arc tool</p>
          </div>
        )}
      </section>

      {selectedSeason && (
        <section className="mt-3 rounded-[10px] bg-surface p-4 shadow-hairline sm:p-5">
          <h3 className="text-[13px] font-semibold text-ink">
            Era-relative neighbors — {player} {selectedSeason}
          </h3>
          {compsLoading && <p className="mt-2 text-[12.5px] text-ink-3">Scoring the pool…</p>}
          {compsError && !compsLoading && (
            <p role="alert" className="mt-2 text-[12.5px] text-red">{compsError}. No substitute data is shown.</p>
          )}
          {!compsLoading && !compsError && comps?.rows && (
            <div className="mt-2 divide-y divide-line">
              {comps.rows.map((comp, i) => (
                <div key={i} className="flex items-baseline justify-between gap-2 py-1.5 text-[12.5px]">
                  <span className="text-ink-2">
                    {comp.PLAYER}
                    <span className="ml-1.5 font-mono text-[10px] text-ink-3">{comp.season} {comp.TEAM}</span>
                    {comp.shared_archetype && <span className="ml-1.5 rounded-full border border-line px-1.5 font-mono text-[9px] text-ink-3">{comp.archetype}</span>}
                  </span>
                  <span className="font-mono tabular-nums text-ink-3">{comp.similarity?.toFixed(1)}</span>
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 font-mono text-[10px] leading-[1.6] text-ink-3">
            similarity = 100/(1+d/20) over within-season z-scores — each feature standardized inside its own season's qualified pool, so the match is era-relative shape, not raw level
          </p>
        </section>
      )}
      </div>

      <div className="xl:sticky xl:top-6">
      <section className="mt-3 rounded-[10px] bg-surface p-4 shadow-hairline sm:p-5 xl:mt-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[13px] font-semibold text-ink">Era leaderboard</h3>
          <div className="ml-auto flex items-center gap-1.5 text-[12px]">
            <select
              value={leaderSeason}
              onChange={(e) => setLeaderSeason(e.target.value)}
              aria-label="season"
              className="h-7 rounded-[7px] border border-line bg-surface px-1.5 text-[12px] text-ink"
            >
              {SEASONS.map((season) => <option key={season} value={season}>{season}</option>)}
            </select>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              aria-label="category"
              className="h-7 rounded-[7px] border border-line bg-surface px-1.5 text-[12px] text-ink"
            >
              {CATEGORIES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
          </div>
        </div>

        {leadersLoading && <p className="mt-2 text-[12.5px] text-ink-3">Ranking the pool…</p>}
        {leadersError && !leadersLoading && (
          <p role="alert" className="mt-2 text-[12.5px] text-red">{leadersError}. No substitute data is shown.</p>
        )}
        {!leadersLoading && !leadersError && leaders?.rows && (
          <div className="mt-2 divide-y divide-line">
            {leaders.rows.map((row) => (
              <div key={row.rank} className="flex items-baseline justify-between gap-2 py-1.5 text-[12.5px]">
                <span className="text-ink-2">
                  <span className="mr-2 font-mono text-[10.5px] text-ink-3">{row.rank}</span>
                  {row.player}
                </span>
                <span className="font-mono tabular-nums text-ink-3">
                  <span className="text-ink">{row.value}</span>
                  <span className="ml-2 text-[10.5px]">z {row.z > 0 ? "+" : ""}{row.z}</span>
                </span>
              </div>
            ))}
          </div>
        )}
        {leaders?.meta && (
          <p className="mt-2 font-mono text-[10px] leading-[1.6] text-ink-3">
            {leaders.meta.source} · pool of {leaders.meta.pool} · {leaders.meta.normalization}
          </p>
        )}
      </section>
      </div>
      </div>
    </div>
  );
}

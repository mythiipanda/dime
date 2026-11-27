"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ds/Skeleton";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";
import { DataState } from "@/components/ds/DataState";
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

type CompDriver = { stat: string; target: number | null; comp: number | null };

type CompRow = {
  z?: Record<string, number>;
  PLAYER: string;
  PLAYER_ID: number;
  TEAM: string;
  season: string;
  age?: number | null;
  similarity: number;
  drivers?: CompDriver[];
  archetype?: string;
  shared_archetype?: boolean;
};

type CompsQualification = {
  gp: number;
  min_pg: number;
  total_min: number | null;
  rule: string;
};

type CompsResponse = {
  ok: boolean;
  qualified?: boolean;
  rows?: CompRow[];
  player?: { name?: string; z?: Record<string, number> };
  qualification?: CompsQualification;
  qualifying_seasons?: string[];
  meta?: { features?: string[]; feature_labels?: Record<string, string> };
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


const FRACTION_STAT = /efficiency|rate|true shooting/i;

function fmtDriver(stat: string, value: number | null): string {
  if (value == null) return "–";
  if (FRACTION_STAT.test(stat)) return `${(value * 100).toFixed(1)}%`;
  return String(value);
}


function ShapeChart({ target, comp, features, labels, compName }: {
  target: Record<string, number>;
  comp: Record<string, number>;
  features: string[];
  labels: Record<string, string>;
  compName: string;
}) {
  const CLAMP = 3;
  const width = (z: number) => `${Math.min(Math.abs(z), CLAMP) / CLAMP * 50}%`;
  return (
    <div data-testid="shape-chart" className="rounded-[8px] bg-field p-3">
      <p className="font-mono text-[10px] text-ink-3">{`shape profile vs ${compName} — within-season z-scores from center zero; overlap is the match, clamped at ±3`}</p>
      <div className="mt-2 space-y-1">
        {features.map((feat) => {
          const tz = target[feat] ?? 0;
          const cz = comp[feat] ?? 0;
          return (
            <div key={feat} className="grid grid-cols-[170px_minmax(0,1fr)] items-center gap-2">
              <span className="truncate text-right text-[10.5px] text-ink-3">{labels[feat] ?? feat}</span>
              <div className="relative h-[10px]">
                <div className="absolute left-1/2 top-0 h-full w-px bg-line" />
                <div
                  data-z={tz.toFixed(1)}
                  data-side="target"
                  className="absolute top-[1px] h-[8px] rounded-[2px] bg-ink-3/50"
                  style={{ width: width(tz), ...(tz >= 0 ? { left: "50%" } : { right: "50%" }) }}
                  title={`target z ${tz.toFixed(1)}`}
                />
                <div
                  data-z={cz.toFixed(1)}
                  data-side="comp"
                  className="absolute top-[1px] h-[8px] rounded-[2px] bg-accent/70"
                  style={{ width: width(cz), ...(cz >= 0 ? { left: "50%" } : { right: "50%" }), opacity: 0.75 }}
                  title={`comp z ${cz.toFixed(1)}`}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function HistoryView({ onAsk }: { onAsk?: (text: string, context?: import("@/lib/view-context").ViewContext) => void }) {
  const [query, setQuery] = useState("Jayson Tatum");
  const [player, setPlayer] = useState("Jayson Tatum");
  const [career, setCareer] = useState<CareerResponse | null>(null);
  const [careerError, setCareerError] = useState<string | null>(null);
  const [careerLoading, setCareerLoading] = useState(false);
  const [selectedSeason, setSelectedSeason] = useState<string | null>(null);
  const [comps, setComps] = useState<CompsResponse | null>(null);
  const [compsError, setCompsError] = useState<string | null>(null);
  const [compsLoading, setCompsLoading] = useState(false);
  const [selectedComp, setSelectedComp] = useState(0);
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
    fetch(`${BACKEND}${apiPath(`/history/era-comps?player=${encodeURIComponent(player)}&season=${encodeURIComponent(selectedSeason)}&k=12`)}`)
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
          setSelectedComp(0);
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
        <span className="text-[11px] text-ink-2">{`1996-97 → ${SEASONS[0]} · era-relative throughout`}</span>
        {onAsk && career && (
          <span className="ml-auto">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onAsk(
                `Break down ${player}'s career arc — the peak, the trajectory, and how the era-relative profile compares.${selectedSeason ? ` Focus on the ${selectedSeason} season.` : ""}`,
                {
                  kind: "career_arc",
                  summary: `${player} career arc${selectedSeason ? ` · ${selectedSeason}` : ""}`,
                  entities: {
                    player,
                    ...(selectedSeason ? { season: selectedSeason } : {}),
                    seasons: (career.rows ?? []).map((row: Record<string, unknown>) => row.season).filter(Boolean),
                  },
                },
              )}
            >
              Ask Dime about this arc
            </Button>
          </span>
        )}
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

        {careerLoading && (
          <div className="mt-3" aria-label="loading the arc">
            <Skeleton className="h-[200px] rounded-[8px]" />
            <div className="mt-3 space-y-2">
              {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[18px]" />)}
            </div>
          </div>
        )}
        {careerError && !careerLoading && (
          <DataState tone="error" label={careerError} detail="No substitute data is shown." className="mt-3" />
        )}

        {!careerLoading && !careerError && arc.length > 0 && (
          <div className="mt-3">
            <div className="grid gap-2">
              <ArtifactChart
                series={series.slice(0, 1)}
                xLabels={chartSeasons}
                title={`${player} scoring trajectory`}
                subtitle="points per game by season — open 'view chart data' for exact figures"
                height={130}
              />
              <ArtifactChart
                series={series.slice(1)}
                xLabels={chartSeasons}
                title={`${player} impact trajectory`}
                subtitle="RAPTOR impact by season — open 'view chart data' for exact figures"
                height={130}
              />
            </div>
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
            <p className="mt-2 text-[11px] text-ink-2">
              click a season row for its era-relative neighbors · sources per row from the career arc tool
              {(() => {
                const lastCovered = [...arc].reverse().find((row) => row.raptor != null);
                const hasGap = lastCovered && arc.some((row) => row.season > lastCovered.season);
                return hasGap ? ` · raptor coverage ends ${lastCovered.season} — later seasons show –` : "";
              })()}
            </p>
          </div>
        )}
      </section>

      {selectedSeason && (
        <section className="mt-3 rounded-[10px] bg-surface p-4 shadow-hairline sm:p-5">
          <h3 className="text-[13px] font-semibold text-ink">
            Era-relative neighbors — {player} {selectedSeason}
          </h3>
          {compsLoading && (
            <div className="mt-2 space-y-2" aria-label="loading era comps">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[52px] rounded-[8px]" />)}
            </div>
          )}
          {compsError && !compsLoading && (
            <DataState tone="error" label={compsError} detail="No substitute data is shown." className="mt-2" />
          )}
          {!compsLoading && !compsError && comps?.qualified === false && comps.qualification && (
            <div className="mt-2 rounded-[8px] bg-field p-3 text-[12.5px] text-ink-2">
              <p>
                {`${player}'s ${selectedSeason} does not meet the era comps qualification minimum (${comps.qualification.rule} — this season: ${comps.qualification.gp} gp, ${comps.qualification.total_min != null ? `${Math.round(comps.qualification.total_min)} total minutes` : "minutes unavailable"}).`}
              </p>
              {comps.qualifying_seasons && comps.qualifying_seasons.length > 0 && (
                <p className="mt-1.5">
                  qualifying seasons:{" "}
                  {comps.qualifying_seasons.map((season, i) => (
                    <span key={season}>
                      {i > 0 && " · "}
                      <button
                        type="button"
                        className="font-mono text-[11.5px] text-accent underline-offset-2 hover:underline"
                        onClick={() => setSelectedSeason(season)}
                      >
                        {season}
                      </button>
                    </span>
                  ))}
                </p>
              )}
            </div>
          )}
          {!compsLoading && !compsError && comps?.qualified !== false && comps?.rows && comps.rows.length > 0 && (
            <div className="mt-2">
              {(() => {
                const features = comps.meta?.features ?? [];
                const labels = comps.meta?.feature_labels ?? {};
                const tz = comps.player?.z;
                const active = comps.rows[Math.min(selectedComp, comps.rows.length - 1)];
                if (!tz || !active?.z || features.length === 0) return null;
                return <ShapeChart target={tz} comp={active.z} features={features} labels={labels} compName={`${active.PLAYER} ${active.season}`} />;
              })()}
              <p className="mt-2 font-mono text-[10px] text-ink-3">driver values: target season vs comp · click a comp to overlay its shape</p>
              {comps.rows.length === 0 && (
                <p className="mt-1.5 text-[12.5px] text-ink-2">no era neighbors found within the pool window — widen the window or pick another season.</p>
              )}
              <div className="mt-1.5 divide-y divide-line">
                {comps.rows.map((comp, i) => (
                  <button
                    type="button"
                    key={`${comp.PLAYER_ID}-${comp.season}-${i}`}
                    className={`block w-full cursor-pointer py-2.5 text-left ${i === selectedComp ? "bg-field" : ""} rounded-[6px] px-2 -mx-2`}
                    onClick={() => setSelectedComp(i)}
                    aria-pressed={i === selectedComp}
                    title="overlay this comp's shape profile"
                  >
                    <div className="flex items-baseline justify-between gap-2 text-[12.5px]">
                      <span className="text-ink">
                        {comp.PLAYER}
                        <span className="ml-1.5 font-mono text-[10px] text-ink-3">
                          {comp.season} {comp.TEAM}{comp.age != null ? ` · age ${comp.age}` : ""}
                        </span>
                        {comp.shared_archetype && comp.archetype && (
                          <span className="ml-1.5 rounded-full border border-line px-1.5 font-mono text-[9px] text-ink-3">{comp.archetype}</span>
                        )}
                      </span>
                      <span className="font-mono tabular-nums text-ink">{comp.similarity?.toFixed(1)}</span>
                    </div>
                    {comp.drivers && comp.drivers.length > 0 && (
                      <div className="mt-1 space-y-0.5">
                        {comp.drivers.map((driver) => (
                          <div key={driver.stat} className="flex items-baseline justify-between gap-2 text-[11.5px]">
                            <span className="text-ink-3">{driver.stat}</span>
                            <span className="font-mono tabular-nums text-ink-2">
                              {fmtDriver(driver.stat, driver.target)}
                              <span className="mx-1 text-ink-3">vs</span>
                              {fmtDriver(driver.stat, driver.comp)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </button>
                ))}
              </div>
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
          <DataState tone="error" label={leadersError} detail="No substitute data is shown." className="mt-2" />
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

"use client";

import { useEffect, useState } from "react";
import { initialTeamParam } from "@/lib/open-in-view";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";

const TEAMS = [
  "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
  "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
  "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
];

type Section = { source?: string; ok?: boolean; error?: string | null; rows?: unknown; note?: string };
type Dossier = {
  ok: boolean;
  season?: string;
  edge?: string | null;
  team?: { abbrev?: string };
  opponent?: { abbrev?: string; team_id?: number };
  sections?: Record<string, Section>;
  error?: string;
};

type FormGame = { date: string; matchup: string; wl: string; pts: number | null; opp_pts: number | null };
type ShotZone = { zone: string; fga: number; share: number; fg_pct: number };
type LineupRow = { group: string; min: number; plus_minus: number; w: number; l: number; sample: string | null };
type H2HGame = { date: string; matchup: string; wl: string; pts: number | null; opp_pts: number | null };

function Source({ name }: { name?: string }) {
  if (!name) return null;
  return <span className="font-mono text-[10px] text-ink-3">{name}</span>;
}

function SectionShell({ title, source, error, children }: { title: string; source?: string; error?: string | null; children: React.ReactNode }) {
  return (
    <section className="rounded-[10px] bg-surface p-4 shadow-hairline sm:p-5">
      <div className="flex items-baseline justify-between">
        <h3 className="font-mono text-[10px] uppercase tracking-wider text-ink-3">{title}</h3>
        <Source name={source} />
      </div>
      {error ? (
        <p className="mt-3 text-[12.5px] text-ink-3">{error} — this section is unavailable; no substitute data is shown.</p>
      ) : (
        <div className="mt-3">{children}</div>
      )}
    </section>
  );
}

function sectionError(section: Section | undefined, missing: boolean): string | null {
  if (!missing) return null;
  if (section?.error) return section.error;
  if (section != null && section.rows == null && typeof section.note === "string") return section.note;
  return "not available";
}

function pct1(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

export default function ScoutView() {
  const [team, setTeam] = useState(() => initialTeamParam() ?? "BOS");
  const [opponent, setOpponent] = useState(() => {
    const seeded = initialTeamParam();
    return seeded === "NYK" ? "BOS" : "NYK";
  });
  const [data, setData] = useState<Dossier | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!team || !opponent || team === opponent) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${BACKEND}${apiPath(`/scout-dossier?team=${encodeURIComponent(team)}&opponent=${encodeURIComponent(opponent)}`)}`)
      .then(async (response) => {
        const body = await response.json().catch(() => null);
        if (!response.ok) throw new Error(body?.error || `dossier request failed (${response.status})`);
        return body as Dossier;
      })
      .then((value) => {
        if (cancelled) return;
        if (!value || value.ok === false) {
          setError(value?.error || "dossier unavailable");
          setData(null);
        } else {
          setData(value);
        }
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "dossier unavailable");
        setData(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [team, opponent]);

  const sections = data?.sections ?? {};
  const form = sections.recent_form?.rows as { last10_record?: string; games?: FormGame[]; avg_pts?: number; avg_opp_pts?: number } | undefined;
  const factors = sections.four_factors?.rows as { offense?: Record<string, number>; defense?: Record<string, number>; note?: string } | undefined;
  const zones = (sections.shot_profile?.rows as ShotZone[] | undefined) ?? [];
  const lineups = (sections.top_lineups?.rows as LineupRow[] | undefined) ?? [];
  type RotationPlayer = Record<string, unknown>;
  const rotation = sections.rotation?.rows as
    | { players?: RotationPlayer[]; tiers?: { core?: RotationPlayer[]; bench?: RotationPlayer[]; fringe?: RotationPlayer[] } }
    | RotationPlayer[]
    | undefined;
  const injuries = (sections.injuries?.rows as Array<Record<string, unknown>> | undefined) ?? [];
  const h2h = sections.head_to_head?.rows as { record?: string; games?: H2HGame[] } | undefined;

  const rotationPlayers: RotationPlayer[] = Array.isArray(rotation)
    ? rotation
    : rotation?.tiers
      ? [...(rotation.tiers.core ?? []), ...(rotation.tiers.bench ?? []), ...(rotation.tiers.fringe ?? [])]
      : (rotation?.players ?? []);

  return (
    <div className="mx-auto w-full max-w-[760px] px-4 py-6 sm:px-8">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-[15px] font-semibold text-ink">Opponent prep</h1>
        <div className="ml-auto flex items-center gap-1.5 text-[12.5px]">
          <label className="text-ink-3" htmlFor="scout-team">Our team</label>
          <select
            id="scout-team"
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            className="h-7 rounded-[7px] border border-line bg-surface px-1.5 text-[12.5px] text-ink"
          >
            {TEAMS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <span className="text-ink-3">vs</span>
          <label className="sr-only" htmlFor="scout-opponent">Opponent</label>
          <select
            id="scout-opponent"
            value={opponent}
            onChange={(e) => setOpponent(e.target.value)}
            className="h-7 rounded-[7px] border border-line bg-surface px-1.5 text-[12.5px] text-ink"
          >
            {TEAMS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      {team === opponent && (
        <div className="mt-4 rounded-[10px] bg-surface p-8 text-center text-[13px] text-ink-3 shadow-hairline">
          Pick two different teams to build the dossier.
        </div>
      )}

      {loading && team !== opponent && (
        <div className="mt-4 rounded-[10px] bg-surface p-8 text-center text-[13px] text-ink-3 shadow-hairline">
          Assembling the dossier…
        </div>
      )}

      {!loading && error && team !== opponent && (
        <div role="alert" className="mt-4 rounded-[10px] border border-line bg-surface p-8 text-center shadow-hairline">
          <p className="text-[13px] text-red">{error}. No sample data is substituted.</p>
        </div>
      )}

      {!loading && !error && data && team !== opponent && (
        <div className="mt-4 space-y-3">
          {data.edge && (
            <div className="rounded-[10px] bg-surface p-4 text-[13px] leading-[1.6] text-ink-2 shadow-hairline sm:p-5">
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-3">edge</span>
              <p className="mt-1">{data.edge}</p>
              {data.season && <p className="mt-1 font-mono text-[10.5px] text-ink-3">season {data.season} · warehouse-nightly freshness</p>}
            </div>
          )}

          <SectionShell title="Recent form" source={sections.recent_form?.source} error={sectionError(sections.recent_form, !form)}>
            {form && (
              <div>
                <div className="flex items-baseline gap-3 text-[13px]">
                  <span className="font-medium text-ink">last 10: {form.last10_record ?? "–"}</span>
                  {form.avg_pts != null && <span className="text-ink-3">{form.avg_pts} for / {form.avg_opp_pts} against</span>}
                </div>
                <div className="mt-2 divide-y divide-line">
                  {(form.games ?? []).map((g, i) => (
                    <div key={i} className="flex items-baseline justify-between py-1.5 text-[12.5px]">
                      <span className="text-ink-2">{g.matchup}</span>
                      <span className="font-mono tabular-nums text-ink-3">
                        <span className={g.wl === "W" ? "text-ink" : ""}>{g.wl}</span> {g.pts}–{g.opp_pts}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </SectionShell>

          <SectionShell title="Four factors" source={sections.four_factors?.source} error={sectionError(sections.four_factors, !factors)}>
            {factors?.offense && factors?.defense && (
              <div className="grid grid-cols-2 gap-3">
                {(["offense", "defense"] as const).map((side) => (
                  <div key={side}>
                    <div className="font-mono text-[10px] uppercase tracking-wide text-ink-3">{side}</div>
                    <div className="mt-1 space-y-1">
                      {Object.entries(factors[side]!).map(([k, v]) => (
                        <div key={k} className="flex justify-between text-[12.5px]">
                          <span className="text-ink-2">{k.replace("_pct", "%").replace("_", " ")}</span>
                          <span className="font-mono tabular-nums text-ink">{k.includes("pct") || k === "ftr" ? pct1(v) : v}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SectionShell>

          <SectionShell title="Shot profile" source={sections.shot_profile?.source} error={sectionError(sections.shot_profile, zones.length === 0)}>
            <div className="space-y-2">
              {zones.map((z) => (
                <div key={z.zone}>
                  <div className="flex items-baseline justify-between text-[12.5px]">
                    <span className="text-ink-2">{z.zone}</span>
                    <span className="font-mono tabular-nums text-ink-3">
                      {(z.share * 100).toFixed(1)}% of shots · {(z.fg_pct * 100).toFixed(1)}% fg
                    </span>
                  </div>
                  <div className="mt-1 h-1 overflow-hidden rounded-full bg-field" aria-hidden>
                    <div className="h-full rounded-full bg-ink" style={{ width: `${Math.max(3, z.share * 100 * 2.5)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </SectionShell>

          <SectionShell title="Top lineups" source={sections.top_lineups?.source} error={sectionError(sections.top_lineups, lineups.length === 0)}>
            <div className="divide-y divide-line">
              {lineups.slice(0, 5).map((l, i) => (
                <div key={i} className="py-2">
                  <div className="text-[12.5px] leading-[1.5] text-ink-2">{l.group}</div>
                  <div className="mt-0.5 flex gap-3 font-mono text-[11px] tabular-nums text-ink-3">
                    <span>{Math.round(l.min)} min</span>
                    <span className={l.plus_minus >= 0 ? "text-ink" : ""}>{l.plus_minus >= 0 ? "+" : ""}{l.plus_minus} +/-</span>
                    <span>{l.w}–{l.l}</span>
                    {l.sample && <span className="rounded-full border border-line px-1.5">{l.sample} sample</span>}
                  </div>
                </div>
              ))}
            </div>
          </SectionShell>

          <SectionShell title="Rotation shape" source={sections.rotation?.source} error={sectionError(sections.rotation, rotationPlayers.length === 0)}>
            <div className="divide-y divide-line">
              {(rotationPlayers as Array<Record<string, unknown>>).slice(0, 10).map((p, i) => {
                const name = String(p.player ?? p.player_name ?? p.PLAYER ?? "?");
                const mpg = typeof p.mpg === "number" ? p.mpg : typeof p.MPG === "number" ? p.MPG : null;
                const pts = typeof p.pts === "number" ? p.pts : typeof p.PTS === "number" ? p.PTS : null;
                return (
                  <div key={i} className="flex items-baseline justify-between py-1.5 text-[12.5px]">
                    <span className="text-ink-2">{name}</span>
                    <span className="font-mono tabular-nums text-ink-3">
                      {mpg != null ? `${mpg.toFixed(1)} mpg` : ""}{pts != null ? ` · ${pts.toFixed(1)} ppg` : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          </SectionShell>

          <SectionShell title="Injury report" source={sections.injuries?.source} error={sectionError(sections.injuries, sections.injuries?.rows == null)}>
            {injuries.length === 0 ? (
              <p className="text-[12.5px] text-ink-3">No injuries listed for the opponent.</p>
            ) : (
              <div className="divide-y divide-line">
                {injuries.slice(0, 6).map((inj, i) => (
                  <div key={i} className="py-1.5 text-[12.5px] text-ink-2">{String(inj.player ?? inj.name ?? inj.display ?? JSON.stringify(inj).slice(0, 90))}</div>
                ))}
              </div>
            )}
          </SectionShell>

          <SectionShell title="Season series" source={sections.head_to_head?.source} error={sectionError(sections.head_to_head, !h2h)}>
            {h2h && (
              <div>
                <div className="text-[13px] font-medium text-ink">season series: {h2h.record ?? "–"}</div>
                <div className="mt-2 divide-y divide-line">
                  {(h2h.games ?? []).map((g, i) => (
                    <div key={i} className="flex items-baseline justify-between py-1.5 text-[12.5px]">
                      <span className="text-ink-2">{g.matchup}</span>
                      <span className="font-mono tabular-nums text-ink-3">
                        <span className={g.wl === "W" ? "text-ink" : ""}>{g.wl}</span> {g.pts}–{g.opp_pts}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </SectionShell>
        </div>
      )}
    </div>
  );
}

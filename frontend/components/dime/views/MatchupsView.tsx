"use client";

import { useEffect, useMemo, useState } from "react";
import { Skeleton } from "@/components/ds/Skeleton";
import { initialTeamParam } from "@/lib/open-in-view";
import FormChips from "@/components/dime/views/FormChips";
import { DataState } from "@/components/ds/DataState";
import { Button } from "@/components/ds/Button";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";

type TeamPayload = {
  abbr: string;
  name: string;
  record: string;
  net_rating: number | null;
  off_rating: number | null;
  def_rating: number | null;
  pace: number | null;
  ts_pct: number | null;
  fg3_pct: number | null;
  form: ("W" | "L")[];
  injuries: string[] | null;
};

type MatchupGame = {
  id: string;
  away: TeamPayload;
  home: TeamPayload;
  time: string;
  network: string;
  date: string;
  home_score?: number | null;
  away_score?: number | null;
};

type MatchupsResponse = {
  ok: boolean;
  date?: string;
  season?: string;
  games?: MatchupGame[];
  error?: string;
  live?: boolean;
  fetched_at?: string;
};

type StatRow = {
  label: string;
  away: number;
  home: number;
  fmt: (v: number) => string;
  lowerBetter?: boolean;
};

const f1 = (v: number) => v.toFixed(1);
const pct1 = (v: number) => `${v.toFixed(1)}%`;
const signed = (v: number) => (v > 0 ? "+" : "") + v.toFixed(1);

function statRows(away: TeamPayload, home: TeamPayload): StatRow[] {
  const rows: StatRow[] = [];
  const add = (label: string, a: number | null, h: number | null, fmt: (v: number) => string, lowerBetter = false) => {
    if (a !== null && h !== null && Number.isFinite(a) && Number.isFinite(h))
      rows.push({ label, away: a, home: h, fmt, lowerBetter });
  };
  add("Net rating", away.net_rating, home.net_rating, signed);
  add("Offensive rating", away.off_rating, home.off_rating, f1);
  add("Defensive rating", away.def_rating, home.def_rating, f1, true);
  add("Pace", away.pace, home.pace, f1);
  add("3P%", away.fg3_pct, home.fg3_pct, pct1);
  add("TS%", away.ts_pct, home.ts_pct, pct1);
  return rows;
}

function MatchupBars({ rows, aName, bName }: { rows: StatRow[]; aName: string; bName: string }) {
  return (
    <div>
      <div className="divide-y divide-line">
        {rows.map((r) => {
          const max = Math.max(Math.abs(r.away), Math.abs(r.home)) || 1;
          const aLead = r.lowerBetter ? r.away <= r.home : r.away >= r.home;
          return (
            <div key={r.label} className="py-2.5">
              <div className="flex items-baseline justify-between text-[12.5px]">
                <span className="text-ink-2">{r.label}</span>
                <span className="font-mono tabular-nums">
                  <span className="mr-1 text-[10px] uppercase text-ink-3">{aName}</span>
                  <span className={aLead ? "font-semibold text-ink" : "text-ink-3"}>{r.fmt(r.away)}</span>
                  <span className="text-ink-3"> · </span>
                  <span className={!aLead ? "font-semibold text-ink" : "text-ink-3"}>{r.fmt(r.home)}</span>
                  <span className="ml-1 text-[10px] uppercase text-ink-3">{bName}</span>
                  {Math.abs(r.away - r.home) > 0 && (
                    <span className="ml-1.5 text-[10px] font-medium text-accent">Δ {r.fmt(Math.abs(r.away - r.home))}</span>
                  )}
                </span>
              </div>
              <div className="mt-1.5 grid grid-cols-2 gap-1.5" aria-hidden>
                <div className="h-1 overflow-hidden rounded-full bg-field">
                  <div
                    className={`h-full rounded-full ${aLead ? "bg-ink" : "bg-line"}`}
                    style={{ width: `${Math.max(4, (Math.abs(r.away) / max) * 100)}%` }}
                  />
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-field">
                  <div
                    className={`h-full rounded-full ${!aLead ? "bg-ink" : "bg-line"}`}
                    style={{ width: `${Math.max(4, (Math.abs(r.home) / max) * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function InjuryNotes({ game }: { game: MatchupGame }) {
  const sides = [
    { team: game.away, entries: game.away.injuries },
    { team: game.home, entries: game.home.injuries },
  ];
  const listed = sides.filter((s) => s.entries && s.entries.length > 0);
  const unavailable = sides.filter((s) => s.entries === null);
  if (listed.length === 0)
    return (
      <div className="mt-3 border-t border-line pt-3 text-[12.5px] text-ink-3">
        {unavailable.length === sides.length
          ? "Injury report unavailable; no substitute data is shown."
          : "No out or doubtful players listed for either team."}
        {unavailable.length > 0 && unavailable.length < sides.length &&
          ` Injury report unavailable for ${unavailable.map((s) => s.team.abbr).join(", ")}.`}
      </div>
    );
  return (
    <div className="mt-3 divide-y divide-line border-t border-line">
      {listed.map((s) => (
        <div key={s.team.abbr} className="py-2.5">
          <div className="text-[11px] font-medium uppercase tracking-wide text-ink-3">{s.team.abbr} injury report</div>
          <ul className="mt-1 space-y-1">
            {(s.entries ?? []).map((note, i) => (
              <li key={i} className="text-[13px] leading-[1.55] text-ink-2">{note}</li>
            ))}
          </ul>
        </div>
      ))}
      {unavailable.map((s) => (
        <div key={s.team.abbr} className="py-2.5 text-[12.5px] text-ink-3">
          {s.team.abbr} injury report unavailable; no substitute data is shown.
        </div>
      ))}
    </div>
  );
}

function slateStaleness(dateIso: string): string | null {
  if (!dateIso) return null;
  const slate = new Date(dateIso + "T12:00:00Z").getTime();
  if (Number.isNaN(slate)) return null;
  const days = Math.floor((Date.now() - slate) / 86400000);
  if (days <= 2) return null;
  return `warehouse snapshot ${days} days behind today; a historical slate, not tonight's games`;
}

function slateState(m: MatchupGame): "live" | "final" | "upcoming" {
  if (/final/i.test(m.time)) return "final";
  if (/^Q/.test(m.time) || /^Halftime/i.test(m.time)) return "live";
  return "upcoming";
}

function MatchupDetail({ game, onAsk }: { game: MatchupGame; onAsk?: (text: string, context?: import("@/lib/view-context").ViewContext) => void }) {
  const rows = statRows(game.away, game.home);
  return (
    <div
      className="rounded-[10px] bg-surface p-4 shadow-hairline sm:p-5"
      style={{ animation: "fade-up 200ms var(--ease-out-strong) both" }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div className="text-[14px] font-medium text-ink">
          {game.away.name}{" "}
          <span className="font-mono text-[12px] font-normal tabular-nums text-ink-3">{game.away.record}</span>
          <span className="mx-1.5 text-[12px] font-normal text-ink-3">@</span>
          {game.home.name}{" "}
          <span className="font-mono text-[12px] font-normal tabular-nums text-ink-3">{game.home.record}</span>
          {game.away_score != null && game.home_score != null && (
            <span className="ml-2 font-mono text-[13px] tabular-nums text-ink">
              {game.away_score}–{game.home_score}
            </span>
          )}
        </div>
        <div className="shrink-0 text-[12px] text-ink-3">
          {game.time}{game.network ? ` · ${game.network}` : ""}
        </div>
      </div>

      {rows.length > 0 ? (
        <div className="mt-2">
          <MatchupBars rows={rows} aName={game.away.abbr} bName={game.home.abbr} />
        </div>
      ) : (
        <DataState tone="absent" label="Team ratings are unavailable for this matchup." className="mt-3" />
      )}

      <div className="mt-1 space-y-2 border-t border-line pt-3">
        <div className="flex flex-wrap items-center justify-between gap-y-1">
          <span className="text-[12px] text-ink-3">{game.away.abbr} last {game.away.form.length || 10}</span>
          {game.away.form.length > 0 ? <FormChips form={game.away.form} /> : <span className="text-[12px] text-ink-3">–</span>}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-y-1">
          <span className="text-[12px] text-ink-3">{game.home.abbr} last {game.home.form.length || 10}</span>
          {game.home.form.length > 0 ? <FormChips form={game.home.form} /> : <span className="text-[12px] text-ink-3">–</span>}
        </div>
      </div>

      <InjuryNotes game={game} />

      {onAsk && (
        <div className="mt-3 flex justify-end border-t border-line pt-3">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onAsk(
              `Who has the edge in ${game.away.abbr} @ ${game.home.abbr}? Break down the matchup: ratings, form, pace and the injury picture.`,
              {
                kind: "matchup",
                summary: `${game.away.abbr} @ ${game.home.abbr} · ${game.date}`,
                entities: {
                  teams: [game.away.abbr, game.home.abbr],
                  away: { abbr: game.away.abbr, name: game.away.name, record: game.away.record, net_rating: game.away.net_rating, off_rating: game.away.off_rating, def_rating: game.away.def_rating, pace: game.away.pace, form: game.away.form, injuries: game.away.injuries },
                  home: { abbr: game.home.abbr, name: game.home.name, record: game.home.record, net_rating: game.home.net_rating, off_rating: game.home.off_rating, def_rating: game.home.def_rating, pace: game.home.pace, form: game.home.form, injuries: game.home.injuries },
                  date: game.date,
                  time: game.time,
                  ...(game.away_score != null && game.home_score != null ? { score: { away: game.away_score, home: game.home_score } } : {}),
                },
              },
            )}
          >
            Ask Dime about this matchup
          </Button>
        </div>
      )}
    </div>
  );
}

export default function MatchupsView({ onAsk }: { onAsk?: (text: string, context?: import("@/lib/view-context").ViewContext) => void }) {
  const [data, setData] = useState<MatchupsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${BACKEND}${apiPath("/matchups")}`)
      .then((response) => {
        if (!response.ok) throw new Error(`matchups request failed (${response.status})`);
        return response.json();
      })
      .then((value: MatchupsResponse) => {
        if (cancelled) return;
        if (value.ok === false) {
          setError(value.error || "matchups unavailable");
          setData(null);
        } else {
          setData(value);
          setError(null);
          setActiveId((current) => {
            if (current) return current;
            const seeded = initialTeamParam();
            if (seeded) {
              const hit = value.games?.find((g) =>
                g.home?.abbr === seeded || g.away?.abbr === seeded);
              if (hit) return hit.id;
            }
            return value.games?.[0]?.id || "";
          });
        }
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "matchups unavailable");
        setData(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const games = useMemo(() => {
    const list = [...(data?.games ?? [])];
    const rank = (m: MatchupGame) => (slateState(m) === "live" ? 0 : slateState(m) === "upcoming" ? 1 : 2);
    const minutes = (m: MatchupGame) => {
      const hit = m.time.match(/(\d+):(\d+)\s*(AM|PM)/i);
      if (!hit) return 0;
      let h = parseInt(hit[1], 10) % 12;
      if (/pm/i.test(hit[3])) h += 12;
      return h * 60 + parseInt(hit[2], 10);
    };
    list.sort((a, b) => rank(a) - rank(b) || minutes(a) - minutes(b));
    return list;
  }, [data]);
  const active = games.find((m) => m.id === activeId) ?? games[0];

  return (
    <div className="mx-auto w-full max-w-[1120px] px-4 py-6 sm:px-8">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[15px] font-semibold text-ink">
          Matchups
          {data?.season && (
            <span className="ml-2 align-middle font-mono text-[10.5px] font-normal text-ink-3">
              {data.season}
            </span>
          )}
        </h1>
        <span className="text-[12px] tabular-nums text-ink-3">
          {loading ? "" : `${games.length} ${games.length === 1 ? "game" : "games"}`}
        </span>
      </div>

      {loading && (
        <div className="mt-4 grid items-start gap-3 xl:grid-cols-[280px_1fr]" aria-label="loading tonight's slate">
          <div className="grid grid-cols-2 gap-2 xl:grid-cols-1">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[54px] rounded-[10px]" />)}
          </div>
          <Skeleton className="h-[420px] rounded-[10px]" />
        </div>
      )}

      {!loading && error && (
        <div role="alert" className="mt-4 rounded-[10px] border border-line bg-surface p-8 text-center shadow-hairline">
          <DataState tone="error" label={error} detail="No substitute data is shown." />
        </div>
      )}

      {!loading && !error && games.length === 0 && (
        <div className="mt-4 rounded-[10px] bg-surface p-8 text-center text-[13px] text-ink-3 shadow-hairline">
          No games on the current slate.
        </div>
      )}

      {!loading && !error && active && (
        <>
          {data?.date && (
            <p className="mt-1 text-[12px] text-ink-3">
              Slate date {data.date}
              {data?.live && data.fetched_at
                ? ` · live as of ${new Date(data.fetched_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" })} ET`
                : " · schedule from the nightly warehouse refresh"}
              {" · ratings and form from the warehouse, injuries from the latest report."}
            </p>
          )}
          {data?.date && !data?.live && slateStaleness(data.date) && (
            <p className="mt-1 text-[12px] text-orange">
              {slateStaleness(data.date)}
            </p>
          )}
          <div className="mt-4 grid items-start gap-3 xl:grid-cols-[280px_1fr]">
            <div className="grid grid-cols-2 gap-2 xl:grid-cols-1">
              {games.map((m) => {
                const selected = m.id === active.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setActiveId(m.id)}
                    aria-pressed={selected}
                    className={`select-none rounded-[10px] p-3 text-left shadow-hairline transition-[background-color,transform] duration-150 active:scale-[0.98] ${
                      selected ? "bg-hover-2" : "bg-surface hover:bg-hover"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <div className={`text-[13px] font-medium ${selected ? "text-ink" : "text-ink-2"}`}>
                        {m.away.abbr} <span className="font-normal text-ink-3">@</span> {m.home.abbr}
                      </div>
                      {m.away_score != null && m.home_score != null && (
                        <span className={`font-mono text-[12.5px] tabular-nums ${slateState(m) === "live" ? "font-semibold text-ink" : "text-ink-2"}`}>
                          {m.away_score}–{m.home_score}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-1.5 text-[11.5px] tabular-nums text-ink-3">
                      {slateState(m) === "live" && (
                        <span className="inline-block size-1.5 rounded-full bg-accent motion-safe:animate-pulse" aria-label="live" />
                      )}
                      <span className={slateState(m) === "live" ? "font-medium text-accent" : ""}>
                        {m.time}
                      </span>
                      {m.network ? ` · ${m.network}` : ""}
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="xl:sticky xl:top-6">
              <MatchupDetail key={active.id} game={active} onAsk={onAsk} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

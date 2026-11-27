"use client";

import { useEffect, useMemo, useState } from "react";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";
import {
  capSheetFixture,
  capScenarioFixture,
  type CapPlayer,
  type CapSheetResponse,
  type ScenarioMove,
  type ScenarioResponse,
} from "@/lib/capsheet-fixture";

const TEAMS = [
  "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
  "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
  "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
];

function money(value: number | null | undefined): string {
  if (value == null) return "–";
  return `$${(value / 1e6).toFixed(1)}`;
}

function shortSeason(season: string): string {
  return `’${season.slice(5)}`;
}

function useFixture(): boolean {
  return process.env.NODE_ENV === "development"
    && typeof window !== "undefined"
    && new URLSearchParams(window.location.search).get("fixture") === "cap";
}

export default function CapSheetView() {
  const [team, setTeam] = useState("BOS");
  const [sheet, setSheet] = useState<CapSheetResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [includePending, setIncludePending] = useState(false);
  const [moves, setMoves] = useState<ScenarioMove[]>([]);
  const [scenario, setScenario] = useState<ScenarioResponse | null>(null);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [signingAmount, setSigningAmount] = useState("");
  const [signingLabel, setSigningLabel] = useState("");
  const fixture = useFixture();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    if (fixture) {
      setSheet(capSheetFixture);
      setLoading(false);
      return;
    }
    fetch(`${BACKEND}${apiPath(`/cap/sheet?team=${encodeURIComponent(team)}&season=2026-27`)}`)
      .then(async (response) => {
        const body = await response.json().catch(() => null);
        if (!response.ok) throw new Error(body?.error || `cap sheet request failed (${response.status})`);
        return body as CapSheetResponse;
      })
      .then((value) => {
        if (cancelled) return;
        if (!value || value.ok === false) {
          setError(value?.error || "cap sheet unavailable");
          setSheet(null);
        } else {
          setSheet(value);
        }
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "cap sheet unavailable");
        setSheet(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [team, fixture]);

  useEffect(() => {
    if (moves.length === 0) {
      setScenario(null);
      setScenarioError(null);
      return;
    }
    let cancelled = false;
    setEvaluating(true);
    if (fixture) {
      setScenario(capScenarioFixture);
      setEvaluating(false);
      return;
    }
    fetch(`${BACKEND}${apiPath("/cap/scenario")}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ team, season: "2026-27", moves }),
    })
      .then(async (response) => {
        const body = await response.json().catch(() => null);
        if (!response.ok) throw new Error(body?.error || `scenario eval failed (${response.status})`);
        return body as ScenarioResponse;
      })
      .then((value) => {
        if (cancelled) return;
        setScenario(value);
        setScenarioError(null);
        setEvaluating(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setScenario(null);
        setScenarioError(err instanceof Error ? err.message : "scenario eval unavailable");
        setEvaluating(false);
      });
    return () => {
      cancelled = true;
    };
  }, [moves, team, fixture]);

  const seasons = useMemo(() => {
    if (!sheet?.players?.length) return [] as string[];
    return sheet.players[0].years.map((y) => y.season);
  }, [sheet]);

  function optionToggled(player: CapPlayer, season: string) {
    setMoves((current) => {
      const existing = current.findIndex(
        (m) => m.kind === "option_decision" && m.player === player.player && m.season === season,
      );
      if (existing >= 0) return current.filter((_, i) => i !== existing);
      return [...current, { kind: "option_decision", player: player.player, season, exercise: false }];
    });
  }

  function toggledOption(player: CapPlayer, season: string): boolean {
    return moves.some((m) => m.kind === "option_decision" && m.player === player.player && m.season === season);
  }

  function yearTotals(season: string) {
    if (!sheet) return null;
    const base = sheet.totals[season];
    if (!base) return null;
    let committed = base.committed;
    let pending = base.pending_option ?? 0;
    for (const move of moves) {
      if (move.kind === "option_decision" && move.season === season && move.exercise === false) {
        const player = sheet.players.find((p) => p.player === move.player);
        const year = player?.years.find((y) => y.season === season);
        if (year?.salary && year.option === "player") committed -= year.salary;
        if (year?.salary && year.option === "team") pending -= year.salary;
      }
    }
    const payroll = committed + (includePending ? Math.max(0, pending) : 0)
      + base.dead_money + base.cap_holds + base.incomplete_roster_charges;
    return { committed, pending, payroll, base };
  }

  const state = scenario?.state ?? sheet?.state;

  return (
    <div className="mx-auto w-full max-w-[1100px] px-4 py-6 sm:px-8">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-[15px] font-semibold text-ink">Cap sheet</h1>
        {fixture && (
          <span className="rounded-full border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-ink-3">
            fictional fixture
          </span>
        )}
        <div className="ml-auto flex items-center gap-1.5 text-[12.5px]">
          <label className="text-ink-3" htmlFor="cap-team">Team</label>
          <select
            id="cap-team"
            value={team}
            onChange={(e) => { setTeam(e.target.value); setMoves([]); }}
            className="h-7 rounded-[7px] border border-line bg-surface px-1.5 text-[12.5px] text-ink"
          >
            {TEAMS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      {loading && (
        <div className="mt-4 rounded-[10px] bg-surface p-8 text-center text-[13px] text-ink-3 shadow-hairline">
          Loading the cap sheet…
        </div>
      )}

      {!loading && error && (
        <div role="alert" className="mt-4 rounded-[10px] border border-line bg-surface p-8 text-center shadow-hairline">
          <p className="text-[13px] text-red">{error}. No sample data is substituted.</p>
        </div>
      )}

      {!loading && !error && sheet && (
        <div className="mt-4 flex flex-col gap-3 lg:flex-row">
          <div className="min-w-0 flex-1 rounded-[10px] bg-surface shadow-hairline">
            <div className="flex items-center justify-between px-4 pt-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-3">
                {sheet.team} · committed money by season
              </span>
              <label className="flex items-center gap-1.5 text-[11.5px] text-ink-2">
                <input
                  type="checkbox"
                  checked={includePending}
                  onChange={(e) => setIncludePending(e.target.checked)}
                  className="size-3 accent-[var(--accent)]"
                />
                include pending options
              </label>
            </div>
            <div className="overflow-x-auto p-3">
              <table className="w-full min-w-[760px] border-separate border-spacing-0 text-[12px]">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 bg-surface px-2 py-1.5 text-left font-mono text-[10px] font-normal uppercase tracking-wide text-ink-3">
                      player
                    </th>
                    {seasons.map((season) => (
                      <th key={season} className="px-2 py-1.5 text-right font-mono text-[10px] font-normal uppercase tracking-wide text-ink-3">
                        ’{season.slice(2)}
                        {sheet.lines[season]?.projected && (
                          <span className="ml-1 rounded-full border border-line px-1 text-[8.5px] normal-case tracking-normal">proj</span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sheet.players.map((player) => (
                    <tr key={player.player_id} className="group">
                      <td className="sticky left-0 z-10 max-w-[190px] truncate border-t border-line bg-surface px-2 py-1.5">
                        <span className="text-[12.5px] text-ink">{player.player}</span>
                        <span className="ml-1.5 font-mono text-[9.5px] text-ink-3">{player.contract_type}</span>
                      </td>
                      {player.years.map((year) => {
                        const declined = toggledOption(player, year.season);
                        const clickable = !!year.option && year.salary != null;
                        return (
                          <td
                            key={year.season}
                            className={`border-t border-line px-2 py-1.5 text-right font-mono tabular-nums ${
                              !year.guaranteed ? "text-ink-3" : "text-ink-2"
                            } ${declined ? "line-through opacity-40" : ""} ${clickable ? "cursor-pointer hover:bg-field" : ""}`}
                            title={clickable ? `${year.option} option — click to mark ${declined ? "exercised" : "declined"} in the scenario` : undefined}
                            onClick={clickable ? () => optionToggled(player, year.season) : undefined}
                          >
                            {money(year.salary)}
                            {year.option && year.salary != null && (
                              <span className="ml-1 rounded-sm border border-line px-0.5 text-[8.5px] uppercase">{year.option[0]}</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  {(["committed", "payroll"] as const).map((row) => (
                    <tr key={row}>
                      <td className={`sticky left-0 z-10 border-t border-line bg-surface px-2 py-1.5 font-mono text-[10px] uppercase tracking-wide ${row === "payroll" ? "text-ink" : "text-ink-3"}`}>
                        {row}
                      </td>
                      {seasons.map((season) => {
                        const totals = yearTotals(season);
                        const value = row === "payroll" ? totals?.payroll : totals?.committed;
                        const lines = sheet.lines[season];
                        const over = row === "payroll" && value != null && lines && value > lines.apron2;
                        return (
                          <td key={season} className={`border-t border-line px-2 py-1.5 text-right font-mono tabular-nums ${row === "payroll" ? "font-medium text-ink" : "text-ink-2"} ${over ? "text-red" : ""}`}>
                            {money(value)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  {(["cap", "tax", "apron1", "apron2"] as const).map((line) => (
                    <tr key={line}>
                      <td className="sticky left-0 z-10 border-t border-line bg-surface px-2 py-1 font-mono text-[9.5px] uppercase tracking-wide text-ink-3">
                        {line === "apron1" ? "apron 1" : line === "apron2" ? "apron 2" : line}
                      </td>
                      {seasons.map((season) => {
                        const lines = sheet.lines[season];
                        const totals = yearTotals(season);
                        const threshold = lines?.[line];
                        const breached = threshold != null && totals != null && totals.payroll > threshold;
                        return (
                          <td key={season} className={`border-t border-line px-2 py-1 text-right font-mono text-[10.5px] tabular-nums ${breached ? "text-red" : "text-ink-3"}`}>
                            {money(threshold)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tfoot>
              </table>
            </div>
            <p className="px-4 pb-3 font-mono text-[10px] leading-[1.6] text-ink-3">
              {sheet.meta.source} · salaries as of {sheet.meta.salary_date}
              {" · "}p/t = player/team option, click an option cell to toggle it in the scenario
              {" · "}lines beyond 2027-28 projected at a 7% growth assumption
            </p>
          </div>

          <aside className="w-full shrink-0 space-y-3 lg:w-[280px]">
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h3 className="font-mono text-[10px] uppercase tracking-wider text-ink-3">scenario</h3>
              {moves.length === 0 ? (
                <p className="mt-2 text-[12.5px] leading-[1.55] text-ink-3">
                  No moves yet. Toggle an option cell or add a signing below — the grid re-prices instantly.
                </p>
              ) : (
                <div className="mt-2 space-y-1.5">
                  {moves.map((move, i) => (
                    <div key={i} className="flex items-baseline justify-between gap-2 text-[12px]">
                      <span className="text-ink-2">
                        {move.kind === "signing" && `sign ${move.label} (${money(move.amount)})`}
                        {move.kind === "option_decision" && `${move.exercise ? "exercise" : "decline"} ${move.player} ${shortSeason(move.season ?? "")} option`}
                        {move.kind === "waive" && `waive ${move.player}${move.stretch ? " (stretch)" : ""}`}
                        {move.kind === "trade_out" && `trade out ${move.player}`}
                        {move.kind === "trade_in" && `trade in ${move.player}`}
                      </span>
                      <button
                        className="font-mono text-[10px] text-ink-3 underline-offset-2 hover:underline"
                        onClick={() => setMoves((current) => current.filter((_, j) => j !== i))}
                      >
                        remove
                      </button>
                    </div>
                  ))}
                  {evaluating && <p className="text-[11.5px] text-ink-3">evaluating…</p>}
                  {scenarioError && <p className="text-[11.5px] text-red">{scenarioError}</p>}
                  {scenario && (
                    <p className="border-t border-line pt-1.5 font-mono text-[11px] tabular-nums text-ink">
                      payroll after: {money(scenario.pay_after)}
                    </p>
                  )}
                </div>
              )}
              <form
                className="mt-2 flex items-center gap-1.5"
                onSubmit={(e) => {
                  e.preventDefault();
                  const amount = Math.round(parseFloat(signingAmount) * 1e6);
                  if (!signingLabel || !amount || amount <= 0) return;
                  setMoves((current) => [...current, { kind: "signing", label: signingLabel, amount }]);
                  setSigningAmount("");
                  setSigningLabel("");
                }}
              >
                <input
                  value={signingLabel}
                  onChange={(e) => setSigningLabel(e.target.value)}
                  placeholder="free agent"
                  aria-label="signing name"
                  className="h-7 w-0 flex-1 rounded-[7px] border border-line bg-surface px-2 text-[12px] text-ink placeholder:text-ink-3"
                />
                <input
                  value={signingAmount}
                  onChange={(e) => setSigningAmount(e.target.value)}
                  placeholder="$M/yr"
                  aria-label="signing amount in millions"
                  inputMode="decimal"
                  className="h-7 w-[64px] rounded-[7px] border border-line bg-surface px-2 text-[12px] text-ink placeholder:text-ink-3"
                />
                <button type="submit" className="h-7 rounded-[7px] border border-line px-2 text-[11.5px] text-ink-2 hover:bg-field">
                  add
                </button>
              </form>
            </section>

            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h3 className="font-mono text-[10px] uppercase tracking-wider text-ink-3">apron state</h3>
              {state ? (
                <div className="mt-2 space-y-1 text-[12px]">
                  {([
                    ["tax", state.over_tax],
                    ["first apron", state.over_apron1],
                    ["second apron", state.over_apron2],
                  ] as const).map(([label, over]) => (
                    <div key={label} className="flex items-baseline justify-between">
                      <span className="text-ink-2">{label}</span>
                      <span className={`font-mono text-[10.5px] uppercase tracking-wide ${over ? "text-red" : "text-ink-3"}`}>
                        {over ? "over" : "under"}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-[12.5px] text-ink-3">Apron state unavailable.</p>
              )}
            </section>

            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h3 className="font-mono text-[10px] uppercase tracking-wider text-ink-3">restrictions</h3>
              {scenario?.restrictions?.length ? (
                <div className="mt-2 space-y-2">
                  {scenario.restrictions.map((r, i) => (
                    <div key={i}>
                      <div className="flex items-baseline gap-1.5">
                        <span className={`rounded-full border px-1.5 py-px font-mono text-[9px] uppercase tracking-wide ${r.status === "active" ? "border-red text-red" : r.status === "trigger" ? "border-line text-ink" : "border-line text-ink-3"}`}>
                          {r.status}
                        </span>
                        <span className="text-[11px] text-ink-3">{r.threshold}</span>
                      </div>
                      <p className="mt-0.5 text-[12px] leading-[1.55] text-ink-2">{r.rule}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-[12.5px] leading-[1.55] text-ink-3">
                  CBA restriction triggers appear here once a scenario is evaluated — hard caps, frozen picks, matching limits.
                </p>
              )}
              {scenario?.errors?.length ? (
                <div className="mt-2 border-t border-line pt-2">
                  {scenario.errors.map((err, i) => (
                    <p key={i} className="text-[11.5px] text-red">
                      {typeof err === "string" ? err : `move ${err.move ?? i}: ${err.error ?? "invalid move"}`}
                    </p>
                  ))}
                </div>
              ) : null}
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}

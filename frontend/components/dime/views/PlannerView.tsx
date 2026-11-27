"use client";

import { useEffect, useMemo, useState } from "react";
import { loadCapDraft } from "@/lib/cap-draft";
import { fetchProjection, formatMoney, type ProjectionResponse, type ProjectionSeason } from "@/lib/planner";
import type { ScenarioMove } from "@/lib/capsheet-fixture";

const TEAMS = [
  "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
  "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
  "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
];

const BASE_SEASON = "2026-27";

function cellTone(value: number, cap: number): string {
  if (value > cap) return "text-red";
  return "text-ink";
}

function SeasonSummary({ block }: { block: ProjectionSeason }) {
  const over = block.cap_room < 0;
  return (
    <div className="rounded-[10px] bg-surface p-3 shadow-hairline">
      <p className="font-mono text-[11px] text-ink-3">{block.season}{block.lines_projected ? " · projected" : ""}</p>
      <p className="mt-1 text-[15px] font-semibold text-ink">{formatMoney(block.pay_after)}</p>
      <p className={`mt-0.5 text-[12px] font-medium ${over ? "text-red" : "text-ink-2"}`}>
        {over ? `${formatMoney(Math.abs(block.cap_room))} over the cap` : `${formatMoney(block.cap_room)} room`}
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {block.hard_cap && (
          <span className="rounded bg-[var(--accent)]/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent)]">
            hard-capped · {block.hard_cap}
          </span>
        )}
        {block.exception_usage.map(ex => (
          <span key={ex} className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-ink-2">{ex.toUpperCase()}</span>
        ))}
      </div>
      {block.hard_cap_violation && (
        <p className="mt-1.5 text-[11px] leading-[1.5] text-red">{block.hard_cap_violation}</p>
      )}
      {block.ordering_notes.map((note, i) => (
        <p key={i} className="mt-1.5 text-[11px] leading-[1.5] text-amber-700 dark:text-amber-400">{note}</p>
      ))}
    </div>
  );
}

export default function PlannerView() {
  const [team, setTeam] = useState("BOS");
  const [moves, setMoves] = useState<ScenarioMove[]>([]);
  const [projection, setProjection] = useState<ProjectionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    void (async () => {
      const draft = await loadCapDraft(team, BASE_SEASON).catch(() => null);
      const scenarioMoves = draft ?? [];
      const result = await fetchProjection(team, BASE_SEASON, scenarioMoves);
      if (cancelled) return;
      setMoves(scenarioMoves);
      setProjection(result);
      setFailed(result === null);
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [team]);

  const grid = useMemo(() => {
    if (!projection) return null;
    const seasons = projection.seasons;
    const names = new Map<string, string>();
    for (const block of seasons)
      for (const row of block.players)
        if (!names.has(row.player)) names.set(row.player, row.player);
    const rows = [...names.keys()].sort().map(player => ({
      player,
      cells: seasons.map(block => {
        const hit = block.players.find(p => p.player === player);
        return hit ? { salary: hit.salary, option: hit.option } : null;
      }),
    }));
    return { seasons, rows };
  }, [projection]);

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-ink">Cap planner</h1>
          <p className="mt-1 text-[12.5px] text-ink-3">
            Multi-year projection of the working scenario — every number derives server-side from warehouse contract schedules.
          </p>
        </div>
        <select
          aria-label="Team"
          value={team}
          onChange={event => setTeam(event.target.value)}
          className="rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-[13px] text-ink"
        >
          {TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {loading && <p className="mt-8 text-[13px] text-ink-3">Projecting {team} across four seasons…</p>}

      {failed && !loading && (
        <div className="mt-8 rounded-[10px] bg-surface p-6 shadow-hairline">
          <h2 className="text-[15px] font-medium text-ink">The projection didn&apos;t complete</h2>
          <p className="mt-2 max-w-[520px] text-[13px] leading-[1.6] text-ink-2">
            The multi-year evaluation is server-side and may be temporarily unavailable — reload in a moment. Nothing here is ever estimated client-side.
          </p>
        </div>
      )}

      {projection && grid && !loading && (
        <>
          {moves.length === 0 && (
            <p className="mt-6 rounded-[10px] bg-surface px-4 py-2.5 text-[12.5px] text-ink-2 shadow-hairline">
              Baseline projection — no scenario moves yet. Build moves in the cap sheet&apos;s scenario panel and they project here.
            </p>
          )}
          {moves.length > 0 && (
            <p className="mt-6 rounded-[10px] bg-surface px-4 py-2.5 text-[12.5px] text-ink-2 shadow-hairline">
              Projecting the working scenario · {moves.length} move{moves.length === 1 ? "" : "s"}
            </p>
          )}

          {projection.errors.length > 0 && (
            <div className="mt-4 rounded-[10px] border border-red/30 bg-surface px-4 py-3">
              {projection.errors.map((error, i) => (
                <p key={i} className="text-[12.5px] text-red">move {error.move}: {error.error}</p>
              ))}
            </div>
          )}

          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {projection.seasons.map(block => <SeasonSummary key={block.season} block={block} />)}
          </div>

          <div className="mt-6 overflow-x-auto rounded-[10px] bg-surface shadow-hairline">
            <table className="w-full border-collapse text-[12.5px]">
              <thead>
                <tr className="border-b border-line text-left">
                  <th className="px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-ink-3">Player</th>
                  {grid.seasons.map(block => (
                    <th key={block.season} className="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-wide text-ink-3">{block.season}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grid.rows.map(row => (
                  <tr key={row.player} className="border-b border-line/60 last:border-0">
                    <td className="px-4 py-2 font-medium text-ink">{row.player}</td>
                    {row.cells.map((cell, i) => (
                      <td key={i} className={`px-3 py-2 text-right tabular-nums ${cell ? cellTone(cell.salary, grid.seasons[i].lines.cap) : "text-ink-3"}`}>
                        {cell ? formatMoney(cell.salary) : "—"}
                        {cell?.option && <span className="ml-1 text-[10px] text-ink-3">{cell.option === "team" ? "TO" : "PO"}</span>}
                      </td>
                    ))}
                  </tr>
                ))}
                {grid.rows.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-ink-3">No contract data in the warehouse for {team} — the grid is honestly empty rather than zero-filled.</td></tr>
                )}
              </tbody>
              <tfoot>
                <tr className="border-t border-line bg-surface-2/50">
                  <td className="px-4 py-2 text-[11px] font-medium uppercase tracking-wide text-ink-3">Payroll</td>
                  {projection.seasons.map(block => (
                    <td key={block.season} className="px-3 py-2 text-right font-semibold tabular-nums text-ink">{formatMoney(block.pay_after)}</td>
                  ))}
                </tr>
              </tfoot>
            </table>
          </div>

          {projection.seasons.some(block => block.effects.length > 0) && (
            <div className="mt-6 rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Scenario effects by season</h2>
              <div className="mt-3 space-y-3">
                {projection.seasons.filter(block => block.effects.length > 0).map(block => (
                  <div key={block.season}>
                    <p className="font-mono text-[11px] text-ink-3">{block.season}</p>
                    <ul className="mt-1 space-y-1">
                      {block.effects.map((effect, i) => (
                        <li key={i} className="flex flex-wrap items-baseline gap-x-2 text-[12.5px]">
                          <span className="text-ink-2">{effect.detail}</span>
                          <span className={`tabular-nums ${effect.delta >= 0 ? "text-ink" : "text-ink-2"}`}>
                            {effect.delta >= 0 ? "+" : "−"}{formatMoney(Math.abs(effect.delta))}
                          </span>
                          <span className={`rounded px-1 py-0.5 text-[10px] font-medium ${effect.exactness === "exact" ? "bg-surface-2 text-ink-3" : "bg-amber-500/10 text-amber-700 dark:text-amber-400"}`}>
                            {effect.exactness}
                          </span>
                          {effect.disclosure && <span className="w-full text-[11px] leading-[1.5] text-ink-3">{effect.disclosure}</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

          {projection.disclosures.length > 0 && (
            <ul className="mt-5 space-y-1">
              {projection.disclosures.map((disclosure, i) => (
                <li key={i} className="text-[11.5px] leading-[1.55] text-ink-3">{disclosure}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

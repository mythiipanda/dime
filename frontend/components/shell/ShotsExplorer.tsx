"use client";

import { useState } from "react";
import { getDatasetJson, resolveFirstPlayerId } from "../../lib/api";
import { Button } from "../ds/Button";

type Dataset = { rows: Record<string, unknown>[]; source: string; error: string | null };
const empty: Dataset = { rows: [], source: "", error: null };
const cell = (value: unknown) => value == null ? "—" : String(value);

export function ShotsExplorer({ season, initialPlayer = "" }: { season: string; initialPlayer?: string }) {
  const [player, setPlayer] = useState(initialPlayer);
  const [loadedSeason, setLoadedSeason] = useState("");
  const [shots, setShots] = useState<Dataset>(empty);
  const [zones, setZones] = useState<Dataset>(empty);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    setBusy(true); setError(""); setShots(empty); setZones(empty); setLoadedSeason("");
    try {
      const id = /^\d+$/.test(player.trim()) ? player.trim() : await resolveFirstPlayerId(player.trim());
      if (!id) throw new Error("Player not found in the warehouse.");
      const results = await Promise.allSettled([getDatasetJson("shots", { player_id: String(id), season }), getDatasetJson("zone_splits", { player_id: String(id), season })]);
      const unpack = (result: PromiseSettledResult<Awaited<ReturnType<typeof getDatasetJson>>>): Dataset => {
        if (result.status === "rejected") return { ...empty, error: "Could not load this dataset." };
        const value = result.value;
        if (!value.ok) return { ...empty, error: String(value.error || "Dataset unavailable.") };
        const meta = value.meta as Record<string, unknown> | undefined;
        return { rows: Array.isArray(value.data) ? value.data as Record<string, unknown>[] : [], source: String(meta?.table || meta?.source || "Source unavailable"), error: null };
      };
      setShots(unpack(results[0])); setZones(unpack(results[1])); setLoadedSeason(season);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Could not load shots."); }
    finally { setBusy(false); }
  };
  const plotted = shots.rows.filter(row => typeof row.LOC_X === "number" && typeof row.LOC_Y === "number");
  return <section className="mt-7 border-t border-line pt-5" aria-label="Shots and zone splits">
    <h3 className="text-[14px] font-medium">Shots & zone splits</h3>
    <p className="mt-2 text-[12px] text-ink-3">Player-level shots and zone shares, using the existing warehouse-first datasets. All attempt counts are included.</p>
    <form onSubmit={event => { event.preventDefault(); void load(); }} className="my-4 flex flex-wrap items-center gap-2">
      <input aria-label="Player name or id" placeholder="Player name or id" value={player} onChange={event => setPlayer(event.target.value)} className="min-w-0 rounded-lg border border-line bg-field px-3 py-2 text-[12px]" />
      <input aria-label="Shots season" value={season} readOnly title="Select a season above in the table detail" className="w-24 rounded-lg border border-line bg-field px-3 py-2 text-[12px]" />
      <Button type="submit" size="sm" disabled={busy || !player.trim() || !season}>{busy ? "Loading…" : "Load shots"}</Button>
    </form>
    {error && <p role="alert" className="text-[12px] text-red">{error}</p>}
    {loadedSeason && <div className="space-y-4">
      {shots.error ? <p role="status" className="text-[12px] text-ink-3">Shot chart: {shots.error}</p> : <>
        <p className="text-[12px] text-ink-2">{shots.rows.length} shots · filled marks made, outlines missed{plotted.length !== shots.rows.length ? ` · ${shots.rows.length - plotted.length} without coordinates` : ""}</p>
        {plotted.length > 0 && <svg role="img" aria-label="Player shot chart" viewBox="-250 -425 500 475" className="max-h-80 w-full rounded-lg border border-line bg-inset"><g fill="none" stroke="var(--line-strong)" strokeWidth="2"><rect x="-249" y="-424" width="498" height="473" /><circle cx="0" cy="0" r="7.5" /><rect x="-80" y="-137.5" width="160" height="190" /><path d="M-220,47 L-220,-92 A237.5,237.5 0 0 1 220,-92 L220,47" /></g>{plotted.map((row, index) => <circle key={index} cx={Number(row.LOC_X)} cy={-Number(row.LOC_Y)} r="3" stroke="var(--ink-2)" fill={String(row.SHOT_MADE_FLAG) === "1" || String(row.EVENT_TYPE).toLowerCase().startsWith("made") ? "var(--ink)" : "none"}><title>{cell(row.ACTION_TYPE)} · {cell(row.EVENT_TYPE)}</title></circle>)}</svg>}
        <p className="font-mono text-[10px] text-ink-3">Source: {shots.source} · {loadedSeason}</p>
      </>}
      {zones.error ? <p role="status" className="text-[12px] text-ink-3">Zone splits: {zones.error}</p> : <>
        <h4 className="text-[12px] font-medium">Zone splits</h4>
        {!zones.rows.length ? <p className="text-[12px] text-ink-3">No zone rows returned.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-[12px]"><thead className="border-b border-line text-ink-3"><tr>{["Zone", "FGM", "FGA", "FG%", "Share"].map(label => <th key={label} className="py-2 pr-4 font-normal">{label}</th>)}</tr></thead><tbody>{zones.rows.map((row, index) => <tr key={index} className="border-b border-line"><td className="py-2 pr-4">{cell(row.zone ?? row.ZONE)}</td><td>{cell(row.FGM ?? row.fgm)}</td><td>{cell(row.FGA ?? row.fga)}</td><td>{typeof row.FG_PCT === "number" ? `${(row.FG_PCT * 100).toFixed(1)}%` : "—"}</td><td>{typeof (row.share ?? row.SHARE) === "number" ? `${(Number(row.share ?? row.SHARE) * 100).toFixed(1)}%` : "—"}</td></tr>)}</tbody></table></div>}
        <p className="font-mono text-[10px] text-ink-3">Source: {zones.source} · {loadedSeason}</p>
      </>}
    </div>}
  </section>;
}

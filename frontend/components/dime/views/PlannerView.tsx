"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { loadCapDraft, syncCapDraft } from "@/lib/cap-draft";
import { mintObject, shareLink as objectShareLink } from "@/lib/objects-client";
import { MintedLink, copyToClipboard } from "@/components/dime/MintedLink";
import { fetchProjection, formatMoney, type ProjectionResponse, type ProjectionSeason } from "@/lib/planner";
import type { ScenarioMove } from "@/lib/capsheet-fixture";
import { pruneGroups, type MoveGroupsMap } from "@/lib/move-groups";
import ScenarioMoveList from "@/components/dime/ScenarioMoveList";

const TEAMS = [
  "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
  "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
  "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
];

const BASE_SEASON = "2026-27";
const EXCEPTIONS = ["cap_room", "mle", "bae", "minimum", "bird"] as const;

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
        {(block.trade_exceptions ?? []).map((tpe, i) => (
          <span
            key={`tpe-${i}`}
            title={tpe.note}
            className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${tpe.status === "active" ? "bg-surface-2 text-ink-2" : "bg-surface-2/50 text-ink-3 line-through"}`}
          >
            TPE ${(tpe.amount / 1_000_000).toFixed(1)}M · {tpe.exactness.replace(/_/g, " ")}
          </span>
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

function moveLabel(move: ScenarioMove): string {
  if (move.label) return move.label;
  if (move.kind === "waive") return `Waive ${move.player ?? ""}${move.stretch ? " (stretch)" : ""}`.trim();
  if (move.kind === "option_decision") return `${move.exercise ? "Exercise" : "Decline"} option · ${move.player ?? ""}`;
  if (move.kind === "extend") return `Extend ${move.player ?? ""} · ${move.years ?? 1}yr`;
  if (move.kind === "renounce") return `Renounce ${move.player ?? ""} · cap hold released`;
  if (move.kind === "signing") return `Sign ${move.player ?? move.label ?? "free agent"}`;
  if (move.kind === "trade_out") return `Trade out ${move.player ?? ""}`;
  if (move.kind === "trade_in") return `Trade in ${move.player ?? ""}`;
  return move.kind;
}

const actionButton = "rounded px-1.5 py-0.5 text-[10.5px] font-medium text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink";

export default function PlannerView() {
  const [team, setTeam] = useState("BOS");
  const [moves, setMoves] = useState<ScenarioMove[]>([]);
  const [projection, setProjection] = useState<ProjectionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [hydratedTeam, setHydratedTeam] = useState<string | null>(null);
  const [signName, setSignName] = useState("");
  const [signAmount, setSignAmount] = useState("");
  const [signYears, setSignYears] = useState("1");
  const [signException, setSignException] = useState<string>("cap_room");
  const [extendTarget, setExtendTarget] = useState<string | null>(null);
  const [extendAmount, setExtendAmount] = useState("");
  const [extendYears, setExtendYears] = useState("1");
  const [syncFailed, setSyncFailed] = useState(false);
  const [groups, setGroups] = useState<MoveGroupsMap>({});
  const [share, setShare] = useState<{ phase: "idle" } | { phase: "minting" } | { phase: "minted"; link: string; copied: boolean; moves: ScenarioMove[] } | { phase: "error" }>({ phase: "idle" });

  const project = useCallback(async (teamCode: string, scenarioMoves: ScenarioMove[]) => {
    const result = await fetchProjection(teamCode, BASE_SEASON, scenarioMoves);
    setProjection(result);
    setFailed(result === null);
    setLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setFailed(false);
    void (async () => {
      const draft = await loadCapDraft(team, BASE_SEASON).catch(() => null);
      const scenarioMoves = draft?.moves ?? [];
      if (draft?.groups) setGroups(draft.groups);
      if (cancelled) return;
      setMoves(scenarioMoves);
      setHydratedTeam(team);
      await project(team, scenarioMoves);
    })();
    return () => { cancelled = true; };
  }, [team, project]);

  const applyMoves = useCallback((next: ScenarioMove[]) => {
    setMoves(next);
    setSyncFailed(false);
    const liveGroups = pruneGroups(next, groups);
    if (liveGroups !== groups) setGroups(liveGroups);
    void syncCapDraft(team, BASE_SEASON, next, liveGroups).then(ok => setSyncFailed(!ok));
    void project(team, next);
  }, [team, project, groups]);

  const addMove = useCallback((move: ScenarioMove) => {
    applyMoves([...moves, move]);
  }, [moves, applyMoves]);

  function mintShare() {
    if (moves.length === 0 || share.phase === "minting") return;
    setShare({ phase: "minting" });
    mintObject("cap_scenario", `${team} planner scenario · ${BASE_SEASON}`, { team, season: BASE_SEASON, moves, groups: pruneGroups(moves, groups) })
      .then((created) => setShare({ phase: "minted", link: objectShareLink(created.read_token), copied: false, moves }))
      .catch(() => setShare({ phase: "error" }));
  }

  function copyShare(link: string) {
    copyToClipboard(link, () => setShare((current) => current.phase === "minted" ? { ...current, copied: true } : current));
  }

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

  const editing = hydratedTeam === team;

  const submitSigning = () => {
    const amount = Number(signAmount) * 1_000_000;
    if (!signName.trim() || !Number.isFinite(amount) || amount <= 0) return;
    const years = Math.max(1, Math.min(4, Number(signYears) || 1));
    addMove({
      kind: "signing",
      label: signName.trim(),
      amount,
      years,
      exception: signException as ScenarioMove["exception"],
    });
    setSignName("");
    setSignAmount("");
    setSignYears("1");
  };

  const submitExtension = () => {
    if (!extendTarget) return;
    const amount = Number(extendAmount) * 1_000_000;
    if (!Number.isFinite(amount) || amount <= 0) return;
    const years = Math.max(1, Math.min(4, Number(extendYears) || 1));
    addMove({ kind: "extend", player: extendTarget, first_year_amount: amount, years });
    setExtendTarget(null);
    setExtendAmount("");
    setExtendYears("1");
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-ink">Cap planner</h1>
          <p className="mt-1 text-[12.5px] text-ink-3">
            Multi-year projection of the working scenario. Every number derives server-side from warehouse contract schedules.
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
            The multi-year evaluation is server-side and may be temporarily unavailable. Reload in a moment. Nothing here is ever estimated client-side.
          </p>
        </div>
      )}

      {projection && grid && !loading && (
        <>
          {moves.length === 0 && (
            <p className="mt-6 rounded-[10px] bg-surface px-4 py-2.5 text-[12.5px] text-ink-2 shadow-hairline">
              Baseline projection. No scenario moves yet. Add moves here or in the cap sheet; they write through to the shared draft.
            </p>
          )}

          {syncFailed && (
            <div className="mt-4 rounded-[10px] border border-red/30 bg-surface px-4 py-3">
              <p className="text-[12.5px] text-red">The moves below didn&apos;t persist to the shared draft. They project here but won&apos;t survive reload or reach the cap sheet. Retry by removing and re-adding the last move.</p>
            </div>
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
                  {editing && <th className="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-wide text-ink-3">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {grid.rows.map(row => (
                  <tr key={row.player} className="group border-b border-line/60 last:border-0">
                    <td className="px-4 py-2 font-medium text-ink">{row.player}</td>
                    {row.cells.map((cell, i) => (
                      <td key={i} className={`px-3 py-2 text-right tabular-nums ${cell ? cellTone(cell.salary, grid.seasons[i].lines.cap) : "text-ink-3"}`}>
                        {cell ? formatMoney(cell.salary) : "—"}
                        {cell?.option && <span className="ml-1 text-[10px] text-ink-3">{cell.option === "team" ? "TO" : "PO"}</span>}
                      </td>
                    ))}
                    {editing && (
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button type="button" className={actionButton} onClick={() => addMove({ kind: "waive", player: row.player })}>waive</button>
                        <button type="button" className={actionButton} onClick={() => addMove({ kind: "waive", player: row.player, stretch: true })}>stretch</button>
                        {row.cells[0]?.option && (
                          <button type="button" className={actionButton} onClick={() => addMove({ kind: "option_decision", player: row.player, exercise: false })}>decline opt</button>
                        )}
                        <button
                          type="button"
                          className={actionButton}
                          onClick={() => { setExtendTarget(extendTarget === row.player ? null : row.player); setExtendAmount(""); setExtendYears("1"); }}
                        >extend</button>
                      </td>
                    )}
                  </tr>
                ))}
                {grid.rows.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-6 text-center text-ink-3">No contract data in the warehouse for {team}; the grid is honestly empty rather than zero-filled.</td></tr>
                )}
              </tbody>
              <tfoot>
                <tr className="border-t border-line bg-surface-2/50">
                  <td className="px-4 py-2 text-[11px] font-medium uppercase tracking-wide text-ink-3">Payroll</td>
                  {projection.seasons.map(block => (
                    <td key={block.season} className="px-3 py-2 text-right font-semibold tabular-nums text-ink">{formatMoney(block.pay_after)}</td>
                  ))}
                  {editing && <td />}
                </tr>
              </tfoot>
            </table>
          </div>

          {extendTarget && (
            <div className="mt-4 flex flex-wrap items-end gap-2 rounded-[10px] bg-surface p-4 shadow-hairline">
              <p className="w-full text-[12.5px] font-medium text-ink">Extend {extendTarget}</p>
              <label className="text-[11px] text-ink-3">
                First-year salary ($M)
                <input
                  value={extendAmount}
                  onChange={event => setExtendAmount(event.target.value)}
                  inputMode="decimal"
                  placeholder="30"
                  className="mt-1 block w-24 rounded-[6px] border border-line bg-surface px-2 py-1 text-[12.5px] text-ink"
                />
              </label>
              <label className="text-[11px] text-ink-3">
                Years
                <input
                  value={extendYears}
                  onChange={event => setExtendYears(event.target.value)}
                  inputMode="numeric"
                  className="mt-1 block w-14 rounded-[6px] border border-line bg-surface px-2 py-1 text-[12.5px] text-ink"
                />
              </label>
              <button type="button" onClick={submitExtension} className="rounded-[6px] bg-[var(--accent)] px-3 py-1.5 text-[12px] font-medium text-white">Add extension</button>
              <button type="button" onClick={() => setExtendTarget(null)} className="rounded-[6px] px-3 py-1.5 text-[12px] font-medium text-ink-3 hover:text-ink">Cancel</button>
              <p className="w-full text-[11px] leading-[1.5] text-ink-3">Flat structure, starts the season after the contract&apos;s last year; labeled unvalidated against exact CBA extension rules.</p>
            </div>
          )}

          {editing && (
            <div className="mt-4 rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Sign a free agent</h2>
              <div className="mt-2 flex flex-wrap items-end gap-2">
                <label className="text-[11px] text-ink-3">
                  Player
                  <input
                    value={signName}
                    onChange={event => setSignName(event.target.value)}
                    placeholder="Free agent name"
                    className="mt-1 block w-44 rounded-[6px] border border-line bg-surface px-2 py-1 text-[12.5px] text-ink"
                  />
                </label>
                <label className="text-[11px] text-ink-3">
                  Salary ($M/yr)
                  <input
                    value={signAmount}
                    onChange={event => setSignAmount(event.target.value)}
                    inputMode="decimal"
                    placeholder="12"
                    className="mt-1 block w-24 rounded-[6px] border border-line bg-surface px-2 py-1 text-[12.5px] text-ink"
                  />
                </label>
                <label className="text-[11px] text-ink-3">
                  Years
                  <input
                    value={signYears}
                    onChange={event => setSignYears(event.target.value)}
                    inputMode="numeric"
                    className="mt-1 block w-14 rounded-[6px] border border-line bg-surface px-2 py-1 text-[12.5px] text-ink"
                  />
                </label>
                <label className="text-[11px] text-ink-3">
                  Exception
                  <select
                    value={signException}
                    onChange={event => setSignException(event.target.value)}
                    className="mt-1 block rounded-[6px] border border-line bg-surface px-2 py-1 text-[12.5px] text-ink"
                  >
                    {EXCEPTIONS.map(ex => <option key={ex} value={ex}>{ex.replace("_", " ").toUpperCase()}</option>)}
                  </select>
                </label>
                <button type="button" onClick={submitSigning} className="rounded-[6px] bg-[var(--accent)] px-3 py-1.5 text-[12px] font-medium text-white">Add signing</button>
              </div>
            </div>
          )}

          {moves.length > 0 && (
            <div className="mt-4 rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Scenario moves · {moves.length}</h2>
              <div className="mt-2 space-y-1.5">
                <ScenarioMoveList
                  moves={moves}
                  groups={groups}
                  labels={{ describe: moveLabel }}
                  onChange={applyMoves}
                  reorderable={editing}
                  numbered
                />
              </div>
              <p className="mt-2 text-[11px] leading-[1.5] text-ink-3">Order matters: a signing that fits after a trade may be flagged before it. Moves write through to the shared cap-sheet draft.</p>
              {editing && (share.phase !== "minted" || JSON.stringify(moves) !== JSON.stringify(share.moves)) && (
                <button
                  type="button"
                  className="mt-3 h-7 rounded-[7px] border border-line px-2 text-[11.5px] text-ink-2 hover:bg-field disabled:opacity-50"
                  onClick={mintShare}
                  disabled={share.phase === "minting"}
                >
                  {share.phase === "minting" ? "Sharing…" : share.phase === "minted" ? "Share updated" : "Share scenario"}
                </button>
              )}
              {share.phase === "minted" && (
                <div className="mt-3">
                  <MintedLink
                    link={share.link}
                    copied={share.copied}
                    onCopy={copyShare}
                    note={
                      <>
                        Snapshot link minted. Recipients see those moves evaluated live.
                        {JSON.stringify(moves) !== JSON.stringify(share.moves)
                          ? " The scenario has changed since this link was minted. The link still holds the earlier moves; use Share updated for a new link."
                          : " Editing the scenario here won't change it; share again for a new link."}
                      </>
                    }
                  />
                </div>
              )}
              {share.phase === "error" && (
                <p className="mt-2 text-[11px] leading-[1.45] text-red">
                  The scenario couldn&apos;t be shared. The backend didn&apos;t accept the mint. Your moves are untouched; try again.
                </p>
              )}
            </div>
          )}

          <div className="mt-6 rounded-[10px] bg-surface p-4 shadow-hairline">
            <h2 className="text-[13px] font-semibold text-ink">Exceptions</h2>
            <p className="mt-1 text-[11px] leading-[1.5] text-ink-3">Usage reflects scenario moves only; league-wide exception consumption isn&apos;t derivable from seeded transactions. MLE/BAE usage hard-caps at the first apron.</p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full border-collapse text-[12.5px]">
                <thead>
                  <tr className="border-b border-line text-left">
                    <th className="py-1.5 pr-3 text-[11px] font-medium uppercase tracking-wide text-ink-3">Exception</th>
                    {projection.seasons.map(block => (
                      <th key={block.season} className="px-3 py-1.5 text-right text-[11px] font-medium uppercase tracking-wide text-ink-3">{block.season}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {["mle", "bae", "room"].map(name => (
                    <tr key={name} className="border-b border-line/60 last:border-0">
                      <td className="py-2 pr-3 font-medium text-ink">{name === "mle" ? "Non-taxpayer MLE" : name === "bae" ? "Bi-annual" : "Room"}</td>
                      {projection.seasons.map(block => {
                        const row = (block.exceptions ?? []).find(e => e.exception === name);
                        if (!row) return <td key={block.season} className="px-3 py-2 text-right text-ink-3">—</td>;
                        return (
                          <td key={block.season} className="px-3 py-2 text-right">
                            <span className={`tabular-nums ${row.used > 0 ? "text-ink" : "text-ink-2"}`}>
                              {row.used > 0 ? `${formatMoney(row.remaining)} left` : formatMoney(row.amount)}
                            </span>
                            {row.used > 0 && <span className="ml-1 text-[10px] text-ink-3">of {formatMoney(row.amount)}</span>}
                            {row.hard_caps && <span className="ml-1 rounded bg-[var(--accent)]/10 px-1 py-0.5 text-[10px] font-medium text-[var(--accent)]">hard-caps</span>}
                            {row.exceeds != null && <span className="ml-1 rounded bg-red/10 px-1 py-0.5 text-[10px] font-medium text-red">exceeds exception</span>}
                            {row.unavailable && <span className="ml-1 rounded bg-red/10 px-1 py-0.5 text-[10px] font-medium text-red">over-apron</span>}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {editing && projection.seasons.some(block => (block.cap_hold_details ?? []).length > 0) && (
            <div className="mt-4 rounded-[10px] bg-surface p-4 shadow-hairline">
              <h2 className="text-[13px] font-semibold text-ink">Cap holds</h2>
              <p className="mt-1 text-[11px] leading-[1.5] text-ink-3">Expired contracts with retained rights count against the cap until renounced or re-signed. Renouncing frees the room but forfeits the rights.</p>
              <div className="mt-2 space-y-2">
                {projection.seasons.filter(block => (block.cap_hold_details ?? []).length > 0).map(block => (
                  <div key={block.season}>
                    <p className="font-mono text-[11px] text-ink-3">
                      {block.season} · {block.cap_holds ? formatMoney(block.cap_holds) : "amounts unpriced"}
                      {block.cap_holds_exactness && block.cap_holds_exactness !== "exact" && (
                        <span className="ml-1.5 rounded bg-amber-500/10 px-1 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-400">{block.cap_holds_exactness}</span>
                      )}
                    </p>
                    <ul className="mt-1 space-y-1">
                      {(block.cap_hold_details ?? []).map((hold, i) => (
                        <li key={i} className="flex items-center justify-between gap-3 text-[12.5px]">
                          <span className="text-ink-2">{hold.player} <span className="text-ink-3">· {hold.fa_type || "rights held"}</span></span>
                          <span className="flex items-center gap-2">
                            <span className="tabular-nums text-ink">{hold.amount != null ? formatMoney(hold.amount) : "unpriced"}</span>
                            {hold.amount != null && (
                              <button type="button" className={actionButton} onClick={() => addMove({ kind: "renounce", player: hold.player, season: block.season })}>renounce</button>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

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

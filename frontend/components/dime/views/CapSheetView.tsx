"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Skeleton } from "@/components/ds/Skeleton";
import { apiPath } from "@/lib/api";
import { initialTeamParam } from "@/lib/open-in-view";
import { DataState } from "@/components/ds/DataState";
import { listBoards, pinArtifact, saveBoard } from "@/lib/boards";
import { mintObject, shareLink as objectShareLink } from "@/lib/objects-client";
import { consumeCapHandoff } from "@/lib/cap-handoff";
import { syncCapDraft, loadCapDraft } from "@/lib/cap-draft";
import { toast } from "sonner";
import { pruneGroups, type MoveGroupsMap } from "@/lib/move-groups";
import ScenarioMoveList from "@/components/dime/ScenarioMoveList";
import { MintedLink, copyToClipboard } from "@/components/dime/MintedLink";
import { BACKEND } from "@/lib/chat";
import {
  capSheetFixture,
  capScenarioFixture,
  describeScenarioMove,
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

const DEFAULT_SCENARIO_SEASON = "2026-27";

function scenarioSeasonForMoves(moves: ScenarioMove[]): string | null {
  const optionMoves = moves.filter((move) => move.kind === "option_decision");
  if (optionMoves.length === 0 || optionMoves.length !== moves.length) return DEFAULT_SCENARIO_SEASON;
  const seasons = new Set(optionMoves.map((move) => move.season || DEFAULT_SCENARIO_SEASON));
  return seasons.size === 1 ? Array.from(seasons)[0] : null;
}

export default function CapSheetView({ onAsk, seed }: { onAsk?: (text: string, context?: import("@/lib/view-context").ViewContext) => void; seed?: import("@/lib/workbench-navigation").CapScenarioSeed | null }) {
  const [team, setTeam] = useState(() => initialTeamParam() ?? "BOS");
  const [sheet, setSheet] = useState<CapSheetResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [includePending, setIncludePending] = useState(false);
  const [handoffNote, setHandoffNote] = useState<string | null>(null);
  const [moves, setMoves] = useState<ScenarioMove[]>([]);
  const [groups, setGroups] = useState<MoveGroupsMap>({});
  const [scenario, setScenario] = useState<ScenarioResponse | null>(null);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [saveState, setSaveState] = useState<string | null>(null);
  const [share, setShare] = useState<{ phase: "idle" } | { phase: "minting" } | { phase: "minted"; link: string; copied: boolean; moves: ScenarioMove[] } | { phase: "error" }>({ phase: "idle" });
  const [signingAmount, setSigningAmount] = useState("");
  const [signingLabel, setSigningLabel] = useState("");
  const fixture = useFixture();
  const scenarioSeason = useMemo(() => scenarioSeasonForMoves(moves), [moves]);

  useEffect(() => {
    if (!seed?.team) return;
    setTeam(seed.team);
    setMoves(seed.moves as ScenarioMove[]);
    setGroups({});
    setHandoffNote("Opened from a chat artifact. The scenario is a one-way copy: edits here don't affect the artifact.");
  }, [seed]);

  const handoffConsumed = useRef(false);
  useEffect(() => {
    const handoff = consumeCapHandoff();
    if (!handoff) return;
    handoffConsumed.current = true;
    setTeam(handoff.team);
    setMoves(handoff.moves);
    if (handoff.groups) setGroups(handoff.groups);
    setHandoffNote(handoff.source ? `Imported from the trade machine (${handoff.source}). The trade is a one-way copy: edits here don't affect it.` : null);
  }, []);

  const draftKey = `${team}:${scenarioSeason ?? DEFAULT_SCENARIO_SEASON}`;
  const settledDrafts = useRef<Set<string>>(new Set());
  const [draftSettled, setDraftSettled] = useState(0);
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("team") === team) return;
    url.searchParams.set("team", team);
    window.history.replaceState({}, "", url);
  }, [team]);

  useEffect(() => {
    if (handoffConsumed.current) {
      settledDrafts.current.add(draftKey);
      setDraftSettled((count) => count + 1);
      return;
    }
    let active = true;
    loadCapDraft(team, scenarioSeason ?? DEFAULT_SCENARIO_SEASON).then((restored) => {
      if (!active) return;
      settledDrafts.current.add(draftKey);
      setDraftSettled((count) => count + 1);
      if (!restored) return;
      if (restored.groups) setGroups(restored.groups);
      setMoves((current) => current.length === 0 ? restored.moves : current);
    });
    return () => { active = false; };
  }, [draftKey, team, scenarioSeason]);

  useEffect(() => {
    if (!settledDrafts.current.has(draftKey)) return;
    const currentSeason = scenarioSeason ?? DEFAULT_SCENARIO_SEASON;
    const timer = setTimeout(() => {
      void syncCapDraft(team, currentSeason, moves, pruneGroups(moves, groups)).then((ok) => {
        if (!ok) {
          toast.error("Scenario changes aren't saving", {
            id: `cap-sync-${draftKey}`,
            description: "The working scenario could not be written to the object store. It retries as you keep editing.",
          });
        }
      });
    }, 800);
    return () => clearTimeout(timer);
  }, [draftKey, draftSettled, team, scenarioSeason, moves, groups]);
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
    if (scenarioSeason === null) {
      setScenario(null);
      setScenarioError("Option decisions span multiple seasons. Evaluate one season at a time.");
      setEvaluating(false);
      return;
    }
    let cancelled = false;
    setEvaluating(true);
    if (fixture) {
      setScenario({ ...capScenarioFixture, season: scenarioSeason });
      setEvaluating(false);
      return;
    }
    fetch(`${BACKEND}${apiPath("/cap/scenario")}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ team, season: scenarioSeason, moves }),
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
  }, [moves, team, fixture, scenarioSeason]);

  const seasons = useMemo(() => {
    if (!sheet?.players?.length) return [] as string[];
    const all = sheet.players[0].years.map((y) => y.season);
    const current = sheet.season ?? all[0];
    return all.filter((season) => season >= current);
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

  function removedFromSeason(player: CapPlayer): string | null {
    const removal = moves
      .filter((m) => (m.kind === "waive" || m.kind === "trade_out") && m.player === player.player)
      .map((m) => m.season ?? seasons[0])
      .filter((s): s is string => typeof s === "string")
      .sort()[0];
    return removal ?? null;
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

  function scenarioContext(): import("@/lib/view-context").ViewContext {
    const evaluationSeason = scenario?.season ?? scenarioSeason ?? DEFAULT_SCENARIO_SEASON;
    return {
      kind: "cap_scenario",
      summary: `${sheet?.team ?? team} cap scenario · ${evaluationSeason} · ${moves.length} move${moves.length === 1 ? "" : "s"}`,
      entities: {
        team: sheet?.team ?? team,
        season: evaluationSeason,
        moves,
        ...(scenario ? { payroll_after: scenario.pay_after } : {}),
      },
    };
  }

  function serializeScenario(): string {
    const lines = moves.map((move) => {
      if (move.kind === "signing") return `- sign ${move.label} at ${money(move.amount)}/yr`;
      if (move.kind === "option_decision") return `- ${move.exercise ? "exercise" : "decline"} ${move.player}'s ${move.season} ${move.exercise ? "option" : "option"}`;
      if (move.kind === "waive") return `- waive ${move.player}${move.stretch ? " using the stretch provision" : ""}`;
      if (move.kind === "trade_out") return `- trade out ${move.player}`;
      return `- trade in ${move.player}`;
    });
    const evaluationSeason = scenario?.season ?? scenarioSeason ?? "mixed seasons";
    return `Cap scenario for ${sheet?.team ?? team} (${evaluationSeason}):\n${lines.join("\n")}\nPost-scenario payroll: ${scenario ? money(scenario.pay_after) : "not evaluated"}. Analyze this scenario: what restrictions trigger, what is the apron exposure, and what are the basketball consequences?`;
  }

  function mintShare() {
    if (moves.length === 0 || share.phase === "minting") return;
    setShare({ phase: "minting" });
    mintObject("cap_scenario", `${team} scenario · ${scenarioSeason ?? DEFAULT_SCENARIO_SEASON}`, {
      team,
      season: scenarioSeason ?? DEFAULT_SCENARIO_SEASON,
      moves,
    })
      .then((created) => {
        setShare({ phase: "minted", link: objectShareLink(created.read_token), copied: false, moves });
      })
      .catch(() => setShare({ phase: "error" }));
  }
  function copyShareLink(link: string) {
    copyToClipboard(link, () => setShare((current) => current.phase === "minted" ? { ...current, copied: true } : current));
  }
  function saveToBoard() {
    const boards = listBoards();
    const board = boards[0];
    if (!board) {
      setSaveState("no board exists yet; create one in Boards first");
      return;
    }
    const artifact = {
      kind: "cap_scenario",
      title: `${sheet?.team ?? team} cap scenario · ${moves.length} move${moves.length === 1 ? "" : "s"}`,
      team: sheet?.team ?? team,
      season: scenario?.season ?? scenarioSeason ?? sheet?.season ?? DEFAULT_SCENARIO_SEASON,
      moves,
      pay_after: scenario?.pay_after ?? null,
      pinned_from: "cap_sheet_view",
    };
    const next = pinArtifact(board, artifact as never);
    saveBoard(next);
    setSaveState(`saved to "${board.title}"`);
  }

  function loadFromBoard() {
    const boards = listBoards();
    for (const board of boards) {
      const pin = (board.pins ?? []).filter((p) => (p.artifact as { kind?: string }).kind === "cap_scenario").pop();
      if (pin) {
        const artifact = pin.artifact as { team?: string; moves?: ScenarioMove[] };
        if (artifact.team && Array.isArray(artifact.moves)) {
          setTeam(artifact.team);
          setMoves(artifact.moves);
          setSaveState(`loaded scenario from "${board.title}"`);
          return;
        }
      }
    }
    setSaveState("no saved cap scenario found on any board");
  }

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
        <div className="mt-4 flex flex-col gap-3 lg:flex-row" aria-label="loading the cap sheet">
          <div className="min-w-0 flex-1 rounded-[10px] bg-surface p-4 shadow-hairline">
            <Skeleton className="h-4 w-52" />
            <div className="mt-4 space-y-2.5">
              {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-[22px]" />)}
            </div>
          </div>
          <div className="w-full shrink-0 space-y-3 lg:w-[300px]">
            <Skeleton className="h-[150px] rounded-[10px]" />
            <Skeleton className="h-[110px] rounded-[10px]" />
          </div>
        </div>
      )}

      {!loading && error && (
        <div role="alert" className="mt-4 rounded-[10px] border border-line bg-surface p-8 text-center shadow-hairline">
          <DataState tone="error" label={error} detail="No substitute data is shown." />
        </div>
      )}

      {!loading && !error && sheet && (
        <div key={team} className="mt-4 flex flex-col gap-3 lg:flex-row" style={{ animation: "fade-up 180ms var(--ease-out-strong) both" }}>
          <div className="min-w-0 flex-1 rounded-[10px] bg-surface shadow-hairline">
            <div className="flex items-center justify-between px-4 pt-3">
              <span className="text-[13px] font-semibold text-ink">
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
              <table className="w-full min-w-[640px] border-separate border-spacing-0 text-[12px]">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 bg-surface px-2 py-1.5 text-left font-mono text-[10px] font-normal uppercase tracking-wide text-ink-3">
                      player
                    </th>
                    {seasons.map((season) => (
                      <th key={season} className="px-2 py-1.5 text-right font-mono text-[10px] font-normal uppercase tracking-wide text-ink-3">
                        ’{season.slice(2)}
                        {sheet.lines[season]?.projected && (
                          <span className="ml-1 text-[9px] text-ink-3">proj</span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sheet.players.map((player) => (
                    <tr key={player.player_id ?? `unsigned-${player.player}`} className="group">
                      <td className="sticky left-0 z-10 max-w-[220px] border-t border-line bg-surface px-2 py-1.5 leading-snug">
                        <span className="text-[12.5px] text-ink">{player.player}</span>
                        <span className="ml-1.5 font-mono text-[9.5px] text-ink-3">{player.contract_type}</span>
                      </td>
                      {seasons.map((season) => {
                        const year = player.years.find((y) => y.season === season);
                        if (!year) return <td key={season} className="border-t border-line px-2 py-1.5 text-right font-mono tabular-nums text-ink-3">–</td>;
                        const declined = toggledOption(player, year.season);
                        const removal = removedFromSeason(player);
                        const removed = removal != null && year.season >= removal;
                        const clickable = !!year.option && year.salary != null && !removed;
                        return (
                          <td
                            key={season}
                            className={`border-t border-line px-2 py-1.5 text-right font-mono tabular-nums ${
                              !year.guaranteed ? "text-ink-3" : "text-ink-2"
                            } ${declined || removed ? "line-through opacity-40" : ""} ${clickable ? "p-0" : ""}`}
                            title={removed ? `${player.player} is removed by a scenario move in ${removal}; this season and forward are struck` : undefined}
                          >
                            {clickable ? (
                              <button
                                type="button"
                                className="block w-full cursor-pointer px-2 py-1.5 text-right font-mono tabular-nums transition-colors hover:bg-field"
                                title={`${year.option} option: activate to mark ${declined ? "exercised" : "declined"} in the scenario`}
                                aria-pressed={declined}
                                onClick={() => optionToggled(player, year.season)}
                              >
                                {money(year.salary)}
                                <span className="ml-1 text-[9px] uppercase text-ink-3">{year.option?.[0]}</span>
                              </button>
                            ) : (
                              <>
                                {money(year.salary)}
                                {year.option && year.salary != null && (
                                  <span className="ml-1 rounded-sm border border-line px-0.5 text-[8.5px] uppercase">{year.option[0]}</span>
                                )}
                              </>
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

          <aside className="w-full shrink-0 space-y-3 lg:sticky lg:top-6 lg:w-[280px] lg:self-start">
            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h3 className="text-[13px] font-semibold text-ink">Scenario</h3>
              {moves.length > 0 && (
                <p className="mt-1 text-[11px] text-ink-2">evaluation season {scenarioSeason ?? "mixed"}</p>
              )}
              {moves.length === 0 ? (
                <p className="mt-2 text-[12.5px] leading-[1.55] text-ink-3">
                  No moves yet. Toggle an option cell or add a signing below. The grid re-prices instantly.
                </p>
              ) : (
                <div className="mt-2 space-y-1.5">
                  <ScenarioMoveList
                    moves={moves}
                    groups={groups}
                    labels={{
                      describe: describeScenarioMove,
                      waiverBasis: (move) => move.kind === "waive"
                        ? scenario?.steps.find((step) => step.kind === "waive" && step.player === move.player)?.estimate_basis
                        : undefined,
                    }}
                    onChange={setMoves}
                  />
                  {evaluating && <p className="text-[11.5px] text-ink-3">evaluating…</p>}
                  {handoffNote && <p className="text-[11px] leading-[1.45] text-ink-3">{handoffNote}</p>}
                  {scenarioError && <p className="text-[11.5px] text-red">{scenarioError}</p>}
                  {scenario && (
                    <p className="border-t border-line pt-1.5 font-mono text-[11px] tabular-nums text-ink">
                      payroll after: {money(scenario.pay_after)}M
                    </p>
                  )}
                </div>
              )}
              {moves.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-line pt-2">
                  {onAsk && (
                    <button
                      className="h-7 rounded-[7px] border border-line px-2 text-[11.5px] text-ink-2 hover:bg-field"
                      onClick={() => onAsk(serializeScenario(), scenarioContext())}
                    >
                      Ask about this scenario
                    </button>
                  )}
                  <button
                    className="h-7 rounded-[7px] border border-line px-2 text-[11.5px] text-ink-2 hover:bg-field"
                    onClick={saveToBoard}
                  >
                    Save to board
                  </button>
                  {(share.phase !== "minted" || JSON.stringify(moves) !== JSON.stringify(share.moves)) && (
                    <button
                      className="h-7 rounded-[7px] border border-line px-2 text-[11.5px] text-ink-2 hover:bg-field disabled:opacity-50"
                      onClick={mintShare}
                      disabled={share.phase === "minting"}
                    >
                      {share.phase === "minting" ? "Sharing…" : share.phase === "minted" ? "Share updated" : "Share"}
                    </button>
                  )}
                  <button
                    className="h-7 rounded-[7px] border border-line px-2 text-[11.5px] text-ink-2 hover:bg-field"
                    onClick={loadFromBoard}
                  >
                    Load saved
                  </button>
                  {saveState && <span className="w-full text-[11px] text-ink-2">{saveState}</span>}
                  {share.phase === "minted" && (
                    <MintedLink
                      link={share.link}
                      copied={share.copied}
                      onCopy={copyShareLink}
                      note={
                        <>
                          Snapshot link minted. Recipients see those moves evaluated live.
                          {JSON.stringify(moves) !== JSON.stringify(share.moves)
                            ? " The scenario has changed since this link was minted; the link still holds the earlier moves; use Share updated for a new link."
                            : " Editing the scenario here won't change it; share again for a new link."}
                        </>
                      }
                    />
                  )}
                  {share.phase === "error" && (
                    <p className="w-full text-[11px] leading-[1.45] text-red">
                      The scenario couldn't be shared. The backend didn't accept the mint. Your moves are untouched; try again.
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
              <h3 className="text-[13px] font-semibold text-ink">Apron state</h3>
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
                <DataState tone="absent" label="Apron state unavailable." className="mt-2" />
              )}
            </section>

            <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
              <h3 className="text-[13px] font-semibold text-ink">Restrictions</h3>
              {scenario?.restrictions?.length ? (
                <div className="mt-2 space-y-2">
                  {scenario.restrictions.map((r, i) => (
                    <div key={i}>
                      <div className="flex items-baseline gap-1.5">
                        <span className={`text-[10px] font-medium uppercase tracking-wide ${r.status === "active" ? "text-red" : r.status === "trigger" ? "text-ink" : "text-ink-3"}`}>
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
                  CBA restriction triggers appear here once a scenario is evaluated: hard caps, frozen picks, matching limits.
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

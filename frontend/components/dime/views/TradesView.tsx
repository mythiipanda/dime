"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";
import type { DimeArtifact } from "@/lib/dime-stream";
import { nbaTeams } from "../../../lib/dime-data-trades";
import PinButton from "../PinButton";

const money = (v: number) => `$${v.toFixed(1)}M`;

const TRADE_SEASON = "2026-27";

type RosterPlayer = { name: string; salary: number };
type Pick = { year: number; round: number; orig: string; protection: string | null; conditional: boolean; summary: string };
type Assets =
  | { state: "loading" }
  | { state: "ready"; players: RosterPlayer[]; picks: Pick[]; source: string; season: string }
  | { state: "error"; error: string };

type TradeSideRows = {
  team: string;
  out: number;
  players: string[];
  payroll: number;
  allowed_in: number;
  match_rule: string;
  outgoing_needed: number;
  over_apron1: boolean;
  over_apron2: boolean;
};

type TradeCheckRows = {
  legal: boolean;
  issues: string[];
  team_a: TradeSideRows;
  team_b: TradeSideRows;
  disclaimer: string;
  salary_date?: string;
};

type CheckState =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "ok"; rows: TradeCheckRows }
  | { state: "error"; error: string };

type PartnerRow = { team: string; players: string; package_salary: number; legal: boolean; match_rule?: string };
type FillersState =
  | { state: "idle" }
  | { state: "loading"; side: "a" | "b" }
  | { state: "ok"; side: "a" | "b"; rows: PartnerRow[] }
  | { state: "error"; side: "a" | "b"; error: string };

type Package = { players: string[]; picks: string[] };

const pickKey = (pick: Pick) => `${pick.year}-${pick.round}-${pick.orig}`;
const pickLabel = (pick: Pick) => `${pick.year} R${pick.round}${pick.orig ? ` (via ${pick.orig})` : ""}${pick.protection ? ` · ${pick.protection}` : ""}`;

const chipButton = "h-7 shrink-0 rounded-[7px] border border-line bg-surface px-2 font-mono text-[11px] text-ink-2 hover:bg-hover disabled:opacity-40";
const playerButton = "w-full flex items-center justify-between gap-2 px-3 py-1.5 text-left text-xs hover:bg-hover";

export default function TradesView({ onAsk }: { onAsk?: (text: string) => void }) {
  const [teamA, setTeamA] = useState("DAL");
  const [teamB, setTeamB] = useState("NYK");
  const [assets, setAssets] = useState<Record<string, Assets>>({});
  const [pkgA, setPkgA] = useState<Package>({ players: [], picks: [] });
  const [pkgB, setPkgB] = useState<Package>({ players: [], picks: [] });
  const [check, setCheck] = useState<CheckState>({ state: "idle" });
  const [fillers, setFillers] = useState<FillersState>({ state: "idle" });
  const checkSeq = useRef(0);

  const loadAssets = useCallback((abbr: string) => {
    setAssets(previous => {
      const existing = previous[abbr];
      if (existing && existing.state !== "error") return previous;
      return { ...previous, [abbr]: { state: "loading" } };
    });
    fetch(`${BACKEND}${apiPath(`/trade/assets?team=${abbr}&season=${TRADE_SEASON}`)}`)
      .then(response => response.json())
      .then(data => {
        if (!data.ok) {
          setAssets(previous => ({ ...previous, [abbr]: { state: "error", error: data.error ?? "Could not load assets" } }));
          return;
        }
        setAssets(previous => ({ ...previous, [abbr]: { state: "ready", players: data.players ?? [], picks: data.picks ?? [], source: data.meta?.source ?? "salary_records", season: data.season ?? TRADE_SEASON } }));
      })
      .catch(() => setAssets(previous => ({ ...previous, [abbr]: { state: "error", error: "Could not reach the backend" } })));
  }, []);

  useEffect(() => {
    loadAssets(teamA);
    loadAssets(teamB);
  }, [teamA, teamB, loadAssets]);

  useEffect(() => {
    if (pkgA.players.length === 0 || pkgB.players.length === 0) {
      setCheck({ state: "idle" });
      return;
    }
    const seq = ++checkSeq.current;
    setCheck({ state: "loading" });
    fetch(`${BACKEND}${apiPath("/trade/check")}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team_a: teamA, players_a: pkgA.players, team_b: teamB, players_b: pkgB.players, season: TRADE_SEASON }),
    })
      .then(response => response.json().then(data => ({ status: response.status, data })))
      .then(({ status, data }) => {
        if (checkSeq.current !== seq) return;
        if (status === 422 || data.ok === false) {
          setCheck({ state: "error", error: data.error ?? "Trade check failed" });
          return;
        }
        setCheck({ state: "ok", rows: data.rows });
      })
      .catch(() => {
        if (checkSeq.current === seq) setCheck({ state: "error", error: "Could not reach the backend" });
      });
  }, [pkgA.players, pkgB.players, teamA, teamB]);

  const addPlayer = useCallback((side: "a" | "b", name: string) => {
    setFillers({ state: "idle" });
    if (side === "a") {
      setPkgA(previous => previous.players.includes(name) ? previous : { ...previous, players: [...previous.players, name] });
    } else {
      setPkgB(previous => previous.players.includes(name) ? previous : { ...previous, players: [...previous.players, name] });
    }
  }, []);

  const addPick = useCallback((side: "a" | "b", id: string) => {
    if (side === "a") {
      setPkgA(previous => previous.picks.includes(id) ? previous : { ...previous, picks: [...previous.picks, id] });
    } else {
      setPkgB(previous => previous.picks.includes(id) ? previous : { ...previous, picks: [...previous.picks, id] });
    }
  }, []);

  const removeItem = useCallback((side: "a" | "b", kind: "player" | "pick", value: string) => {
    setFillers({ state: "idle" });
    const setter = side === "a" ? setPkgA : setPkgB;
    setter(previous => kind === "player"
      ? { ...previous, players: previous.players.filter(name => name !== value) }
      : { ...previous, picks: previous.picks.filter(id => id !== value) });
  }, []);

  const onAssetDrag = useCallback((event: React.DragEvent, name: string) => {
    event.dataTransfer.setData("text/plain", name);
  }, []);

  const onPackageDrop = useCallback((side: "a" | "b", event: React.DragEvent) => {
    event.preventDefault();
    const name = event.dataTransfer.getData("text/plain");
    if (name.startsWith("pick:")) addPick(side, name.slice(5));
    else if (name) addPlayer(side, name);
  }, [addPlayer, addPick]);

  const suggestFillers = useCallback((side: "a" | "b") => {
    const other = side === "a" ? pkgB.players : pkgA.players;
    const target = side === "a" ? teamA : teamB;
    if (other.length === 0) return;
    setFillers({ state: "loading", side });
    fetch(`${BACKEND}${apiPath("/trade/partners")}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player: other[0], teams: target, max_packages: 3 }),
    })
      .then(response => response.json().then(data => ({ status: response.status, data })))
      .then(({ status, data }) => {
        if (status === 422 || data.ok === false) {
          setFillers({ state: "error", side, error: data.error ?? "Partner search failed" });
          return;
        }
        setFillers({ state: "ok", side, rows: (data.rows ?? []).filter((row: PartnerRow) => row.team === target) });
      })
      .catch(() => setFillers({ state: "error", side, error: "Could not reach the backend" }));
  }, [pkgA.players, pkgB.players, teamA, teamB]);

  const packageSummary = (side: "a" | "b") => {
    const pkg = side === "a" ? pkgA : pkgB;
    const names = pkg.players.slice();
    if (pkg.picks.length > 0) names.push(`${pkg.picks.length} pick${pkg.picks.length === 1 ? "" : "s"}`);
    return names.length ? names.join(", ") : "nothing";
  };

  const buildAskText = () => {
    const rows = check.state === "ok" ? check.rows : null;
    const verdict = rows ? (rows.legal ? "legal" : "not legal") : "not checked";
    const issues = rows && rows.issues.length > 0 ? ` Issues: ${rows.issues.join(" ")}` : "";
    return `Evaluate this proposed trade for ${TRADE_SEASON}: ${teamA} sends ${packageSummary("a")}; ${teamB} sends ${packageSummary("b")}. Salary check says: ${verdict}.${issues} Grade the basketball fit and value for both sides.`;
  };

  const pinArtifact = (): DimeArtifact => {
    const rows: (string | number)[][] = [];
    const push = (side: "a" | "b") => {
      const pkg = side === "a" ? pkgA : pkgB;
      const abbr = side === "a" ? teamA : teamB;
      const roster = assets[abbr];
      for (const name of pkg.players) {
        const salary = roster?.state === "ready" ? roster.players.find(player => player.name === name)?.salary : undefined;
        rows.push([`${abbr} sends`, name, salary ?? "", "player"]);
      }
      for (const id of pkg.picks) rows.push([`${abbr} sends`, id, "", "draft pick (not in salary match)"]);
    };
    push("a");
    push("b");
    if (check.state === "ok") rows.push(["verdict", check.rows.legal ? "legal" : "not legal", "", check.rows.issues.join(" ") || check.rows.disclaimer]);
    return {
      kind: "table",
      title: `${teamA} ↔ ${teamB} trade · ${TRADE_SEASON}`,
      columns: [
        { key: "side", label: "side" },
        { key: "asset", label: "asset" },
        { key: "salary", label: "salary $M", numeric: true },
        { key: "note", label: "note" },
      ],
      rows,
      provenance: {
        origin: "warehouse",
        liveSources: [],
        capability: "get_trade_check",
        season: TRADE_SEASON,
        asOf: check.state === "ok" ? check.rows.salary_date : undefined,
      },
    };
  };

  const sidePayroll = (side: "a" | "b") => {
    if (check.state !== "ok") return null;
    const rows = check.rows;
    const self = side === "a" ? rows.team_a : rows.team_b;
    const other = side === "a" ? rows.team_b : rows.team_a;
    const before = self.payroll / 1_000_000;
    const after = (self.payroll - self.out + other.out) / 1_000_000;
    return { before, after, out: self.out / 1_000_000, allowed: self.allowed_in / 1_000_000, rule: self.match_rule, needed: self.outgoing_needed, apron1: self.over_apron1, apron2: self.over_apron2 };
  };

  const renderPackage = (side: "a" | "b") => {
    const pkg = side === "a" ? pkgA : pkgB;
    const abbr = side === "a" ? teamA : teamB;
    const roster = assets[abbr];
    return (
      <div
        className="min-h-[52px] rounded-[8px] border border-dashed border-line px-2 py-1.5"
        onDragOver={event => event.preventDefault()}
        onDrop={event => onPackageDrop(side, event)}
        aria-label={`${abbr} outgoing package`}
      >
        {pkg.players.length === 0 && pkg.picks.length === 0
          ? <span className="px-1 font-mono text-[10px] text-ink-3">drag players or picks here, or click to add</span>
          : <div className="flex flex-wrap gap-1">
              {pkg.players.map(name => (
                <button key={name} className={chipButton} onClick={() => removeItem(side, "player", name)} title="Remove">
                  {name}
                  {roster?.state === "ready" ? ` ${money(roster.players.find(player => player.name === name)?.salary ?? 0)}` : ""} ×
                </button>
              ))}
              {pkg.picks.map(id => (
                <button key={id} className={chipButton} onClick={() => removeItem(side, "pick", id)} title="Remove">{id} ×</button>
              ))}
            </div>}
      </div>
    );
  };

  const renderColumn = (side: "a" | "b") => {
    const abbr = side === "a" ? teamA : teamB;
    const setTeam = side === "a" ? setTeamA : setTeamB;
    const setPkg = side === "a" ? setPkgA : setPkgB;
    const pkg = side === "a" ? pkgA : pkgB;
    const roster = assets[abbr];
    const payroll = sidePayroll(side);
    return (
      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <label className="font-mono text-[10px] uppercase tracking-wider text-ink-3" htmlFor={`trade-team-${side}`}>Team {side === "a" ? "A" : "B"} sends</label>
          <select
            id={`trade-team-${side}`}
            value={abbr}
            onChange={event => { setTeam(event.target.value); setPkg({ players: [], picks: [] }); setFillers({ state: "idle" }); }}
            className="h-7 rounded-[7px] border border-line bg-surface px-2 text-xs text-ink"
            aria-label={`Team ${side === "a" ? "A" : "B"}`}
          >
            {nbaTeams.map(team => <option key={team.abbr} value={team.abbr}>{team.abbr} · {team.name}</option>)}
          </select>
        </div>
        {renderPackage(side)}
        <div className="rounded-card border border-line bg-surface shadow-hairline">
          <div className="px-3 py-2 font-mono text-[10px] uppercase tracking-wider text-ink-3">
            {abbr} roster {roster?.state === "ready" ? `· ${roster.season}` : ""}
          </div>
          <div className="max-h-72 overflow-y-auto divide-y divide-line border-t border-line">
            {roster?.state === "loading" && <div className="px-3 py-2 text-xs text-ink-3">Loading roster…</div>}
            {roster?.state === "error" && (
              <div className="px-3 py-2 text-xs text-red">
                {roster.error} <button className="underline" onClick={() => loadAssets(abbr)}>retry</button>
              </div>
            )}
            {roster?.state === "ready" && roster.players.length === 0 && <div className="px-3 py-2 text-xs text-ink-3">No salary records for {TRADE_SEASON}.</div>}
            {roster?.state === "ready" && roster.players.map(player => {
              const picked = pkg.players.includes(player.name);
              return (
                <button
                  key={player.name}
                  className={`${playerButton} ${picked ? "bg-hover text-ink-3" : "text-ink"}`}
                  draggable
                  onDragStart={event => onAssetDrag(event, player.name)}
                  onClick={() => (picked ? removeItem(side, "player", player.name) : addPlayer(side, player.name))}
                >
                  <span className="truncate">{player.name}</span>
                  <span className="shrink-0 font-mono text-[11px] text-ink-2">{money(player.salary)}</span>
                </button>
              );
            })}
          </div>
          {roster?.state === "ready" && roster.picks.length > 0 && (
            <div className="border-t border-line px-3 py-2">
              <div className="pb-1 font-mono text-[10px] uppercase tracking-wider text-ink-3">Draft picks (no salary value)</div>
              <div className="flex flex-wrap gap-1">
                {roster.picks.map(pick => {
                  const id = pickKey(pick);
                  const picked = pkg.picks.includes(id);
                  return (
                    <button
                      key={id}
                      className={`${chipButton} ${picked ? "bg-hover text-ink-3" : ""}`}
                      draggable
                      onDragStart={event => onAssetDrag(event, `pick:${id}`)}
                      onClick={() => (picked ? removeItem(side, "pick", id) : addPick(side, id))}
                      title={pick.summary || pickLabel(pick)}
                    >
                      {id}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
        {payroll && (
          <div className="rounded-card border border-line bg-surface px-3 py-2 text-xs shadow-hairline">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-3">payroll</span>
              <span className="font-mono">{money(payroll.before)} → {money(payroll.after)}</span>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[10px] text-ink-3">
              <span>out {money(payroll.out)}</span>
              <span>allowed in {money(payroll.allowed)}</span>
              {payroll.apron1 && <span className="text-orange">over apron 1</span>}
              {payroll.apron2 && <span className="text-red">over apron 2</span>}
            </div>
            <div className="mt-0.5 font-mono text-[10px] text-ink-3">{payroll.rule}</div>
          </div>
        )}
      </div>
    );
  };

  const renderFillers = (side: "a" | "b") => {
    const needs = check.state === "ok" ? (side === "a" ? check.rows.team_a : check.rows.team_b).outgoing_needed : 0;
    const active = fillers.state !== "idle" && fillers.side === side;
    if (needs <= 0 && !active) return null;
    return (
      <div className="space-y-1">
        {needs > 0 && !active && (
          <button
            className="h-7 rounded-[7px] border border-line bg-surface px-2.5 text-xs font-medium text-ink-2 hover:bg-hover"
            onClick={() => suggestFillers(side)}
          >
            Side {side === "a" ? teamA : teamB} needs ${(needs / 1_000_000).toFixed(1)}M more outgoing · suggest fillers
          </button>
        )}
        {active && fillers.state === "loading" && <div className="text-xs text-ink-3">Searching packages…</div>}
        {active && fillers.state === "error" && <div className="text-xs text-red">{fillers.error}</div>}
        {active && fillers.state === "ok" && fillers.rows.length === 0 && <div className="text-xs text-ink-3">No matching packages.</div>}
        {active && fillers.state === "ok" && fillers.rows.map((row, index) => (
          <div key={index} className="flex items-center justify-between gap-2 rounded-[8px] border border-line bg-surface px-2.5 py-1.5 text-xs">
            <span className="min-w-0 truncate">
              <span className="text-ink">{row.players}</span>
              <span className="ml-2 font-mono text-[10px] text-ink-3">{money(row.package_salary / 1_000_000)}{row.legal ? "" : " · over limit"}</span>
            </span>
            <button
              className="h-6 shrink-0 rounded-[6px] border border-line px-2 font-mono text-[10px] text-ink-2 hover:bg-hover"
              onClick={() => row.players.split(",").map(name => name.trim()).filter(Boolean).forEach(name => addPlayer(side, name))}
            >
              Add
            </button>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="mx-auto w-full max-w-[1100px] space-y-3 px-4 py-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-ink">Trade builder</div>
          <div className="font-mono text-[10px] text-ink-3">{TRADE_SEASON} · salaries via salary_records · checks via get_trade_check</div>
        </div>
        <div className="flex items-center gap-1.5">
          {(pkgA.players.length > 0 || pkgB.players.length > 0) && <PinButton artifact={pinArtifact()} />}
          {onAsk && (
            <button
              className="h-7 rounded-[7px] border border-line bg-surface px-2.5 text-xs font-medium text-ink-2 hover:bg-hover disabled:opacity-40"
              disabled={pkgA.players.length === 0 || pkgB.players.length === 0}
              onClick={() => onAsk(buildAskText())}
            >
              Ask Dime about this trade
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3 md:flex-row">
        {renderColumn("a")}
        {renderColumn("b")}
      </div>

      <div className="rounded-card border border-line bg-surface px-3 py-2 shadow-hairline" aria-live="polite">
        {check.state === "idle" && <div className="text-xs text-ink-3">Add at least one player to each side and the salary check runs automatically.</div>}
        {check.state === "loading" && <div className="text-xs text-ink-3">Checking salary match and apron rules…</div>}
        {check.state === "error" && <div className="text-xs text-red" role="alert">{check.error}</div>}
        {check.state === "ok" && (
          <div className="space-y-1 text-xs">
            <div className={`font-semibold ${check.rows.legal ? "text-green" : "text-red"}`}>
              {check.rows.legal ? "Legal trade" : "Not legal"}
            </div>
            {check.rows.issues.map((issue, index) => <div key={index} className="text-ink-2">{issue}</div>)}
            <div className="font-mono text-[10px] text-ink-3">{check.rows.disclaimer}</div>
            {check.rows.salary_date && <div className="font-mono text-[10px] text-ink-3">salaries as of {check.rows.salary_date}</div>}
          </div>
        )}
        <div className="mt-2 space-y-1">
          {renderFillers("a")}
          {renderFillers("b")}
        </div>
      </div>
    </div>
  );
}

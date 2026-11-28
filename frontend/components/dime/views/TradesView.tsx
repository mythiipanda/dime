"use client";
import { mintGroupId } from "@/lib/move-groups";
import { writeCapHandoff, navigateToCap } from "@/lib/cap-handoff";
import type { ScenarioMove } from "@/lib/capsheet-fixture";

import { useCallback, useEffect, useRef, useState } from "react";
import { Skeleton } from "@/components/ds/Skeleton";
import { initialTeamParam, NBA_TEAM_ABBRS } from "@/lib/open-in-view";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";
import type { DimeArtifact } from "@/lib/dime-stream";
import { listBoards } from "@/lib/boards";
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
  tpe_creation?: { amount: number; expiry: string; condition: string; copy: string } | null;
};

type TradeCheckRows = {
  legal: boolean;
  issues: string[];
  team_a: TradeSideRows;
  team_b: TradeSideRows;
  disclaimer: string;
  salary_date?: string;
};

type LegTeamRows = {
  team: string;
  incoming?: number;
  outgoing?: number;
  matching_ok?: boolean;
  match_rule?: string;
  allowed_incoming?: number;
  over_apron1?: boolean;
  over_apron2?: boolean;
  hard_cap?: string | null;
  tpe_creation?: { amount: number; expiry: string; condition: string; copy: string } | null;
  issues?: string[];
};

type TpeRow = { team: string; amount: number; kind?: string; origin_year?: number; exactness?: string };

type LegsResponse = {
  rows?: LegTeamRows[];
  meta?: { disclaimer?: string; salary_date?: string; rules?: unknown };
  error?: string;
  ok?: boolean;
};

type CheckState =
  | { state: "idle" }
  | { state: "loading" }
  | { state: "ok"; rows: TradeCheckRows }
  | { state: "ok-legs"; rows: LegTeamRows[]; disclaimer: string; salary_date?: string; legal: boolean; issues: string[] }
  | { state: "error"; error: string };

type PartnerRow = { team: string; players: string; package_salary: number; legal: boolean; match_rule?: string };
type FillersState =
  | { state: "idle" }
  | { state: "loading"; side: number }
  | { state: "ok"; side: number; rows: PartnerRow[] }
  | { state: "error"; side: number; error: string };

type Package = { players: string[]; picks: string[] };
const emptyPackage = (): Package => ({ players: [], picks: [] });

const pickKey = (pick: Pick) => `${pick.year}-${pick.round}-${pick.orig}`;
const pickLabel = (pick: Pick) => `${pick.year} R${pick.round}${pick.orig ? ` (via ${pick.orig})` : ""}${pick.protection ? ` · ${pick.protection}` : ""}`;

function parsePickId(id: string): Record<string, unknown> {
  const [year, round] = id.split("-");
  return { year: Number(year), round: Number(round) };
}

const chipButton = "h-7 shrink-0 rounded-[7px] border border-line bg-surface px-2 font-mono text-[11px] text-ink-2 hover:bg-hover disabled:opacity-40";
const playerButton = "w-full flex items-center justify-between gap-2 px-3 py-1.5 text-left text-xs hover:bg-hover";

type ScenarioSnapshot = {
  teams: string[];
  packages: Package[];
  season: string;
  verdict: boolean | null;
};

function seedPartner(seeded: string): string {
  for (const candidate of ["DAL", "NYK"]) {
    if (candidate !== seeded) return candidate;
  }
  return NBA_TEAM_ABBRS.find(abbr => abbr !== seeded) ?? "DAL";
}

export default function TradesView({ onAsk }: { onAsk?: (text: string, context?: import("@/lib/view-context").ViewContext) => void }) {
  const [teams, setTeams] = useState<string[]>(() => {
    const seeded = initialTeamParam();
    if (!seeded) return ["DAL", "NYK"];
    return [seeded, seedPartner(seeded)];
  });
  const [pkgs, setPkgs] = useState<Package[]>([emptyPackage(), emptyPackage()]);
  const [assets, setAssets] = useState<Record<string, Assets>>({});
  const [check, setCheck] = useState<CheckState>({ state: "idle" });
  const [fillers, setFillers] = useState<FillersState>({ state: "idle" });
  const [snapshot, setSnapshot] = useState<ScenarioSnapshot | null>(null);
  const [inventory, setInventory] = useState<TpeRow[]>([]);
  const [manualEntry, setManualEntry] = useState<{ side: number; amount: string } | null>(null);
  const [loadNote, setLoadNote] = useState<string | null>(null);
  const checkSeq = useRef(0);

  const multi = teams.length > 2;

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
    teams.forEach(loadAssets);
  }, [teams, loadAssets]);

  useEffect(() => {
    const populated = pkgs.filter(pkg => pkg.players.length > 0).length;
    if (populated < 2) {
      setCheck({ state: "idle" });
      return;
    }
    const seq = ++checkSeq.current;
    setCheck({ state: "loading" });
    if (!multi && inventory.length === 0) {
      fetch(`${BACKEND}${apiPath("/trade/check")}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ team_a: teams[0], players_a: pkgs[0].players, team_b: teams[1], players_b: pkgs[1].players, season: TRADE_SEASON }),
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
      return;
    }
    const legs = teams.map((team, index) => ({
      from: team,
      to: teams[(index + 1) % teams.length],
      players: pkgs[index].players.join(", "),
      picks: pkgs[index].picks.map(parsePickId),
    }));
    fetch(`${BACKEND}${apiPath("/trade/legs")}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ legs, season: TRADE_SEASON, tpes: inventory.length ? inventory : undefined }),
    })
      .then(response => response.json().then(data => ({ status: response.status, data })))
      .then(({ status, data }: { status: number; data: LegsResponse }) => {
        if (checkSeq.current !== seq) return;
        if (status === 422 || data.ok === false) {
          setCheck({ state: "error", error: data.error ?? "Trade check failed" });
          return;
        }
        const rows = data.rows ?? [];
        const legal = rows.length > 0 && rows.every(row => row.matching_ok !== false) ;
        const issues = rows.flatMap(row => row.issues ?? []);
        setCheck({
          state: "ok-legs",
          rows,
          legal,
          issues,
          disclaimer: data.meta?.disclaimer ?? "",
          salary_date: data.meta?.salary_date,
        });
      })
      .catch(() => {
        if (checkSeq.current === seq) setCheck({ state: "error", error: "Could not reach the backend" });
      });
  }, [pkgs, teams, multi, inventory]);

  const setPkgAt = useCallback((index: number, next: (previous: Package) => Package) => {
    setPkgs(previous => previous.map((pkg, i) => (i === index ? next(pkg) : pkg)));
  }, []);

  const addPlayer = useCallback((side: number, name: string) => {
    setFillers({ state: "idle" });
    setPkgAt(side, previous => previous.players.includes(name) ? previous : { ...previous, players: [...previous.players, name] });
  }, [setPkgAt]);

  const addPick = useCallback((side: number, id: string) => {
    setPkgAt(side, previous => previous.picks.includes(id) ? previous : { ...previous, picks: [...previous.picks, id] });
  }, [setPkgAt]);

  const removeItem = useCallback((side: number, kind: "player" | "pick", value: string) => {
    setFillers({ state: "idle" });
    setPkgAt(side, previous => kind === "player"
      ? { ...previous, players: previous.players.filter(name => name !== value) }
      : { ...previous, picks: previous.picks.filter(id => id !== value) });
  }, [setPkgAt]);

  const setTeamAt = useCallback((index: number, abbr: string) => {
    setTeams(previous => previous.map((team, i) => (i === index ? abbr : team)));
    setPkgAt(index, () => emptyPackage());
    setFillers({ state: "idle" });
  }, [setPkgAt]);

  const addTeam = useCallback(() => {
    const unused = nbaTeams.find(team => !teams.includes(team.abbr));
    if (!unused || teams.length >= 4) return;
    setTeams(previous => [...previous, unused.abbr]);
    setPkgs(previous => [...previous, emptyPackage()]);
  }, [teams]);

  const removeTeam = useCallback((index: number) => {
    if (teams.length <= 2) return;
    setTeams(previous => previous.filter((_, i) => i !== index));
    setPkgs(previous => previous.filter((_, i) => i !== index));
  }, [teams.length]);

  const onAssetDrag = useCallback((event: React.DragEvent, name: string) => {
    event.dataTransfer.setData("text/plain", name);
  }, []);

  const onPackageDrop = useCallback((side: number, event: React.DragEvent) => {
    event.preventDefault();
    const name = event.dataTransfer.getData("text/plain");
    if (name.startsWith("pick:")) addPick(side, name.slice(5));
    else if (name) addPlayer(side, name);
  }, [addPlayer, addPick]);

  const suggestFillers = useCallback((side: number) => {
    const otherIndex = side === 0 ? 1 : 0;
    const other = pkgs[otherIndex]?.players ?? [];
    const target = teams[side];
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
  }, [pkgs, teams]);

  const packageSummary = (side: number) => {
    const pkg = pkgs[side] ?? emptyPackage();
    const names = pkg.players.slice();
    if (pkg.picks.length > 0) names.push(`${pkg.picks.length} pick${pkg.picks.length === 1 ? "" : "s"}`);
    return names.length ? names.join(", ") : "nothing";
  };

  const tradeContext = (): import("@/lib/view-context").ViewContext => {
    const legal = check.state === "ok" ? check.rows.legal : check.state === "ok-legs" ? check.legal : null;
    const issues = check.state === "ok" ? check.rows.issues : check.state === "ok-legs" ? check.issues : [];
    return {
      kind: "trade",
      summary: `${teams.join(" ↔ ")} trade · ${TRADE_SEASON}`,
      entities: {
        teams,
        season: TRADE_SEASON,
        packages: teams.map((abbr, index) => ({ team: abbr, players: (pkgs[index] ?? emptyPackage()).players, picks: (pkgs[index] ?? emptyPackage()).picks })),
        ...(legal !== null ? { legal, issues } : {}),
      },
    };
  };

  const buildAskText = () => {
    const parts = teams.map((team, index) => `${team} sends ${packageSummary(index)}`);
    let verdict = "not checked";
    let issues = "";
    if (check.state === "ok") {
      verdict = check.rows.legal ? "legal" : "not legal";
      issues = check.rows.issues.length > 0 ? ` Issues: ${check.rows.issues.join(" ")}` : "";
    } else if (check.state === "ok-legs") {
      verdict = check.legal ? "legal" : "not legal";
      issues = check.issues.length > 0 ? ` Issues: ${check.issues.join(" ")}` : "";
    }
    return `Evaluate this proposed ${teams.length}-team trade for ${TRADE_SEASON}: ${parts.join("; ")}. Salary check says: ${verdict}.${issues} Grade the basketball fit and value for every side.`;
  };

  const pinArtifact = (): DimeArtifact => {
    const rows: (string | number)[][] = [];
    teams.forEach((abbr, index) => {
      const pkg = pkgs[index] ?? emptyPackage();
      const roster = assets[abbr];
      for (const name of pkg.players) {
        const salary = roster?.state === "ready" ? roster.players.find(player => player.name === name)?.salary : undefined;
        rows.push([`${abbr} sends`, name, salary ?? "", "player"]);
      }
      for (const id of pkg.picks) rows.push([`${abbr} sends`, id, "", "draft pick (not in salary match)"]);
    });
    const legal = check.state === "ok" ? check.rows.legal : check.state === "ok-legs" ? check.legal : null;
    const issueText = check.state === "ok" ? check.rows.issues.join(" ") : check.state === "ok-legs" ? check.issues.join(" ") : "";
    if (legal !== null) rows.push(["verdict", legal ? "legal" : "not legal", "", issueText]);
    return {
      kind: "table",
      title: `${teams.join(" ↔ ")} trade · ${TRADE_SEASON}`,
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
        capability: multi ? "get_trade_legality" : "get_trade_check",
        season: TRADE_SEASON,
        asOf: check.state === "ok" ? check.rows.salary_date : check.state === "ok-legs" ? check.salary_date : undefined,
      },
    };
  };

  const scenarioArtifact = (): DimeArtifact => {
    const legal = check.state === "ok" ? check.rows.legal : check.state === "ok-legs" ? check.legal : null;
    return {
      kind: "trade_scenario",
      title: `${teams.join(" ↔ ")} scenario · ${TRADE_SEASON}`,
      teams: teams.slice(),
      packages: pkgs.map(pkg => ({ players: pkg.players.slice(), picks: pkg.picks.slice() })),
      season: TRADE_SEASON,
      verdict: legal,
    } as unknown as DimeArtifact;
  };

  function loadScenario() {
    for (const board of listBoards()) {
      const pin = (board.pins ?? []).filter(p => (p.artifact as { kind?: string }).kind === "trade_scenario").pop();
      if (!pin) continue;
      const artifact = pin.artifact as unknown as ScenarioSnapshot & { packages?: Package[] };
      if (!Array.isArray(artifact.teams) || !Array.isArray(artifact.packages)) continue;
      setTeams(artifact.teams.slice());
      setPkgs(artifact.packages.map(pkg => ({ players: (pkg.players ?? []).slice(), picks: (pkg.picks ?? []).slice() })));
      setSnapshot({ teams: artifact.teams.slice(), packages: artifact.packages, season: artifact.season, verdict: artifact.verdict ?? null });
      const carried = (artifact as unknown as { tpes?: TpeRow[] }).tpes;
      if (Array.isArray(carried)) setInventory(carried.filter(row => row && typeof row.team === "string" && typeof row.amount === "number"));
      setLoadNote(`loaded "${pin.artifact.title}" from "${board.title}"`);
      return;
    }
    setLoadNote("no saved trade scenario found on any board");
  }

  function sendToCapSheet(teamIndex: number) {
    const team = teams[teamIndex];
    const outgoing = pkgs[teamIndex]?.players ?? [];
    const incomingIndex = (teamIndex + teams.length - 1) % teams.length;
    const incoming = pkgs[incomingIndex]?.players ?? [];
    if (!outgoing.length && !incoming.length) return;
    const salaryOf = (name: string, ownerIndex: number): number | undefined => {
      const roster = assets[teams[ownerIndex]];
      return roster?.state === "ready" ? roster.players.find((player) => player.name === name)?.salary : undefined;
    };
    const season = TRADE_SEASON;
    const group = mintGroupId();
    const partners = teams.filter((_, index) => index !== teamIndex).join(" ↔ ");
    const moves: ScenarioMove[] = [
      ...outgoing.map((name) => {
        const amount = salaryOf(name, teamIndex);
        return { kind: "trade_out" as const, player: name, group, ...(amount ? { amount } : {}) };
      }),
      ...incoming.map((name) => {
        const amount = salaryOf(name, incomingIndex);
        return { kind: "trade_in" as const, player: name, group, ...(amount ? { amount } : {}) };
      }),
    ];
    const verdict = check.state === "ok" ? check.rows.legal : check.state === "ok-legs" ? check.legal : null;
    writeCapHandoff({
      team,
      season,
      moves,
      source: `${teams.join(" ↔ ")} · ${pkgs.reduce((total, pkg) => total + pkg.players.length, 0)} players in the trade`,
      groups: { [group]: { partner: partners, verdict, evaluated_at: new Date().toISOString() } },
    });
    navigateToCap();
  }

  const currentVerdict = check.state === "ok" ? check.rows.legal : check.state === "ok-legs" ? check.legal : null;
  const verdictDrift = snapshot && snapshot.verdict !== null && currentVerdict !== null && snapshot.verdict !== currentVerdict;

  const sidePayroll = (side: number) => {
    if (check.state !== "ok" || side > 1) return null;
    const rows = check.rows;
    const self = side === 0 ? rows.team_a : rows.team_b;
    const other = side === 0 ? rows.team_b : rows.team_a;
    const before = self.payroll / 1_000_000;
    const after = (self.payroll - self.out + other.out) / 1_000_000;
    return { before, after, out: self.out / 1_000_000, allowed: self.allowed_in / 1_000_000, rule: self.match_rule, needed: self.outgoing_needed, apron1: self.over_apron1, apron2: self.over_apron2, tpeCreation: self.tpe_creation ?? null };
  };

  const legRow = (side: number): LegTeamRows | null => {
    if (check.state !== "ok-legs") return null;
    return check.rows.find(row => row.team === teams[side]) ?? null;
  };

  const [dragOver, setDragOver] = useState<number | null>(null);

  const renderPackage = (side: number) => {
    const pkg = pkgs[side] ?? emptyPackage();
    const abbr = teams[side];
    const roster = assets[abbr];
    return (
      <div
        className={`min-h-[52px] rounded-[8px] border border-dashed px-2 py-1.5 transition-colors ${
          dragOver === side ? "border-accent bg-field" : "border-line"
        }`}
        onDragOver={event => {
          event.preventDefault();
          if (dragOver !== side) setDragOver(side);
        }}
        onDragLeave={event => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragOver(null);
        }}
        onDrop={event => {
          setDragOver(null);
          onPackageDrop(side, event);
        }}
        aria-label={`${abbr} outgoing package`}
      >
        {pkg.players.length === 0 && pkg.picks.length === 0
          ? <span className="px-1 text-[11px] text-ink-2">drag players or picks here, or click to add</span>
          : <div className="flex flex-wrap gap-1">
              {pkg.players.map(name => (
                <button key={name} className={chipButton} style={{ animation: "fade-up 150ms var(--ease-out-strong) both" }} onClick={() => removeItem(side, "player", name)} title="Remove">
                  {name}
                  {roster?.state === "ready" ? ` ${money(roster.players.find(player => player.name === name)?.salary ?? 0)}` : ""} ×
                </button>
              ))}
              {pkg.picks.map(id => (
                <button key={id} className={chipButton} style={{ animation: "fade-up 150ms var(--ease-out-strong) both" }} onClick={() => removeItem(side, "pick", id)} title="Remove">{id} ×</button>
              ))}
            </div>}
      </div>
    );
  };

  const renderColumn = (side: number) => {
    const abbr = teams[side];
    const pkg = pkgs[side] ?? emptyPackage();
    const roster = assets[abbr];
    const payroll = sidePayroll(side);
    const leg = legRow(side);
    const label = multi ? `${abbr} → ${teams[(side + 1) % teams.length]}` : `Team ${side === 0 ? "A" : "B"} sends`;
    return (
      <div key={`${side}-${abbr}`} className="flex-1 min-w-0 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <label className="text-[11.5px] font-medium uppercase tracking-wide text-ink-2" htmlFor={`trade-team-${side}`}>{label}</label>
          <div className="flex items-center gap-1">
            <select
              id={`trade-team-${side}`}
              value={abbr}
              onChange={event => setTeamAt(side, event.target.value)}
              className="h-7 rounded-[7px] border border-line bg-surface px-2 text-xs text-ink"
              aria-label={`Team ${side + 1}`}
            >
              {nbaTeams.map(team => <option key={team.abbr} value={team.abbr}>{team.abbr} · {team.name}</option>)}
            </select>
            {teams.length > 2 && (
              <button className="h-7 rounded-[7px] border border-line px-1.5 font-mono text-[11px] text-ink-3 hover:bg-hover" onClick={() => removeTeam(side)} title="Remove team">×</button>
            )}
          </div>
        </div>
        {renderPackage(side)}
        <div className="rounded-card border border-line bg-surface shadow-hairline">
          <div className="px-3 py-2 text-[13px] font-semibold text-ink">
            {abbr} roster {roster?.state === "ready" ? `· ${roster.season}` : ""}
          </div>
          <div className="max-h-[max(18rem,52vh)] overflow-y-auto divide-y divide-line border-t border-line">
            {roster?.state === "loading" && (
              <div className="space-y-2 px-3 py-2" aria-label="loading roster">
                {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-[20px]" />)}
              </div>
            )}
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
              <div className="pb-1 text-[11.5px] font-medium text-ink-2">Draft picks (no salary value)</div>
              <div className="flex flex-wrap gap-1">
                {[...roster.picks].sort((a, b) => a.year - b.year || a.round - b.round).map(pick => {
                  const id = pickKey(pick);
                  const picked = pkg.picks.includes(id);
                  return (
                    <button
                      key={id}
                      className={`${chipButton} inline-flex items-baseline gap-1 ${picked ? "bg-hover text-ink-3" : ""}`}
                      draggable
                      onDragStart={event => onAssetDrag(event, `pick:${id}`)}
                      onClick={() => (picked ? removeItem(side, "pick", id) : addPick(side, id))}
                      title={pick.summary || pickLabel(pick)}
                    >
                      <span className={picked ? "" : "text-ink"}>{pick.year}</span>
                      <span className="text-ink-3">R{pick.round}</span>
                      {pick.orig ? <span className="text-[10px] text-ink-3">{pick.orig}</span> : null}
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
            <div className="mt-0.5 text-[11px] text-ink-2">{payroll.rule}</div>
            {payroll.tpeCreation && (
              <div className="mt-1 rounded-[6px] border border-line bg-field px-2 py-1 text-[11px] leading-snug text-ink-2">
                <span className="font-mono text-[10px] uppercase tracking-wider text-accent">trade exception</span>{" "}
                {payroll.tpeCreation.copy}{" "}
                <button
                  className="font-mono text-[10px] text-accent underline underline-offset-2 hover:text-ink"
                  onClick={() => setInventory(rows => [...rows, { team: abbr, amount: payroll.tpeCreation!.amount, kind: "ordinary", exactness: "scenario_derived" }])}
                >
                  carry into inventory
                </button>
              </div>
            )}
          </div>
        )}
        {leg && (
          <div className="rounded-card border border-line bg-surface px-3 py-2 text-xs shadow-hairline">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-3">matching</span>
              <span className={`font-mono text-[10.5px] ${leg.matching_ok === false ? "text-red" : "text-green"}`}>{leg.matching_ok === false ? "fails" : "ok"}</span>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[10px] text-ink-3">
              {leg.outgoing != null && <span>out {money(leg.outgoing / 1_000_000)}</span>}
              {leg.incoming != null && <span>in {money(leg.incoming / 1_000_000)}</span>}
              {leg.over_apron1 && <span className="text-orange">over apron 1</span>}
              {leg.over_apron2 && <span className="text-red">over apron 2</span>}
              {leg.hard_cap && <span className="text-red">hard-capped at {leg.hard_cap}</span>}
            </div>
            {leg.match_rule && <div className="mt-0.5 text-[11px] text-ink-2">{leg.match_rule}</div>}
            {leg.tpe_creation && (
              <div className="mt-1 rounded-[6px] border border-line bg-field px-2 py-1 text-[11px] leading-snug text-ink-2">
                <span className="font-mono text-[10px] uppercase tracking-wider text-accent">trade exception</span>{" "}
                {leg.tpe_creation.copy}{" "}
                <button
                  className="font-mono text-[10px] text-accent underline underline-offset-2 hover:text-ink"
                  onClick={() => setInventory(rows => [...rows, { team: abbr, amount: leg.tpe_creation!.amount, kind: "ordinary", exactness: "scenario_derived" }])}
                >
                  carry into inventory
                </button>
              </div>
            )}
          </div>
        )}
        {(inventory.some(row => row.team === abbr) || manualEntry?.side === side) && (
          <div className="rounded-card border border-line bg-surface px-3 py-2 text-xs shadow-hairline">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-3">exception inventory</span>
              {inventory.some(row => row.team === abbr) && <span className="font-mono text-[10px] text-ink-3">applied to evaluation</span>}
            </div>
            <div className="mt-1 space-y-1">
              {inventory.map((row, index) => row.team === abbr && (
                <div key={index} className="flex items-center justify-between gap-2 text-[11px] text-ink-2">
                  <span>
                    {money(row.amount / 1_000_000)} {row.kind ?? "ordinary"} exception
                    <span className="ml-1 text-ink-3">{(row.exactness ?? "user_declared").replace(/_/g, " ")}</span>
                  </span>
                  <button
                    className="font-mono text-[10px] text-ink-3 hover:text-red"
                    onClick={() => setInventory(rows => rows.filter((_, at) => at !== index))}
                    title="Remove from inventory"
                  >×</button>
                </div>
              ))}
              {manualEntry?.side === side ? (
                <form
                  className="flex items-center gap-1.5"
                  onSubmit={event => {
                    event.preventDefault();
                    const millions = parseFloat(manualEntry.amount);
                    if (Number.isFinite(millions) && millions > 0) {
                      setInventory(rows => [...rows, { team: abbr, amount: Math.round(millions * 1_000_000), kind: "ordinary", exactness: "user_declared" }]);
                    }
                    setManualEntry(null);
                  }}
                >
                  <input
                    autoFocus
                    className="h-6 w-20 rounded-[6px] border border-line bg-field px-1.5 font-mono text-[11px] text-ink"
                    placeholder="0.0"
                    value={manualEntry.amount}
                    onChange={event => setManualEntry({ side, amount: event.target.value })}
                    aria-label={`${abbr} exception amount in millions`}
                  />
                  <span className="text-[10px] text-ink-3">$M</span>
                  <button type="submit" className="font-mono text-[10px] text-accent underline underline-offset-2">add</button>
                  <button type="button" className="font-mono text-[10px] text-ink-3" onClick={() => setManualEntry(null)}>cancel</button>
                </form>
              ) : (
                <button
                  className="font-mono text-[10px] text-ink-3 underline underline-offset-2 hover:text-accent"
                  onClick={() => setManualEntry({ side, amount: "" })}
                >
                  add manually
                </button>
              )}
            </div>
          </div>
        )}
        {!inventory.some(row => row.team === abbr) && manualEntry?.side !== side && (
          <button
            className="w-full text-left font-mono text-[10px] text-ink-3 underline underline-offset-2 hover:text-accent px-1"
            onClick={() => setManualEntry({ side, amount: "" })}
            title="Exceptions come from your own prior constructions or manual entry; real-world inventory is not derivable from the warehouse"
          >
            no exceptions on file — add manually
          </button>
        )}
        {(leg || check.state === "ok") && (
          <button
            className="w-full rounded-[7px] border border-line bg-surface px-3 py-1.5 text-left text-[11.5px] text-ink-2 shadow-hairline hover:bg-field"
            onClick={() => sendToCapSheet(side)}
          >
            Send {abbr} to the working scenario → cap sheet & planner
          </button>
        )}
      </div>
    );
  };

  const renderFillers = (side: number) => {
    if (multi || side > 1) return null;
    const sideRows = check.state === "ok" ? (side === 0 ? check.rows.team_a : check.rows.team_b) : null;
    const needs = sideRows ? Math.max(0, sideRows.outgoing_needed - sideRows.out) : 0;
    const active = fillers.state !== "idle" && fillers.side === side;
    if (needs <= 0) return null;
    return (
      <div className="space-y-1">
        {needs > 0 && !active && (
          <button
            className="h-7 rounded-[7px] border border-line bg-surface px-2.5 text-xs font-medium text-ink-2 hover:bg-hover"
            onClick={() => suggestFillers(side)}
          >
            Side {teams[side]} needs ${(needs / 1_000_000).toFixed(1)}M more outgoing · suggest fillers
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
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1.5">
        <div>
          <div className="text-sm font-semibold text-ink">Trade builder</div>
          <div className="text-[11px] text-ink-2">
            {TRADE_SEASON} · salaries via salary_records · checks via {multi ? "get_trade_legality" : "get_trade_check"}
            {multi ? " · rotational construction: each team's outgoing goes to the next team" : ""}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {teams.length < 4 && (
            <button
              className="h-7 rounded-[7px] border border-line bg-surface px-2.5 text-xs font-medium text-ink-2 hover:bg-hover"
              onClick={addTeam}
            >
              Add team
            </button>
          )}
          {pkgs.some(pkg => pkg.players.length > 0 || pkg.picks.length > 0) && (
            <>
              <span title="Pin trade table"><PinButton artifact={pinArtifact()} /></span>
              <span title="Pin re-loadable scenario"><PinButton artifact={scenarioArtifact()} /></span>
            </>
          )}
          <button
            className="h-7 rounded-[7px] border border-line bg-surface px-2.5 text-xs font-medium text-ink-2 hover:bg-hover"
            onClick={loadScenario}
          >
            Load saved
          </button>
          {onAsk && (
            <button
              className="h-7 rounded-[7px] border border-line bg-surface px-2.5 text-xs font-medium text-ink-2 hover:bg-hover disabled:opacity-40"
              disabled={pkgs.filter(pkg => pkg.players.length > 0).length < 2}
              onClick={() => onAsk(buildAskText(), tradeContext())}
            >
              Ask Dime about this trade
            </button>
          )}
        </div>
      </div>

      {loadNote && <div className="text-[11px] text-ink-2">{loadNote}</div>}

      <div className="flex flex-col gap-3 md:flex-row">
        {teams.map((_, index) => renderColumn(index))}
      </div>

      <div className="rounded-card border border-line bg-surface px-3 py-2 shadow-hairline" aria-live="polite">
        {check.state === "idle" && <div className="text-xs text-ink-3">Add players to at least two sides and the salary check runs automatically.</div>}
        {check.state === "loading" && <div className="text-xs text-ink-3">Checking salary match and apron rules…</div>}
        {check.state === "error" && <div className="text-xs text-red" role="alert">{check.error}</div>}
        {check.state === "ok" && (
          <div className="space-y-1 text-xs">
            <div className={`font-semibold ${check.rows.legal ? "text-green" : "text-red"}`}>
              {check.rows.legal ? "Legal trade" : "Not legal"}
            </div>
            {check.rows.issues.map((issue, index) => <div key={index} className="text-ink-2">{issue}</div>)}
            <div className="mt-1 text-[11px] text-ink-2">{check.rows.disclaimer}</div>
            {check.rows.salary_date && <div className="text-[11px] text-ink-2">salaries as of {check.rows.salary_date}</div>}
          </div>
        )}
        {check.state === "ok-legs" && (
          <div className="space-y-1 text-xs">
            <div className={`font-semibold ${check.legal ? "text-green" : "text-red"}`}>
              {check.legal ? "Matching passes for every team" : "Matching fails for at least one team"}
            </div>
            {check.issues.map((issue, index) => <div key={index} className="text-ink-2">{issue}</div>)}
            {check.disclaimer && <div className="mt-1 text-[11px] text-ink-2">{check.disclaimer}</div>}
            {check.salary_date && <div className="text-[11px] text-ink-2">salaries as of {check.salary_date}</div>}
          </div>
        )}
        {verdictDrift && snapshot && (
          <div className="mt-1 rounded-[7px] border border-line px-2 py-1 text-[11px] text-ink-2" role="status">
            Verdict changed since this scenario was pinned: was {snapshot.verdict ? "legal" : "not legal"}, now {currentVerdict ? "legal" : "not legal"} on current salaries.
          </div>
        )}
        <div className="mt-2 space-y-1">
          {renderFillers(0)}
          {renderFillers(1)}
        </div>
      </div>
    </div>
  );
}

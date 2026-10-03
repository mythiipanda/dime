"use client";

import { useEffect, useState } from "react";
import CopyLink from "./CopyLink";
import ExplorePanel, { PanelHeader } from "./ExplorePanel";
import Skeleton from "./Skeleton";
import WowyCard from "./WowyCard";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BACKEND } from "../lib/chat";
import { apiPath, getQueryParam, setQueryParam } from "../lib/api";
import { shortPlayerName } from "../lib/exploreIndex";
import { streakLine } from "../lib/exploreFeed";
import type { StreakDetail } from "../lib/exploreSearch";
import { TEAM_IDS, abbrForTeamFullName } from "../lib/teams";

const TEAMS: Record<string, number> = TEAM_IDS;
const FETCH_TIMEOUT_MS = 15000;
const RETRY_DELAY_MS = 600;
const UNAVAILABLE = "Lineup data is unavailable right now.";

type Row = { GROUP_NAME: string; MIN: number; PLUS_MINUS: number };

type LineupPanelProps = {
  initialTeam?: string;
  initialStreak?: StreakDetail;
  fetchTimeoutMs?: number;
  retryDelayMs?: number;
};

function resolveTeam(raw: string | null | undefined): string {
  const v = (raw || "").trim();
  if (!v) return "BOS";
  const up = v.toUpperCase();
  if (TEAMS[up]) return up;
  const full = abbrForTeamFullName(v);
  if (full && TEAMS[full]) return full;
  return "BOS";
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function fetchJson(url: string, timeoutMs: number): Promise<{ data?: unknown[]; verdict?: string }> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: ctrl.signal });
    const d = (await res.json()) as { ok?: boolean; data?: unknown[]; verdict?: string };
    if (!res.ok || !d.ok) throw new Error("unavailable");
    return { data: d.data, verdict: d.verdict };
  } finally {
    clearTimeout(timer);
  }
}

export default function LineupPanel({ initialTeam, initialStreak, fetchTimeoutMs = FETCH_TIMEOUT_MS, retryDelayMs = RETRY_DELAY_MS }: LineupPanelProps) {
  const [tab, setTab] = useState<"5man" | "wowy">(() => {
    const t = getQueryParam("lineups_tab");
    return t === "wowy" ? "wowy" : "5man";
  });
  const [team, setTeam] = useState(() => resolveTeam(initialTeam || getQueryParam("lineups_team")));
  const [streak, setStreak] = useState(initialStreak);
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);

  const [playerA, setPlayerA] = useState(() => getQueryParam("wowy_a") || "");
  const [playerB, setPlayerB] = useState(() => getQueryParam("wowy_b") || "");
  const [wowyRows, setWowyRows] = useState<unknown[]>([]);
  const [wowyVerdict, setWowyVerdict] = useState("");
  const [wowyBusy, setWowyBusy] = useState(false);


  useEffect(() => {
    if (tab === "wowy" && wowyRows.length === 0) runWowy();
  }, []);

  useEffect(() => {
    let live = true;
    setQueryParam("lineups_team", team, true);
    setBusy(true);
    setError("");
    const id = TEAMS[team];
    const run = async () => {
      for (let attempt = 0; attempt < 2; attempt++) {
        if (!live) return;
        if (attempt > 0) await sleep(retryDelayMs);
        if (!live) return;
        try {
          const d = await fetchJson(`${BACKEND}${apiPath(`/datasets/lineups?team_id=${id}`)}`, fetchTimeoutMs);
          if (!live) return;
          const all = [...((d.data || []) as Row[])];
          all.sort((a, b) => Number(b.MIN) - Number(a.MIN));
          setRows(all.slice(0, 12));
          break;
        } catch {
          if (!live) return;
          if (attempt === 1) {
            setRows([]);
            setError(UNAVAILABLE);
          }
        }
      }
      if (live) setBusy(false);
    };
    run();
    return () => {
      live = false;
    };
  }, [team, retryNonce]);

  const runWowy = () => {
    if (!playerA || !playerB) return;
    setWowyBusy(true);
    setError("");
    setQueryParam("wowy_a", playerA, true);
    setQueryParam("wowy_b", playerB, true);
    const url = `${BACKEND}${apiPath(`/datasets/wowy?player_a=${encodeURIComponent(playerA)}&player_b=${encodeURIComponent(playerB)}`)}`;
    const run = async () => {
      for (let attempt = 0; attempt < 2; attempt++) {
        if (attempt > 0) await sleep(retryDelayMs);
        try {
          const d = await fetchJson(url, fetchTimeoutMs);
          setWowyRows(d.data || []);
          setWowyVerdict(d.verdict || "");
          break;
        } catch {
          if (attempt === 1) {
            setWowyRows([]);
            setWowyVerdict("");
            setError(UNAVAILABLE);
          }
        }
      }
      setWowyBusy(false);
    };
    run();
  };

  const pickTeam = (abbr: string) => {
    setTeam(abbr);
    setStreak(undefined);
    setQueryParam("lineups_team", abbr, true);
  };

  const pickTab = (next: "5man" | "wowy") => {
    setTab(next);
    setQueryParam("lineups_tab", next, true);
    if (next === "wowy" && !wowyRows.length) runWowy();
  };

  return (
    <ExplorePanel id="explore-lineups">
      <PanelHeader
        kicker="Teams"
        title="Lineups"
        action={<CopyLink panel="lineups" />}
      />
      <div style={{ display: "inline-flex", background: "var(--color-stone-canvas)", padding: 2, borderRadius: 9999, border: "1px solid var(--color-stone-border)", marginBottom: 12 }}>
        <button
          className={tab === "5man" ? "tab-active" : "pill-ghost"}
          style={{ fontSize: 11, padding: "3px 12px", border: "none" }}
          onClick={() => pickTab("5man")}
        >
          5-Man
        </button>
        <button
          className={tab === "wowy" ? "tab-active" : "pill-ghost"}
          style={{ fontSize: 11, padding: "3px 12px", border: "none" }}
          onClick={() => pickTab("wowy")}
        >
          WOWY
        </button>
      </div>

      {tab === "5man" ? (
        <div>
          {streak && (
            <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 8 }}>
              {streakLine(streak)}
            </div>
          )}
          <Select value={team} onValueChange={(next: string | null) => { if (next) pickTeam(next); }}>
            <SelectTrigger aria-label="Team" style={{ width: 120 }}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.keys(TEAMS).map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {error && (
            <div style={{ marginTop: 8 }}>
              <div style={{ color: "var(--color-warm-gray)", fontSize: 12 }}>{error}</div>
              <button
                className="pill-ghost"
                style={{ fontSize: 12, marginTop: 8 }}
                onClick={() => setRetryNonce((n) => n + 1)}
              >
                Try again
              </button>
            </div>
          )}
          {busy && rows.length === 0 && !error && <Skeleton lines={5} label={`Loading ${team} lineups`} />}
          {!busy && !error && rows.length === 0 && (
            <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 8 }}>
              No lineups. They show up once the season is far enough along.
            </div>
          )}
          {rows.length > 0 && (
          <table style={{ width: "100%", marginTop: 8, fontSize: 12 }}>
            <thead><tr><th style={{ textAlign: "left" }}>Unit</th><th>MIN</th><th>+/-</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{String(r.GROUP_NAME || "").split(" - ").map(shortPlayerName).join(", ")}</td>
                  <td style={{ textAlign: "right" }}>{Number(r.MIN).toFixed(1)}</td>
                  <td style={{ textAlign: "right" }}>{r.PLUS_MINUS}</td>
                </tr>
              ))}
            </tbody>
          </table>
          )}
        </div>
      ) : (
        <div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
            <input
              className="field"
              placeholder="Player A"
              value={playerA}
              onChange={(e) => setPlayerA(e.target.value)}
              style={{ width: 160, fontSize: 12 }}
              aria-label="Player A"
            />
            <input
              className="field"
              placeholder="Player B"
              value={playerB}
              onChange={(e) => setPlayerB(e.target.value)}
              style={{ width: 160, fontSize: 12 }}
              aria-label="Player B"
            />
            <button
              className="pill-cta"
              style={{ fontSize: 12, padding: "4px 14px" }}
              disabled={wowyBusy}
              onClick={runWowy}
            >
              {wowyBusy ? "Calculating..." : "Compare"}
            </button>
          </div>
          {error && <div style={{ color: "var(--color-warm-gray)", fontSize: 12, marginBottom: 8 }}>{error}</div>}
          {wowyRows.length > 0 && <WowyCard rows={wowyRows} verdict={wowyVerdict} />}
        </div>
      )}
    </ExplorePanel>
  );
}

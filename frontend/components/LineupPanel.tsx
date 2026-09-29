"use client";

import { useEffect, useState } from "react";
import CopyLink from "./CopyLink";
import ExplorePanel, { PanelHeader } from "./ExplorePanel";
import Skeleton from "./Skeleton";
import WowyCard from "./WowyCard";
import { BACKEND } from "../lib/chat";
import { apiPath, getQueryParam, setQueryParam } from "../lib/api";
import { shortPlayerName } from "../lib/exploreIndex";
import { TEAM_IDS } from "../lib/teams";

const TEAMS: Record<string, number> = TEAM_IDS;

type Row = { GROUP_NAME: string; MIN: number; PLUS_MINUS: number };

export default function LineupPanel({ initialTeam }: { initialTeam?: string }) {


  const [tab, setTab] = useState<"5man" | "wowy">(() => {
    const t = getQueryParam("lineups_tab");
    return t === "wowy" ? "wowy" : "5man";
  });
  const [team, setTeam] = useState(() => {


    const s = (initialTeam || getQueryParam("lineups_team") || "BOS").toUpperCase();
    return TEAMS[s] ? s : "BOS";
  });
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);


  const [playerA, setPlayerA] = useState(() => getQueryParam("wowy_a") || "Luka");
  const [playerB, setPlayerB] = useState(() => getQueryParam("wowy_b") || "LeBron");
  const [wowyRows, setWowyRows] = useState<unknown[]>([]);
  const [wowyVerdict, setWowyVerdict] = useState("");
  const [wowyBusy, setWowyBusy] = useState(false);


  useEffect(() => {
    if (tab === "wowy" && wowyRows.length === 0) runWowy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let live = true;
    setBusy(true);
    setError("");
    const id = TEAMS[team];
    if (!id) {
      setBusy(false);
      setError("Unknown team.");
      setRows([]);
      return () => {
        live = false;
      };
    }
    fetch(`${BACKEND}${apiPath(`/datasets/lineups?team_id=${id}`)}`)
      .then((r) => r.json())
      .then((d) => {
        if (!live) return;
        if (!d.ok) setError(String(d.error || "failed"));
        else {
          const all = (d.data || []) as Row[];
          all.sort((a, b) => Number(b.MIN) - Number(a.MIN));
          setRows(all.slice(0, 12));
        }
      })
      .catch((e) => live && setError(String(e)))
      .finally(() => live && setBusy(false));
    return () => {
      live = false;
    };
  }, [team]);

  const runWowy = () => {
    if (!playerA || !playerB) return;
    setWowyBusy(true);
    setError("");
    setQueryParam("wowy_a", playerA, true);
    setQueryParam("wowy_b", playerB, true);
    fetch(`${BACKEND}${apiPath(`/datasets/wowy?player_a=${encodeURIComponent(playerA)}&player_b=${encodeURIComponent(playerB)}`)}`)
      .then((r) => r.json())
      .then((d) => {
        if (!d.ok) setError(String(d.error || "Failed to calculate WOWY splits"));
        else {
          setWowyRows(d.data || []);
          setWowyVerdict(d.verdict || "");
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setWowyBusy(false));
  };

  const pickTeam = (abbr: string) => {
    setTeam(abbr);
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
          <select className="field" value={team} onChange={(e) => pickTeam(e.target.value)} style={{ width: 120 }} aria-label="Team">
            {Object.keys(TEAMS).map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          {error && <div style={{ color: "var(--color-warm-gray)", marginTop: 8 }}>{error}</div>}
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
              placeholder="Player A (e.g. Luka)"
              value={playerA}
              onChange={(e) => setPlayerA(e.target.value)}
              style={{ width: 160, fontSize: 12 }}
              aria-label="Player A"
            />
            <input
              className="field"
              placeholder="Player B (e.g. LeBron)"
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
          {error && <div style={{ color: "var(--color-warm-gray)", marginBottom: 8 }}>{error}</div>}
          {wowyRows.length > 0 && <WowyCard rows={wowyRows} verdict={wowyVerdict} />}
        </div>
      )}
    </ExplorePanel>
  );
}

"use client";

import { useEffect, useState } from "react";
import { BACKEND } from "../lib/chat";

const TEAMS: Record<string, number> = {
  ATL: 1610612737,
  BOS: 1610612738,
  CLE: 1610612739,
  NOP: 1610612740,
  CHI: 1610612741,
  DAL: 1610612742,
  DEN: 1610612743,
  GSW: 1610612744,
  HOU: 1610612745,
  LAC: 1610612746,
  LAL: 1610612747,
  MIA: 1610612748,
  MIL: 1610612749,
  MIN: 1610612750,
  BKN: 1610612751,
  NYK: 1610612752,
  ORL: 1610612753,
  IND: 1610612754,
  PHI: 1610612755,
  PHX: 1610612756,
  POR: 1610612757,
  SAC: 1610612758,
  SAS: 1610612759,
  OKC: 1610612760,
  TOR: 1610612761,
  UTA: 1610612762,
  MEM: 1610612763,
  WAS: 1610612764,
  DET: 1610612765,
  CHA: 1610612766,
};

type Row = { GROUP_NAME: string; MIN: number; PLUS_MINUS: number; SAMPLE?: string };

function short(full: string) {
  const p = full.trim().split(/\s+/);
  return p.length > 1 ? `${p[0][0]}. ${p.slice(-1)}` : full.trim();
}

export default function LineupPanel() {
  const [team, setTeam] = useState("BOS");
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
    fetch(`${BACKEND}/api/v1/datasets/lineups?team_id=${id}`)
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

  return (
    <div className="card">
      <div className="display" style={{ fontSize: 20 }}>Crew lineups</div>
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 4 }}>
        Five-man units by minutes. Dots mark under 50 MIN.
      </div>
      <select className="field" value={team} onChange={(e) => setTeam(e.target.value)} style={{ marginTop: 12, width: 120 }}>
        {Object.keys(TEAMS).map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
      {error && <div style={{ color: "var(--color-warm-gray)", marginTop: 8 }}>{error}</div>}
      <table style={{ width: "100%", marginTop: 8, fontSize: 12 }}>
        <thead><tr><th style={{ textAlign: "left" }}>Unit</th><th>MIN</th><th>+/-</th><th /></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{String(r.GROUP_NAME || "").split(" - ").map(short).join(", ")}</td>
              <td style={{ textAlign: "right" }}>{Number(r.MIN).toFixed(1)}</td>
              <td style={{ textAlign: "right" }}>{r.PLUS_MINUS}</td>
              <td title={r.SAMPLE || ""}>{r.SAMPLE ? "●" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {busy && <div style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>Loading</div>}
    </div>
  );
}

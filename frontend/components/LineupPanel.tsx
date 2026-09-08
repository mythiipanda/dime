"use client";

import { useEffect, useState } from "react";
import { BACKEND } from "../lib/chat";

const TEAMS: Record<string, number> = {
  BOS: 1610612738,
  OKC: 1610612760,
  NYK: 1610612752,
  SAS: 1610612759,
  CLE: 1610612739,
  DEN: 1610612743,
  MIN: 1610612750,
  DET: 1610612765,
  PHI: 1610612755,
  LAL: 1610612747,
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
    fetch(`${BACKEND}/api/v1/datasets/lineups?team_id=${TEAMS[team]}`)
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
      <div style={{ fontSize: 12, color: "#78716c", marginTop: 4 }}>
        Five-man units by minutes. Dots mark under 50 MIN.
      </div>
      <select className="field" value={team} onChange={(e) => setTeam(e.target.value)} style={{ marginTop: 12, width: 120 }}>
        {Object.keys(TEAMS).map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
      {error && <div style={{ color: "#78716c", marginTop: 8 }}>{error}</div>}
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
      {busy && <div style={{ fontSize: 12, color: "#78716c" }}>Loading</div>}
    </div>
  );
}

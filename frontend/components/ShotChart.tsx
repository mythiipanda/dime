"use client";

import { useEffect, useRef, useState } from "react";
import DataTable from "./DataTable";
import { zoneSplits } from "./Sparkline";
import { getDatasetJson } from "../lib/api";

interface Shot {
  LOC_X?: number;
  LOC_Y?: number;
  EVENT_TYPE?: string;
  ACTION_TYPE?: string;
  PERIOD?: number;
}

function drawShots(canvas: HTMLCanvasElement, shots: Shot[]) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const W = canvas.width;
  const H = canvas.height;
  const sx = (x: number) => ((x + 250) / 500) * W;
  const sy = (y: number) => H - ((y + 50) / 475) * H;
  const sc = W / 500;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "#0c0a09";
  ctx.lineWidth = 2;
  ctx.strokeRect(sx(-250), sy(422), 500 * sc, 472 * sc);
  ctx.beginPath();
  ctx.arc(sx(0), sy(0), 7.5 * sc, 0, Math.PI * 2);
  ctx.stroke();
  ctx.strokeRect(sx(-80), sy(137.5), 160 * sc, 190 * sc);
  ctx.beginPath();
  ctx.arc(sx(0), sy(0), 237.5 * sc, Math.PI * 0.05, Math.PI * 0.95, false);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(sx(-220), sy(-47));
  ctx.lineTo(sx(-220), sy(92));
  ctx.moveTo(sx(220), sy(-47));
  ctx.lineTo(sx(220), sy(92));
  ctx.stroke();
  for (const s of shots) {
    if (typeof s.LOC_X !== "number" || typeof s.LOC_Y !== "number") continue;
    const made = (s.EVENT_TYPE || "").toLowerCase().includes("made");
    ctx.beginPath();
    ctx.arc(sx(s.LOC_X / 10), sy(s.LOC_Y / 10), 3, 0, Math.PI * 2);
    if (made) {
      ctx.fillStyle = "#0c0a09";
      ctx.fill();
    } else {
      ctx.strokeStyle = "#a8a29e";
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }
}

export default function ShotChart({
  playerId,
  season,
}: {
  playerId: string;
  season: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");
  const [zones, setZones] = useState<
    { zone: string; FGM: number; FGA: number; FG_PCT: number; share: number }[]
  >([]);

  useEffect(() => {
    if (!playerId) return;
    setError("");
    getDatasetJson("shots", { season, player_id: playerId })
      .then((res) => {
        if (!res.ok) {
          setError(String(res.error || "failed"));
          return;
        }
        const shots = (res.data || []) as Shot[];
        setCount(shots.length);
        setZones(zoneSplits(shots));
        if (ref.current) drawShots(ref.current, shots);
      })
      .catch((e) => setError(String(e)));
  }, [playerId, season]);

  if (!playerId) return null;
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div style={{ fontWeight: 500 }}>Shot chart</div>
      <div style={{ fontSize: 12, color: "#78716c" }}>
        {count} shots. Filled marks fell. Outlines missed.
      </div>
      {error && <div style={{ fontSize: 12, color: "#78716c" }}>{error}</div>}
      <canvas ref={ref} width={500} height={475} style={{ width: "100%", marginTop: 8 }} />
      {zones.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 12, color: "#78716c", marginBottom: 4 }}>
            Rim under 8 feet. Three beyond 23.75.
          </div>
          <DataTable rows={zones} />
        </div>
      )}
    </div>
  );
}

export function ShotChartCard() {
  const [playerId, setPlayerId] = useState("");
  const [season, setSeason] = useState("2025-26");
  const [active, setActive] = useState("");
  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input
          className="field"
          value={playerId}
          onChange={(e) => setPlayerId(e.target.value)}
          placeholder="player id, e.g. 2544"
          style={{ width: 200 }}
        />
        <input
          className="field"
          value={season}
          onChange={(e) => setSeason(e.target.value)}
          placeholder="season"
          style={{ width: 110 }}
        />
        <button className="pill-ghost" onClick={() => setActive(playerId)}>
          Plot
        </button>
      </div>
      <ShotChart playerId={active} season={season} />
    </div>
  );
}

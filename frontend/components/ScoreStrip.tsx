"use client";

import { useEffect, useState } from "react";
import { getDatasetJson } from "../lib/api";

interface Game {
  GAME_DATE_EST?: string;
  HOME_TEAM_ABBREVIATION?: string;
  VISITOR_TEAM_ABBREVIATION?: string;
  HOME_TEAM_PTS?: number;
  VISITOR_TEAM_PTS?: number;
  GAME_STATUS_TEXT?: string;
}

function yesterday(): string {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${m}/${day}/${d.getFullYear()}`;
}

export default function ScoreStrip() {
  const [games, setGames] = useState<Game[]>([]);

  useEffect(() => {
    getDatasetJson("scoreboard", { season: "2025-26", game_date: yesterday() })
      .then((res) => {
        if (res.ok && Array.isArray(res.data)) {
          setGames((res.data as Game[]).slice(0, 8));
        }
      })
      .catch(() => {});
  }, []);

  if (!games.length) return null;
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        overflowX: "auto",
        padding: "8px 0",
        marginBottom: 16,
      }}
    >
      {games.map((g, i) => (
        <div
          key={i}
          style={{
            flexShrink: 0,
            border: "1px solid #e8e6e5",
            borderRadius: 10,
            padding: "6px 12px",
            background: "#ffffff",
            fontSize: 12,
          }}
        >
          <span style={{ fontWeight: 500 }}>{g.VISITOR_TEAM_ABBREVIATION}</span>{" "}
          {g.VISITOR_TEAM_PTS ?? "-"}
          {"  "}
          <span style={{ fontWeight: 500 }}>{g.HOME_TEAM_ABBREVIATION}</span>{" "}
          {g.HOME_TEAM_PTS ?? "-"}
          <div style={{ fontSize: 10, color: "#a8a29e" }}>
            {g.GAME_STATUS_TEXT || "Final"}
          </div>
        </div>
      ))}
    </div>
  );
}

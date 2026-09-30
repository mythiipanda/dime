"use client";

import { useEffect, useMemo, useState } from "react";
import ExplorePanel, { PanelHeader } from "./ExplorePanel";
import Skeleton from "./Skeleton";
import { getDatasetJson, getQueryParam, resolveFirstPlayerId, resolvePlayers, setQueryParam } from "../lib/api";

interface ZoneRow {
  zone: string;
  fgm: number;
  fga: number;
  pct: number;
}

const SEASONS = [
  "2015-16",
  "2016-17",
  "2017-18",
  "2018-19",
  "2019-20",
  "2020-21",
  "2021-22",
  "2022-23",
  "2023-24",
  "2024-25",
];

function toNum(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function cleanRows(data: unknown): ZoneRow[] {
  if (!Array.isArray(data)) return [];
  const out: ZoneRow[] = [];
  for (const r of data) {
    if (typeof r !== "object" || r === null) continue;
    const rec = r as Record<string, unknown>;
    const zone = typeof rec.zone === "string" ? rec.zone : "";
    const fga = toNum(rec.FGA) ?? 0;
    const fgm = toNum(rec.FGM) ?? 0;
    const pctRaw = toNum(rec.FG_PCT);
    if (!zone || fga <= 0 || pctRaw === null) continue;
    out.push({ zone, fgm, fga, pct: pctRaw > 1.05 ? pctRaw / 100 : pctRaw });
  }
  return out.sort((a, b) => b.fga - a.fga);
}

export default function ZoneSplitsPanel({
  initialPlayerId,
  initialPlayerName,
}: {
  initialPlayerId?: string;
  initialPlayerName?: string;
}) {
  const [input, setInput] = useState<string>(() => getQueryParam("zone_pname") ?? initialPlayerName ?? "");
  const [playerId, setPlayerId] = useState<string>(() => getQueryParam("zone_player") ?? initialPlayerId ?? "");
  const [playerName, setPlayerName] = useState<string>(() => getQueryParam("zone_pname") ?? initialPlayerName ?? "");
  const [season, setSeason] = useState<string>(() => {
    const v = getQueryParam("zone_season");
    return v && SEASONS.includes(v) ? v : "2024-25";
  });
  const [zones, setZones] = useState<ZoneRow[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [error, setError] = useState("");
  const [suggest, setSuggest] = useState<{ id: number; name: string }[]>([]);

  const load = async (pid: string, s: string, label: string) => {
    const id = pid.trim();
    if (!id) return;
    setStatus("loading");
    setError("");
    setQueryParam("zone_player", id, true);
    if (label) setQueryParam("zone_pname", label, true);
    try {
      const res = await getDatasetJson("zone_splits", { season: s, player_id: id });
      if (!res.ok) {
        setZones([]);
        setStatus("error");
        setError(typeof res.error === "string" && res.error ? res.error : "shot data unavailable");
        return;
      }
      const rows = cleanRows(res.data);
      if (!rows.length) {
        setZones([]);
        setStatus("error");
        setError(`No shot rows for this player in ${s}.`);
        return;
      }
      setZones(rows);
      setStatus("ok");
    } catch (e) {
      setZones([]);
      setStatus("error");
      setError(e instanceof Error ? e.message : "request failed");
    }
  };

  useEffect(() => {
    const t = setTimeout(async () => {
      const q = input.trim();
      if (/^\d+$/.test(q) || q.length < 2) {
        setSuggest([]);
        return;
      }
      setSuggest(await resolvePlayers(q));
    }, 250);
    return () => clearTimeout(t);
  }, [input]);

  useEffect(() => {
    const pid = getQueryParam("zone_player") ?? initialPlayerId ?? "";
    const pname = getQueryParam("zone_pname") ?? initialPlayerName ?? "";
    const s = getQueryParam("zone_season");
    const startSeason = s && SEASONS.includes(s) ? s : "2024-25";
    setSeason(startSeason);
    if (pid.trim()) {
      setPlayerId(pid.trim());
      setPlayerName(pname);
      setInput(pname || pid.trim());
      load(pid.trim(), startSeason, pname);
    }
  }, []);

  const show = async () => {
    const q = input.trim();
    if (!q) return;
    if (/^\d+$/.test(q)) {
      setPlayerId(q);
      load(q, season, playerName);
      return;
    }
    const hits = await resolvePlayers(q, 1);
    const found = hits[0] ?? null;
    const id = found ? await resolveFirstPlayerId(q) : null;
    if (!found || !id) {
      setZones([]);
      setStatus("error");
      setError(`No player found for "${q}". Try a full name.`);
      return;
    }
    setPlayerId(String(id));
    setPlayerName(found.name);
    setInput(found.name);
    load(String(id), season, found.name);
  };

  const pickSeason = (s: string) => {
    setSeason(s);
    setQueryParam("zone_season", s, true);
    if (playerId.trim()) load(playerId.trim(), s, playerName);
  };

  const maxFga = useMemo(() => zones.reduce((m, z) => Math.max(m, z.fga), 0), [zones]);
  const totalFga = useMemo(() => zones.reduce((m, z) => m + z.fga, 0), [zones]);

  return (
    <ExplorePanel id="explore-zone-splits">
      <PanelHeader kicker="Shots" title="Shots by zone" />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input
          className="field"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") show();
          }}
          placeholder="Player name or id"
          style={{ width: 220, fontSize: 13 }}
          aria-label="Player name or id"
        />
        <select
          className="field"
          aria-label="Season"
          value={season}
          onChange={(e) => pickSeason(e.target.value)}
          style={{ fontSize: 13 }}
        >
          {SEASONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button className="pill-cta" style={{ fontSize: 12 }} onClick={show}>
          Show
        </button>
      </div>
      {suggest.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          {suggest.map((s) => (
            <button
              key={s.id}
              className="pill-ghost"
              style={{ fontSize: 12 }}
              onClick={() => {
                setPlayerId(String(s.id));
                setPlayerName(s.name);
                setInput(s.name);
                load(String(s.id), season, s.name);
              }}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
      {playerName && status !== "idle" && (
        <div style={{ marginTop: 10, fontSize: 12, color: "var(--color-warm-gray)" }}>
          {playerName}{playerId ? ` · ${season}` : ""}
        </div>
      )}
      <div style={{ marginTop: 8 }}>
        {status === "idle" && (
          <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
            Search a player to see shooting by zone.
          </div>
        )}
        {status === "loading" && <Skeleton lines={4} label="Loading zone splits" />}
        {status === "error" && (
          <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
            {error} Try another player or season.
          </div>
        )}
        {status === "ok" && zones.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div role="img" aria-label={`Field goal percentage by zone for ${playerName || playerId}`}>
              <div style={{ display: "flex", gap: 6, marginBottom: 6, fontSize: 11, color: "var(--color-ash-gray)", fontVariantNumeric: "tabular-nums" }}>
                <span>0%</span>
                <span style={{ marginLeft: "auto" }}>50%</span>
                <span style={{ marginLeft: "auto" }}>100%</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {zones.map((z) => (
                  <div key={z.zone}>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {z.zone}
                      </span>
                      <span style={{ marginLeft: "auto", fontSize: 13, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                        {(z.pct * 100).toFixed(1)}%
                      </span>
                      <span style={{ fontSize: 11, color: "var(--color-ash-gray)", fontVariantNumeric: "tabular-nums" }}>
                        {z.fgm}/{z.fga}
                      </span>
                    </div>
                    <div style={{ height: 8, borderRadius: 4, background: "var(--color-stone-border)", overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.round(z.pct * 100)}%`,
                          borderRadius: 4,
                          background: "var(--color-cyan-signal)",
                          opacity: maxFga > 0 ? 0.45 + 0.55 * (z.fga / maxFga) : 1,
                        }}
                      />
                    </div>
                    <div style={{ marginTop: 2, fontSize: 11, color: "var(--color-ash-gray)", fontVariantNumeric: "tabular-nums" }}>
                      {totalFga > 0 ? Math.round((z.fga / totalFga) * 100) : 0}% of attempts
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 8, fontSize: 11, color: "var(--color-ash-gray)" }}>
                Bar length is field goal percentage. Darker bars mean more attempts.
              </div>
            </div>
            <div
              className="dime-table table-scroll"
              style={{ border: "1px solid var(--color-stone-border)", borderRadius: 10, background: "var(--color-pure-white)", boxShadow: "var(--shadow-card)" }}
            >
              <table style={{ borderCollapse: "collapse", width: "100%", fontFamily: "var(--font-body)" }}>
                <thead>
                  <tr>
                    {["#", "Zone", "FGM", "FGA", "FG%"].map((h) => (
                      <th
                        key={h}
                        style={{
                          borderBottom: "1px solid var(--color-stone-border)",
                          padding: "7px 10px",
                          color: "var(--color-warm-gray)",
                          fontSize: 12,
                          fontWeight: 500,
                          textAlign: h === "Zone" ? "left" : "right",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {zones.map((z, i) => (
                    <tr key={z.zone}>
                      <td style={{ borderBottom: "1px solid var(--color-stone-border)", padding: "7px 10px", fontSize: 13, textAlign: "right", color: "var(--color-ash-gray)", fontVariantNumeric: "tabular-nums" }}>
                        {i + 1}
                      </td>
                      <td style={{ borderBottom: "1px solid var(--color-stone-border)", padding: "7px 10px", fontSize: 13, fontWeight: 500, textAlign: "left" }}>
                        {z.zone}
                      </td>
                      <td style={{ borderBottom: "1px solid var(--color-stone-border)", padding: "7px 10px", fontSize: 13, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {z.fgm}
                      </td>
                      <td style={{ borderBottom: "1px solid var(--color-stone-border)", padding: "7px 10px", fontSize: 13, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {z.fga}
                      </td>
                      <td style={{ borderBottom: "1px solid var(--color-stone-border)", padding: "7px 10px", fontSize: 13, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {(z.pct * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: "var(--color-ash-gray)" }}>
        Zone splits are player-scoped. Zones follow the warehouse shot tables for {season}.
      </div>
    </ExplorePanel>
  );
}

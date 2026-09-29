"use client";

import { useEffect, useState } from "react";
import AutoChart from "./AutoChart";
import CopyLink from "./CopyLink";
import DataTable from "./DataTable";
import ExplorePanel, { PanelHeader } from "./ExplorePanel";
import Skeleton from "./Skeleton";
import Sparkline from "./Sparkline";
import { ShotChartCard } from "./ShotChart";
import { datasetUrl, getDatasetJson, getQueryParam, resolveFirstPlayerId, resolvePlayers, setQueryParam } from "../lib/api";
import { STAT_CATEGORIES } from "../lib/exploreSearch";
import { freshDateLabel } from "../lib/freshness";
import { rankOf } from "../lib/rankContext";

const CATS: readonly string[] = STAT_CATEGORIES;

function usePreview() {
  const [rows, setRows] = useState<unknown>(null);
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (name: string, params: Record<string, string>) => {
    setError("");
    setBusy(true);
    try {
      const res = await getDatasetJson(name, params);
      if (!res.ok) {
        setError(String(res.error || "failed"));
        return;
      }
      setRows(res.data || []);
      setMeta((res.meta as Record<string, unknown>) || null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return { rows, meta, error, busy, run };
}

function Meta({ meta }: { meta: Record<string, unknown> | null }) {
  if (!meta) return null;
  const rows = Number(meta.rows ?? 0);
  const stamp = typeof meta.fetched_at === "string" ? freshDateLabel(meta.fetched_at) : null;
  return (
    <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 8 }}>
      {rows} rows{stamp ? ` · updated ${stamp}` : ""}
    </div>
  );
}

export function Leaders({
  initialStat,
  onPlayerSelect,
}: {
  initialStat?: string;
  onPlayerSelect?: (playerName: string) => void;
}) {
  const [cat, setCat] = useState("PTS");
  const p = usePreview();
  const show = (stat: string) => {
    setQueryParam("leaders_stat", stat, true);
    p.run("leaders", { season: "2025-26", stat });
  };
  useEffect(() => {
    
    


    const v = getQueryParam("leaders_stat");
    const start =
      initialStat && CATS.includes(initialStat)
        ? initialStat
        : v && CATS.includes(v)
          ? v
          : "PTS";
    setCat(start);
    show(start);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <ExplorePanel id="explore-leaders">
      <PanelHeader kicker="Stats" title="League leaders" action={<CopyLink panel="leaders" />} />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {CATS.map((c) => (
          <button
            key={c}
            onClick={() => {
              setCat(c);
              show(c);
            }}
            className={cat === c ? "tab-active" : "tab-idle"}
            style={{ fontSize: 12 }}
            aria-pressed={cat === c}
          >
            {c}
          </button>
        ))}
        <button
          className="pill-cta"
          style={{ fontSize: 12 }}
          disabled={p.busy}
          onClick={() => show(cat)}
        >
          {p.busy ? "Loading" : "Show"}
        </button>
        <a
          className="pill-ghost"
          style={{ fontSize: 12 }}
          href={datasetUrl("leaders", { season: "2025-26", stat: cat }, "csv")}
        >
          CSV
        </a>
      </div>
      {p.error && <div style={{ color: "var(--color-warm-gray)", marginTop: 8 }}>{p.error}</div>}
      <Meta meta={p.meta} />
      {p.rows === null && !p.error && <Skeleton lines={5} label="Loading leaders" />}
      {Array.isArray(p.rows) && p.rows.length > 0 && (
        <div className="leader-summary" aria-label={`${cat} leaders at a glance`}>
          {(p.rows as Record<string, unknown>[]).slice(0, 3).map((row, index) => {
            const name = String(row.PLAYER_NAME ?? row.PLAYER ?? row.player_name ?? row.name ?? `No. ${index + 1}`);
            const value = row[cat] ?? row[cat.toLowerCase()] ?? row.value ?? "—";
            
            


            const pct = rankOf(index, (p.rows as Record<string, unknown>[]).length).percentile;
            return (
              <div className="leader-summary-item" key={`${name}-${index}`}>
                <span className="leader-summary-rank">0{index + 1}</span>
                <strong>{String(value)}</strong>
                <span className="leader-summary-unit">{cat} · p{pct}</span>
                <span className="leader-summary-name" title={name}>{name}</span>
              </div>
            );
          })}
        </div>
      )}
      {p.rows !== null && (
        <div style={{ marginTop: 8 }}>
          <AutoChart table={{ rows: p.rows, meta: { stat_category: cat } }} />
          <DataTable rows={p.rows} storeKey="leaders" heat rankStat={cat} onPlayerSelect={onPlayerSelect} />
        </div>
      )}
    </ExplorePanel>
  );
}

export function Standings() {
  const [season, setSeason] = useState("2025-26");
  const p = usePreview();
  const show = (s: string) => {
    setQueryParam("standings_season", s, true);
    p.run("standings", { season: s });
  };
  useEffect(() => {
    const v = getQueryParam("standings_season");
    if (v) {
      setSeason(v);
      show(v);
    } else {
      

      show("2025-26");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <ExplorePanel id="explore-standings">
      <PanelHeader kicker="Season" title="Standings race" action={<CopyLink panel="leaders" anchor="standings" />} />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input
          className="field"
          value={season}
          onChange={(e) => setSeason(e.target.value)}
          placeholder="2025-26"
          style={{ width: 90, fontSize: 12 }}
          aria-label="Season"
        />
        <button
          className="pill-cta"
          style={{ fontSize: 12 }}
          disabled={p.busy}
          onClick={() => show(season)}
        >
          {p.busy ? "Loading" : "Show"}
        </button>
        <a
          className="pill-ghost"
          style={{ fontSize: 12 }}
          href={datasetUrl("standings", { season }, "csv")}
        >
          CSV
        </a>
      </div>
      {p.error && <div style={{ color: "var(--color-warm-gray)", marginTop: 8 }}>{p.error}</div>}
      <Meta meta={p.meta} />
      {p.rows === null && !p.error && <Skeleton lines={5} label="Loading standings" />}
      {p.rows !== null && (
        <div style={{ marginTop: 8 }}>
          <DataTable rows={p.rows} storeKey="standings" />
        </div>
      )}
    </ExplorePanel>
  );
}

export function Gamelog({ initialPlayer }: { initialPlayer?: string }) {
  const [idVal, setIdVal] = useState("");
  const [suggest, setSuggest] = useState<{ id: number; name: string }[]>([]);
  const p = usePreview();
  const show = (id: string) => {
    const raw = id.trim();
    if (!raw) return;
    if (/^\d+$/.test(raw)) {
      setQueryParam("gamelog_player", raw, true);
      p.run("player_gamelogs", { season: "2025-26", player_id: raw });
      return;
    }
    resolveFirstPlayerId(raw).then((found) => {
      if (!found) return;
      setIdVal(String(found));
      setQueryParam("gamelog_player", String(found), true);
      p.run("player_gamelogs", { season: "2025-26", player_id: String(found) });
    });
  };
  useEffect(() => {
    const q = idVal.trim();
    if (/^\d+$/.test(q) || q.length < 2) {
      setSuggest([]);
      return;
    }
    const t = setTimeout(async () => {
      setSuggest(await resolvePlayers(q));
    }, 250);
    return () => clearTimeout(t);
  }, [idVal]);
  useEffect(() => {
    const fromUrl = getQueryParam("gamelog_player");
    const start = (initialPlayer || fromUrl || "").trim();
    if (start) {
      setIdVal(start);
      show(start);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const list = Array.isArray(p.rows) ? (p.rows as Record<string, unknown>[]) : [];
  const pts = list.filter((r) => typeof r.PTS === "number").map((r) => Number(r.PTS));
  return (
    <ExplorePanel id="explore-gamelog">
      <PanelHeader kicker="Player" title="Game log trends" action={<CopyLink panel="shots" anchor="gamelog" />} />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input
          className="field"
          value={idVal}
          onChange={(e) => setIdVal(e.target.value)}
          placeholder="player id, e.g. 2544"
          style={{ width: 240 }}
          aria-label="Player name or id"
        />
        <button
          className="pill-cta"
          style={{ fontSize: 12 }}
          disabled={p.busy}
          onClick={() => show(idVal)}
        >
          {p.busy ? "Loading" : "Show"}
        </button>
      </div>
      {suggest.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          {suggest.map((s) => (
            <button
              key={s.id}
              className="pill-ghost"
              style={{ fontSize: 12 }}
              onClick={() => show(String(s.id))}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
      {p.error && <div style={{ color: "var(--color-warm-gray)", marginTop: 8 }}>{p.error}</div>}
      <Meta meta={p.meta} />
      {p.rows === null && !p.error && <Skeleton lines={5} label="Loading game log" />}
      {pts.length > 1 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 4 }}>
            Points, recent first
          </div>
          <Sparkline values={pts.slice(0, 20)} />
        </div>
      )}
      {p.rows !== null && (
        <div style={{ marginTop: 8 }}>
          <DataTable rows={p.rows} storeKey="gamelog" />
        </div>
      )}
    </ExplorePanel>
  );
}



export function LeadersPanel({
  initialStat,
  onPlayerSelect,
}: {
  initialStat?: string;
  onPlayerSelect?: (playerName: string) => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Leaders initialStat={initialStat} onPlayerSelect={onPlayerSelect} />
      <Standings />
    </div>
  );
}



export function ShotsPanel({ initialPlayer }: { initialPlayer?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <ExplorePanel id="explore-shots">
        <PanelHeader kicker="Stats" title="Shot chart" action={<CopyLink panel="shots" />} />
        <ShotChartCard initialPlayer={initialPlayer} />
      </ExplorePanel>
      <Gamelog initialPlayer={initialPlayer} />
    </div>
  );
}

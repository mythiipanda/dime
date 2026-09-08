"use client";

import { useEffect, useState } from "react";
import AutoChart from "./AutoChart";
import DataTable from "./DataTable";
import Sparkline from "./Sparkline";
import { ShotChartCard } from "./ShotChart";
import { datasetUrl, getDatasetJson, getQueryParam, resolveFirstPlayerId, resolvePlayers, setQueryParam } from "../lib/api";

const CATS = ["PTS", "REB", "AST", "STL", "BLK"];

function CopyLink() {
  const [done, setDone] = useState(false);
  return (
    <button
      className="pill-ghost"
      style={{ fontSize: 12 }}
      onClick={() => {
        if (typeof window === "undefined") return;
        navigator.clipboard
          .writeText(window.location.href)
          .then(() => {
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          })
          .catch(() => {});
      }}
    >
      {done ? "Copied" : "Copy link"}
    </button>
  );
}

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
  return (
    <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 8 }}>
      {String(meta.rows ?? 0)} rows
      {meta.source ? ` from ${String(meta.source)}` : ""}
      {meta.fetched_at ? ` at ${String(meta.fetched_at).slice(0, 10)}` : ""}
      {meta.cached ? " (cached)" : ""}
    </div>
  );
}

function Leaders() {
  const [cat, setCat] = useState("PTS");
  const p = usePreview();
  const show = (stat: string) => {
    setQueryParam("leaders_stat", stat, true);
    p.run("leaders", { season: "2025-26", stat });
  };
  useEffect(() => {
    const v = getQueryParam("leaders_stat");
    if (v && CATS.includes(v)) {
      setCat(v);
      show(v);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="card">
      <div className="display" style={{ fontSize: 20 }}>League leaders</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        {CATS.map((c) => (
          <button
            key={c}
            onClick={() => setCat(c)}
            className={cat === c ? "tab-active" : "tab-idle"}
            style={{ fontSize: 12 }}
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
        <CopyLink />
      </div>
      {p.error && <div style={{ color: "var(--color-warm-gray)", marginTop: 8 }}>{p.error}</div>}
      <Meta meta={p.meta} />
      {p.rows !== null && (
        <div style={{ marginTop: 8 }}>
          <AutoChart table={{ rows: p.rows, meta: { stat_category: cat } }} />
          <DataTable rows={p.rows} storeKey="leaders" heat />
        </div>
      )}
    </div>
  );
}

function Standings() {
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
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="card">
      <div className="display" style={{ fontSize: 20 }}>Standings race</div>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
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
        <CopyLink />
      </div>
      {p.error && <div style={{ color: "var(--color-warm-gray)", marginTop: 8 }}>{p.error}</div>}
      <Meta meta={p.meta} />
      {p.rows !== null && (
        <div style={{ marginTop: 8 }}>
          <DataTable rows={p.rows} storeKey="standings" />
        </div>
      )}
    </div>
  );
}

function Gamelog() {
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
    const v = getQueryParam("gamelog_player");
    if (v) {
      setIdVal(v);
      show(v);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const list = Array.isArray(p.rows) ? (p.rows as Record<string, unknown>[]) : [];
  const pts = list.filter((r) => typeof r.PTS === "number").map((r) => Number(r.PTS));
  return (
    <div className="card">
      <div className="display" style={{ fontSize: 20 }}>Game log trends</div>
      <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
        <input
          className="field"
          value={idVal}
          onChange={(e) => setIdVal(e.target.value)}
          placeholder="player name or id, e.g. LeBron or 2544"
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
        <CopyLink />
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
    </div>
  );
}

export default function DatasetPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div id="explore-leaders" style={{ scrollMarginTop: 16 }}>
        <Leaders />
      </div>
      <div id="explore-shots" style={{ scrollMarginTop: 16 }}>
        <ShotChartCard />
      </div>
      <Standings />
      <Gamelog />
    </div>
  );
}

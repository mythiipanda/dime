"use client";

import { useState } from "react";
import AutoChart from "./AutoChart";
import DataTable from "./DataTable";
import Sparkline from "./Sparkline";
import { ShotChartCard } from "./ShotChart";
import { datasetUrl, getDatasetJson } from "../lib/api";

const CATS = ["PTS", "REB", "AST", "STL", "BLK"];

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
    <div style={{ fontSize: 12, color: "#78716c", marginTop: 8 }}>
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
          onClick={() => p.run("leaders", { season: "2025-26", stat: cat })}
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
      {p.error && <div style={{ color: "#78716c", marginTop: 8 }}>{p.error}</div>}
      <Meta meta={p.meta} />
      {p.rows !== null && (
        <div style={{ marginTop: 8 }}>
          <AutoChart table={{ rows: p.rows, meta: { stat_category: cat } }} />
          <DataTable rows={p.rows} />
        </div>
      )}
    </div>
  );
}

function Standings() {
  const p = usePreview();
  return (
    <div className="card">
      <div className="display" style={{ fontSize: 20 }}>Standings race</div>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button
          className="pill-cta"
          style={{ fontSize: 12 }}
          disabled={p.busy}
          onClick={() => p.run("standings", { season: "2025-26" })}
        >
          {p.busy ? "Loading" : "Show"}
        </button>
        <a
          className="pill-ghost"
          style={{ fontSize: 12 }}
          href={datasetUrl("standings", { season: "2025-26" }, "csv")}
        >
          CSV
        </a>
      </div>
      {p.error && <div style={{ color: "#78716c", marginTop: 8 }}>{p.error}</div>}
      <Meta meta={p.meta} />
      {p.rows !== null && (
        <div style={{ marginTop: 8 }}>
          <DataTable rows={p.rows} />
        </div>
      )}
    </div>
  );
}

function Gamelog() {
  const [idVal, setIdVal] = useState("");
  const p = usePreview();
  const list = Array.isArray(p.rows) ? (p.rows as Record<string, unknown>[]) : [];
  const pts = list.filter((r) => typeof r.PTS === "number").map((r) => Number(r.PTS));
  return (
    <div className="card">
      <div className="display" style={{ fontSize: 20 }}>Game log trends</div>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <input
          className="field"
          value={idVal}
          onChange={(e) => setIdVal(e.target.value)}
          placeholder="player id, e.g. 2544"
          style={{ width: 180 }}
        />
        <button
          className="pill-cta"
          style={{ fontSize: 12 }}
          disabled={p.busy}
          onClick={() => p.run("player_gamelogs", { season: "2025-26", player_id: idVal })}
        >
          {p.busy ? "Loading" : "Show"}
        </button>
      </div>
      {p.error && <div style={{ color: "#78716c", marginTop: 8 }}>{p.error}</div>}
      <Meta meta={p.meta} />
      {pts.length > 1 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 12, color: "#78716c", marginBottom: 4 }}>
            Points, recent first
          </div>
          <Sparkline values={pts.slice(0, 20)} />
        </div>
      )}
      {p.rows !== null && (
        <div style={{ marginTop: 8 }}>
          <DataTable rows={p.rows} />
        </div>
      )}
    </div>
  );
}

export default function DatasetPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Leaders />
      <Standings />
      <Gamelog />
      <ShotChartCard />
    </div>
  );
}

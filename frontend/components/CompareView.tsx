"use client";

import { useState } from "react";
import DebateCardModal from "./DebateCardModal";

type Side = {
  player_id?: number;
  team_id?: number;
  gp?: number;
  games?: number;
  ppg?: number;
  top_lineup?: string;
  top_lineup_pm?: number;
  last5?: number[];
  on_off?: Record<string, unknown>;
};

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) {
    const first = v[0] as Record<string, unknown> | undefined;
    if (first && typeof first === "object" && "Stat" in first) {
      return (v as Record<string, unknown>[])
        .slice(0, 3)
        .map((x) => `${String(x.Stat)} ${String(x["On-Off"] ?? "")}`)
        .join(" · ");
    }
    return v.map((x) => fmt(x)).join(", ").slice(0, 80);
  }
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    if ("Stat" in o) return `${String(o.Stat)} ${String(o["On-Off"] ?? "")}`;
    return JSON.stringify(v).slice(0, 80);
  }
  return String(v).slice(0, 80);
}

type MetricRow = {
  metric?: string;
  label?: string;
  method?: string;
  a?: number | null;
  b?: number | null;
  leader?: string;
  note?: string;
};

function num(v: number | null | undefined): string {
  if (v === null || v === undefined) return "n/a";
  return String(Math.round(v * 10) / 10);
}

function MetricsView({ rows }: { rows: Record<string, unknown> }) {
  const metrics = (rows.metrics || []) as MetricRow[];
  const labelA = String(rows.a || "A");
  const labelB = String(rows.b || "B");
  const agreement = String(rows.agreement || "");
  const verdict = String(rows.verdict || "");
  const unavailable = (rows.unavailable || []) as { metric?: string }[];
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 8 }}>
        Metrics {agreement}: {verdict}
      </div>
      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", borderBottom: "1px solid #e8e6e5", padding: "4px 8px", color: "#78716c", fontWeight: 500 }}>
              Metric
            </th>
            <th style={{ textAlign: "left", borderBottom: "1px solid #e8e6e5", padding: "4px 8px", color: "#78716c", fontWeight: 500 }}>
              {labelA}
            </th>
            <th style={{ textAlign: "left", borderBottom: "1px solid #e8e6e5", padding: "4px 8px", color: "#78716c", fontWeight: 500 }}>
              {labelB}
            </th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={String(m.metric)}>
              <td style={{ borderBottom: "1px solid #e8e6e5", padding: "4px 8px", color: "#78716c" }}>
                {String(m.label)}
              </td>
              <td style={{ borderBottom: "1px solid #e8e6e5", padding: "4px 8px", fontWeight: m.leader === "a" ? 600 : 400 }}>
                {num(m.a)}
              </td>
              <td style={{ borderBottom: "1px solid #e8e6e5", padding: "4px 8px", fontWeight: m.leader === "b" ? 600 : 400 }}>
                {num(m.b)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {unavailable.length > 0 && (
        <div style={{ fontSize: 11, color: "var(--color-warm-gray)", marginTop: 8 }}>
          Not in warehouse: {unavailable.map((u) => String(u.metric)).join(", ")}
        </div>
      )}
    </div>
  );
}

export default function CompareView({ rows, onDebate }: { rows: unknown; onDebate?: (a: string, b: string) => void }) {
  const [debateOpen, setDebateOpen] = useState(false);
  if (!rows || typeof rows !== "object") return null;
  const r = rows as Record<string, unknown>;
  if (Array.isArray(r.metrics)) return <MetricsView rows={r} />;
  const a = r.a as Side | undefined;
  const b = r.b as Side | undefined;
  if (!a || !b) return null;
  const labelA = (a as Record<string, unknown>).name as string || "A";
  const labelB = (b as Record<string, unknown>).name as string || "B";
  const keys = Array.from(
    new Set([...Object.keys(a), ...Object.keys(b)]),
  ).filter((k) => k !== "player_id" && k !== "team_id" && k !== "name");
  const prob = (r.win_prob || {}) as Record<string, number>;
  const names = Object.keys(prob);
  const fit = r.fit as { fit?: string; note?: string } | undefined;
  const pair = r.pair as { teammates?: boolean; both_on_net?: number | null; both_on_minutes?: number; note?: string } | undefined;
  return (
    <div style={{ marginTop: 8, minWidth: 0, maxWidth: "100%", overflowWrap: "break-word" }}>
      <button
        type="button"
        className="pill-ghost"
        style={{ fontSize: 12, marginBottom: 8, minHeight: 40 }}
        onClick={() => {
          if (onDebate) onDebate(labelA, labelB);
          else setDebateOpen(true);
        }}
      >
        Debate
      </button>
      {debateOpen && (
        <DebateCardModal
          initialA={labelA}
          initialB={labelB}
          onClose={() => setDebateOpen(false)}
        />
      )}
      {fit && fit.note && (
        <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 8 }}>
          Fit {fit.fit}: {fit.note}
        </div>
      )}
      {pair && pair.teammates && pair.note && (
        <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 8 }}>
          Together: {pair.note}
        </div>
      )}
      <div className="table-scroll" style={{ overflowX: "auto", maxWidth: "100%", WebkitOverflowScrolling: "touch" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 480, fontSize: 12 }}>
        <thead>
          <tr>
            <th
              style={{
                textAlign: "left",
                borderBottom: "1px solid #e8e6e5",
                padding: "8px 10px",
                color: "#78716c",
                fontWeight: 500,
                verticalAlign: "top",
                overflowWrap: "break-word",
              }}
            >
              Metric
            </th>
            <th
              style={{
                textAlign: "left",
                borderBottom: "1px solid #e8e6e5",
                padding: "8px 10px",
                color: "#78716c",
                fontWeight: 500,
                verticalAlign: "top",
                overflowWrap: "break-word",
              }}
            >
              {labelA}
            </th>
            <th
              style={{
                textAlign: "left",
                borderBottom: "1px solid #e8e6e5",
                padding: "8px 10px",
                color: "#78716c",
                fontWeight: 500,
                verticalAlign: "top",
                overflowWrap: "break-word",
              }}
            >
              {labelB}
            </th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => (
            <tr key={k}>
              <td style={{ borderBottom: "1px solid #e8e6e5", padding: "8px 10px", color: "#78716c", verticalAlign: "top", overflowWrap: "break-word" }}>
                {k}
              </td>
              <td style={{ borderBottom: "1px solid #e8e6e5", padding: "8px 10px", verticalAlign: "top", overflowWrap: "break-word" }}>
                {fmt(a[k as keyof Side])}
              </td>
              <td style={{ borderBottom: "1px solid #e8e6e5", padding: "8px 10px", verticalAlign: "top", overflowWrap: "break-word" }}>
                {fmt(b[k as keyof Side])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {names.length === 2 && (
        <div style={{ marginTop: 8, minWidth: 0 }}>
          <div style={{ display: "flex", height: 10, borderRadius: 9999, overflow: "hidden" }}>
            <div style={{ width: `${(prob[names[0]] || 0) * 100}%`, background: "#0c0a09" }} />
            <div style={{ flex: 1, background: "#e8e6e5" }} />
          </div>
          <div style={{ fontSize: 12, color: "#78716c", marginTop: 4, overflowWrap: "break-word" }}>
            {names[0]} {Math.round((prob[names[0]] || 0) * 100)} pct vs {names[1]}{" "}
            {Math.round((prob[names[1]] || 0) * 100)} pct
          </div>
        </div>
      )}
    </div>
  );
}

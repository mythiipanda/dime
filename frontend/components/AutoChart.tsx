"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Row = Record<string, unknown>;

const num = (v: unknown) => (typeof v === "number" ? v : Number(v) || 0);
const str = (v: unknown) => (v === null || v === undefined ? "" : String(v));

function rowsOf(t: { rows?: unknown }): Row[] {
  const r = t.rows as unknown;
  if (Array.isArray(r)) return r as Row[];
  if (r && typeof r === "object") {
    const first = Object.values(r as Record<string, unknown>).find((v) =>
      Array.isArray(v),
    );
    if (Array.isArray(first)) return first as Row[];
  }
  return [];
}

export function trendData(rows: Row[]): { label: string; PTS: number }[] | null {
  if (!rows.length || !("PTS" in rows[0] && "GAME_DATE" in rows[0])) return null;
  return rows.slice(0, 15).reverse().map((r) => ({
    label: str(r.GAME_DATE).slice(0, 6),
    PTS: num(r.PTS),
  }));
}

export function leadersData(
  rows: Row[],
  stat = "PTS",
): { label: string; value: number }[] | null {
  if (!rows.length || !("PLAYER" in rows[0] && stat in rows[0])) return null;
  if ("GAME_DATE" in rows[0]) return null;
  return rows.slice(0, 10).map((r) => ({
    label: str(r.PLAYER).split(" ").slice(-1)[0],
    value: num(r[stat]),
  }));
}

export function zoneData(
  rows: Row[],
): { label: string; FG_PCT: number }[] | null {
  if (!rows.length || !("zone" in rows[0] && "FG_PCT" in rows[0])) return null;
  return rows.map((r) => ({ label: str(r.zone), FG_PCT: num(r.FG_PCT) }));
}

const AXIS = { fontSize: 11, fill: "#78716c" } as const;

export default function AutoChart({
  table,
}: {
  table: { rows?: unknown; meta?: { stat_category?: string } };
}) {
  const rows = rowsOf(table);
  const stat = table.meta?.stat_category || "PTS";
  const trend = trendData(rows);
  if (trend) {
    return (
      <div style={{ marginTop: 8 }}>
        <div style={{ fontSize: 12, color: "#78716c", marginBottom: 4 }}>
          Points by game
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={trend}>
            <CartesianGrid stroke="#e8e6e5" vertical={false} />
            <XAxis dataKey="label" tick={AXIS} interval={2} />
            <YAxis tick={AXIS} width={30} />
            <Tooltip />
            <Line type="monotone" dataKey="PTS" stroke="#3ba6f1" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }
  const lead = leadersData(rows, stat);
  if (lead) {
    return (
      <div style={{ marginTop: 8 }}>
        <div style={{ fontSize: 12, color: "#78716c", marginBottom: 4 }}>
          Top {stat}
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={lead} layout="vertical">
            <CartesianGrid stroke="#e8e6e5" horizontal={false} />
            <XAxis type="number" tick={AXIS} />
            <YAxis type="category" dataKey="label" tick={AXIS} width={70} />
            <Tooltip />
            <Bar dataKey="value" fill="#0c0a09" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }
  const zone = zoneData(rows);
  if (zone) {
    return (
      <div style={{ marginTop: 8 }}>
        <div style={{ fontSize: 12, color: "#78716c", marginBottom: 4 }}>
          Efficiency by zone
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={zone}>
            <CartesianGrid stroke="#e8e6e5" vertical={false} />
            <XAxis dataKey="label" tick={AXIS} />
            <YAxis tick={AXIS} width={36} domain={[0, 1]} />
            <Tooltip />
            <Bar dataKey="FG_PCT" fill="#3ba6f1" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }
  return null;
}

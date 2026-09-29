"use client";

import { clamp, ordinal } from "../../lib/viz";

export interface PercentileRow {
  label: string;
  value: string;
  percentile: number;
}

export default function PercentileBars({
  rows,
  note,
}: {
  rows: PercentileRow[];
  note?: string;
}) {
  const sorted = [...rows].sort((a, b) => b.percentile - a.percentile);
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 500, color: "var(--color-ink-black)" }}>
        Percentiles
      </div>
      <div style={{ marginTop: 10 }}>
        {sorted.map((r) => (
          <div key={r.label} style={{ marginBottom: 14 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
              }}
            >
              <span style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>{r.label}</span>
              <span style={{ fontSize: 13, color: "var(--color-ink-black)" }}>
                <span style={{ fontSize: 16, fontWeight: 500 }}>{r.value}</span>
                <span style={{ color: "var(--color-ash-gray)", marginLeft: 8 }}>
                  {ordinal(Math.round(clamp(r.percentile, 0, 100)))}
                </span>
              </span>
            </div>
            <div
              style={{
                marginTop: 6,
                height: 6,
                borderRadius: 3,
                background: "var(--color-stone-border)",
              }}
            >
              <div
                style={{
                  width: `${clamp(r.percentile, 0, 100)}%`,
                  height: "100%",
                  borderRadius: 3,
                  background: "var(--color-soot)",
                }}
              />
            </div>
          </div>
        ))}
      </div>
      {note && (
        <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 2 }}>{note}</div>
      )}
    </div>
  );
}

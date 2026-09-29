"use client";

export interface TrendPoint {
  label: string;
  value: number;
}

const W = 340;
const H = 64;
const PAD = 6;

export default function StatTrend({
  label,
  points,
  format,
  windowLabel,
}: {
  label: string;
  points: TrendPoint[];
  format: (v: number) => string;
  windowLabel: string;
}) {
  if (points.length < 2) return null;
  const values = points.map((p) => p.value);
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  const last = values[values.length - 1];
  const delta = last - avg;

  const min = Math.min(...values, avg);
  const max = Math.max(...values, avg);
  const span = max - min || 1;
  const lo = min - span * 0.18;
  const hi = max + span * 0.18;
  const px = (i: number) => PAD + (i / (values.length - 1)) * (W - PAD * 2);
  const py = (v: number) => H - PAD - ((v - lo) / (hi - lo)) * (H - PAD * 2);
  const d = values
    .map((v, i) => `${i ? "L" : "M"}${px(i).toFixed(1)},${py(v).toFixed(1)}`)
    .join(" ");
  const avgY = py(avg);
  const deltaText = `${delta >= 0 ? "+" : "-"}${format(Math.abs(delta))} vs avg`;

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
        }}
      >
        <span style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>{label}</span>
        <span style={{ fontSize: 13, color: "var(--color-ink-black)" }}>
          <span style={{ fontSize: 18, fontWeight: 500 }}>{format(last)}</span>
          <span style={{ color: "var(--color-ash-gray)", marginLeft: 8 }}>{deltaText}</span>
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${label} over recent games`}
        style={{ width: "100%", height: "auto", display: "block", marginTop: 6 }}
      >
        <line
          x1={PAD}
          x2={W - PAD}
          y1={avgY}
          y2={avgY}
          stroke="var(--color-stone-muted)"
          strokeWidth={1}
          strokeDasharray="3 3"
        >
          <title>{`Average ${format(avg)}`}</title>
        </line>
        <path d={d} fill="none" stroke="var(--color-soot)" strokeWidth={2} />
        <circle cx={px(values.length - 1)} cy={py(last)} r={3.5} fill="var(--color-ink-black)" />
      </svg>
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 4 }}>
        {windowLabel} Dashed line is the average.
      </div>
    </div>
  );
}

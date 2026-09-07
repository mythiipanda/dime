"use client";

export default function Sparkline({
  values,
  width = 300,
  height = 48,
}: {
  values: number[];
  width?: number;
  height?: number;
}) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const px = (i: number) => (i / (values.length - 1)) * (width - 4) + 2;
  const py = (v: number) => height - 4 - ((v - min) / span) * (height - 8);
  const d = values.map((v, i) => `${i ? "L" : "M"}${px(i)},${py(v)}`).join(" ");
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <path d={d} fill="none" stroke="#3ba6f1" strokeWidth={2} />
      {values.map((v, i) => (
        <circle key={i} cx={px(i)} cy={py(v)} r={2} fill="#0c0a09" />
      ))}
    </svg>
  );
}

export function zoneSplits(
  rows: { LOC_X?: number; LOC_Y?: number; EVENT_TYPE?: string }[],
): { zone: string; FGM: number; FGA: number; FG_PCT: number; share: number }[] {
  const zones: Record<string, [number, number]> = { rim: [0, 0], mid: [0, 0], three: [0, 0] };
  for (const r of rows) {
    if (typeof r.LOC_X !== "number" || typeof r.LOC_Y !== "number") continue;
    const dist = Math.hypot(r.LOC_X, r.LOC_Y) / 10;
    const made = (r.EVENT_TYPE || "").toLowerCase().startsWith("made");
    const z = dist < 8 ? "rim" : dist > 23.75 ? "three" : "mid";
    zones[z][1] += 1;
    if (made) zones[z][0] += 1;
  }
  const total = Object.values(zones).reduce((a, [, n]) => a + n, 0) || 1;
  return Object.entries(zones).map(([zone, [m, a]]) => ({
    zone,
    FGM: m,
    FGA: a,
    FG_PCT: a ? Math.round((m / a) * 1000) / 1000 : 0,
    share: Math.round((a / total) * 1000) / 1000,
  }));
}

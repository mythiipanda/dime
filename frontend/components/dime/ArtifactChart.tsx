"use client";

export type ChartSeries = { name: string; tone?: "ink" | "muted"; values: number[] };

export default function ArtifactChart({
  series,
  height = 180,
  footnote,
  unit = "pts",
  xLabels,
}: {
  series: ChartSeries[];
  height?: number;
  footnote?: string;
  unit?: string;
  xLabels?: string[];
}) {
  const W = 720;
  const H = height;
  const PAD = 10;
  const LABEL_W = 30;
  const BOTTOM_PAD = xLabels && xLabels.length > 0 ? 18 : 0;
  const all = series.flatMap((s) => s.values);
  const rawMin = Math.min(...all);
  const rawMax = Math.max(...all);
  const lo = Math.floor(rawMin / 5) * 5;
  const hi = Math.ceil((rawMax + 0.5) / 5) * 5;
  const span = Math.max(hi - lo, 5);
  const n = Math.max(...series.map((s) => s.values.length));
  const x0 = PAD + LABEL_W;
  const x = (i: number) => x0 + (i / Math.max(n - 1, 1)) * (W - x0 - PAD);
  const y = (v: number) => PAD + (1 - (v - lo) / span) * (H - PAD * 2 - BOTTOM_PAD);
  const line = (vals: number[]) =>
    vals.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

  const mid = (lo + hi) / 2;
  const ticks = [hi, mid, lo];
  const unitSuffix = unit ? ` ${unit}` : "";

  return (
    <div className="px-4 py-3">
      <div className="flex items-center gap-4">
        {series.map((s, i) => {
          const isInk = s.tone === "ink" || (s.tone === undefined && i === 0);
          return (
            <span key={s.name} className="flex items-center gap-1.5 text-[11.5px] text-ink-2">
              <span className={`h-[2px] w-4 rounded-full ${isInk ? "bg-ink" : "bg-ink-3"}`} />
              {s.name}
            </span>
          );
        })}
        <span className="ml-auto font-mono text-[11px] tabular-nums text-ink-3">
          {rawMin.toFixed(0)}–{rawMax.toFixed(0)}{unitSuffix}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full" role="img" aria-label="Scoring trend chart">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x0} x2={W - PAD} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
            <text
              x={x0 - 6} y={y(t) + 3} textAnchor="end"
              fontSize={9} fontFamily="var(--font-mono)" fill="var(--ink-3)"
            >
              {Number.isInteger(t) ? t : t.toFixed(1)}
            </text>
          </g>
        ))}
        {xLabels && xLabels.slice(0, n).map((label, i) => (
          <text
            key={i}
            x={x(i)}
            y={H - 4}
            textAnchor="middle"
            fontSize={9}
            fontFamily="var(--font-mono)"
            fill="var(--ink-3)"
          >
            {label}
          </text>
        ))}
        {series.map((s, i) => {
          const last = s.values[s.values.length - 1];
          const isInk = s.tone === "ink" || (s.tone === undefined && i === 0);
          return (
            <g key={s.name}>
              <path
                d={line(s.values)}
                fill="none"
                stroke={isInk ? "var(--ink)" : "var(--ink-3)"}
                strokeWidth={isInk ? 1.5 : 1.25}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={isInk ? undefined : "4 3"}
              />
              <circle
                cx={x(s.values.length - 1)} cy={y(last)} r={3}
                fill={isInk ? "var(--ink)" : "var(--ink-3)"}
                stroke="var(--surface)" strokeWidth={1.5}
              />
              <text
                x={Math.min(x(s.values.length - 1) + 7, W - PAD - 18)} y={y(last) + 3.5}
                fontSize={10} fontWeight={600} fontFamily="var(--font-mono)"
                fill={isInk ? "var(--ink)" : "var(--ink-2)"}
              >
                {last.toFixed(0)}
              </text>
            </g>
          );
        })}
      </svg>
      {footnote && <div className="mt-1 font-mono text-[11px] text-ink-3">{footnote}</div>}
    </div>
  );
}

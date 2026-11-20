"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartSeriesPayload, ChartTone } from "@/lib/dime-stream";
import ArtifactTable from "./ArtifactTable";

export type ChartSeries = ChartSeriesPayload;

const toneColor: Record<ChartTone, string> = { ink: "var(--ink)", muted: "var(--ink-3)", accent: "var(--accent-ink)", good: "var(--green)", warn: "var(--orange)" };

export default function ArtifactChart({ series, height = 220, footnote, unit, xLabels, title = "Trend chart" }: {
  series: ChartSeries[];
  height?: number;
  footnote?: string;
  unit?: string;
  xLabels?: string[];
  title?: string;
}) {
  const count = Math.max(0, ...series.map(s => s.values.length));
  const data = Array.from({ length: count }, (_, i) => Object.fromEntries([
    ["label", xLabels?.[i] || `Observation ${i + 1}`], ...series.map((s, j) => [`series${j}`, s.values[i] ?? null]),
  ]));
  return <figure className="min-w-0 p-4" aria-label={title}>
    <figcaption className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-2">
      {series.map((s, i) => <span key={i} className="inline-flex min-w-0 items-center gap-2 break-words"><span aria-hidden="true" className="w-4 shrink-0 border-t-2" style={{ borderColor: toneColor[s.tone ?? (i === 0 ? "ink" : "muted")], borderTopStyle: i % 2 ? "dashed" : "solid" }} />{s.name}</span>)}
      <span className="text-ink-3">{unit || "Unit not declared"}</span>
    </figcaption>
    <ResponsiveContainer width="100%" height={height} minWidth={0} initialDimension={{ width: 640, height }}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }} accessibilityLayer>
        <CartesianGrid vertical={false} stroke="var(--line)" />
        <XAxis dataKey="label" tick={{ fill: "var(--ink-3)", fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={24} />
        <YAxis tick={{ fill: "var(--ink-3)", fontSize: 11 }} tickLine={false} axisLine={false} width={48} domain={["auto", "auto"]} />
        <Tooltip contentStyle={{ background: "var(--surface)", borderColor: "var(--line)", borderRadius: 8, fontSize: 12, color: "var(--ink)" }} isAnimationActive={false} />
        {series.map((s, i) => <Line key={i} type="linear" dataKey={`series${i}`} name={s.name} stroke={toneColor[s.tone ?? (i === 0 ? "ink" : "muted")]} strokeWidth={2} strokeDasharray={i % 2 ? "4 3" : undefined} dot={count <= 12} connectNulls={false} isAnimationActive={false} />)}
      </LineChart>
    </ResponsiveContainer>
    {footnote && <p className="mt-2 break-words text-xs leading-relaxed text-ink-3">{footnote}</p>}
    <details className="mt-3 text-xs text-ink-2"><summary className="cursor-pointer py-2">View chart data</summary>
      <ArtifactTable title={`${title} data`} columns={[{ key: "label", label: "Observation" }, ...series.map((s, i) => ({ key: `series${i}`, label: `${s.name}${unit ? ` (${unit})` : ""}`, numeric: true }))]} rows={data.map(row => [String(row.label), ...series.map((_, i) => row[`series${i}`] as number | null)])} />
    </details>
  </figure>;
}

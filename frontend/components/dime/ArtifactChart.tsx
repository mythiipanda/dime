"use client";

import { Bar, BarChart, CartesianGrid, LabelList, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartAnnotation, ChartMark, ChartSeriesPayload, ChartTone } from "@/lib/dime-stream";
import ArtifactTable from "./ArtifactTable";
import { QuietDetails } from "@/components/ds/QuietDetails";

export type ChartSeries = ChartSeriesPayload;

const toneColor: Record<ChartTone, string> = { ink: "var(--ink)", muted: "var(--ink-3)", accent: "var(--accent-ink)", good: "var(--green)", warn: "var(--orange)" };

export default function ArtifactChart({ series, height = 220, footnote, unit, xLabels, xLabel, yLabel, subtitle, variant = "line", marks, annotations, labelValues, title = "Trend chart" }: {
  series: ChartSeries[];
  height?: number;
  footnote?: string;
  unit?: string;
  xLabels?: string[];
  xLabel?: string;
  yLabel?: string;
  subtitle?: string;
  variant?: "line" | "bar";
  marks?: ChartMark[];
  annotations?: ChartAnnotation[];
  labelValues?: boolean;
  title?: string;
}) {
  const count = Math.max(0, ...series.map(s => s.values.length));
  const data = Array.from({ length: count }, (_, i) => Object.fromEntries([
    ["label", xLabels?.[i] || `Observation ${i + 1}`], ...series.map((s, j) => [`series${j}`, s.values[i] ?? null]),
  ]));
  const numbered = variant === "bar" && count > 8;
  const rows = variant === "bar"
    ? data.map((row, i) => (numbered ? { ...row, label: `${i + 1}. ${row.label}` } : row))
    : data;
  const barHeight = Math.max(height, count * 34 + 48);
  const chartHeight = variant === "bar" ? barHeight : height;
  const annotationRows = (annotations ?? []).filter(a => a.index >= 0 && a.index < count);
  return <figure className="min-w-0 p-4" aria-label={title}>
    {subtitle && <p className="mb-2 break-words text-xs text-ink-3">{subtitle}</p>}
    <figcaption className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-2">
      {series.map((s, i) => <span key={i} className="inline-flex min-w-0 items-center gap-2 break-words"><span aria-hidden="true" className="w-4 shrink-0 border-t-2" style={{ borderColor: toneColor[s.tone ?? (i === 0 ? "ink" : "muted")], borderTopStyle: i % 2 ? "dashed" : "solid" }} />{s.name}{s.unit ? <span className="text-ink-3">({s.unit})</span> : null}</span>)}
      {!series.some(s => s.unit) && unit ? <span className="text-ink-3">{unit}</span> : null}
      {(marks ?? []).map((m, i) => <span key={`mark-legend-${i}`} className="inline-flex min-w-0 items-center gap-2 break-words text-ink-3"><span aria-hidden="true" className="w-4 shrink-0 border-t-2 border-dashed" style={{ borderColor: "var(--ink-3)" }} />{m.label}</span>)}
    </figcaption>
    <ResponsiveContainer width="100%" height={chartHeight} minWidth={0} initialDimension={{ width: 640, height: chartHeight }}>
      {variant === "bar"
        ? <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 56, bottom: 8, left: 0 }} accessibilityLayer>
            <CartesianGrid horizontal={false} stroke="var(--line)" />
            <XAxis type="number" tick={{ fill: "var(--ink-3)", fontSize: 11 }} tickLine={false} axisLine={false} label={xLabel ? { value: xLabel, position: "insideBottom", offset: -4, fill: "var(--ink-3)", fontSize: 11 } : undefined} />
            <YAxis type="category" dataKey="label" width={numbered ? 150 : 132} tick={{ fill: "var(--ink)", fontSize: 11 }} tickLine={false} axisLine={false} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: "var(--ink-3)", fontSize: 11 } : undefined} />
            <Tooltip contentStyle={{ background: "var(--surface)", borderColor: "var(--line)", borderRadius: 8, fontSize: 12, color: "var(--ink)" }} isAnimationActive={false} />
            {(marks ?? []).map((m, i) => <ReferenceLine key={`mark-${i}`} x={m.value} stroke="var(--ink-3)" strokeDasharray="4 3" />)}
            {series.map((s, i) => <Bar key={i} dataKey={`series${i}`} name={s.name} fill={toneColor[s.tone ?? (i === 0 ? "ink" : "muted")]} isAnimationActive={false}>
              {labelValues && <LabelList dataKey={`series${i}`} position="right" style={{ fill: "var(--ink-2)", fontSize: 11 }} />}
            </Bar>)}
          </BarChart>
        : <LineChart data={rows} margin={{ top: 8, right: 12, bottom: xLabel ? 16 : 8, left: yLabel ? 12 : 0 }} accessibilityLayer>
            <CartesianGrid vertical={false} stroke="var(--line)" />
            <XAxis dataKey="label" tick={{ fill: "var(--ink-3)", fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={24} label={xLabel ? { value: xLabel, position: "insideBottom", offset: -8, fill: "var(--ink-3)", fontSize: 11 } : undefined} />
            <YAxis tick={{ fill: "var(--ink-3)", fontSize: 11 }} tickLine={false} axisLine={false} width={48} domain={["auto", "auto"]} label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", fill: "var(--ink-3)", fontSize: 11 } : undefined} />
            <Tooltip contentStyle={{ background: "var(--surface)", borderColor: "var(--line)", borderRadius: 8, fontSize: 12, color: "var(--ink)" }} isAnimationActive={false} />
            {(marks ?? []).map((m, i) => <ReferenceLine key={`mark-${i}`} y={m.value} stroke="var(--ink-3)" strokeDasharray="4 3" />)}
            {series.map((s, i) => <Line key={i} type="linear" dataKey={`series${i}`} name={s.name} stroke={toneColor[s.tone ?? (i === 0 ? "ink" : "muted")]} strokeWidth={2} strokeDasharray={i % 2 ? "4 3" : undefined} dot={count <= 12 || labelValues} connectNulls={false} isAnimationActive={false}>
              {labelValues && <LabelList dataKey={`series${i}`} position="top" style={{ fill: "var(--ink-2)", fontSize: 10 }} />}
            </Line>)}
          </LineChart>}
    </ResponsiveContainer>
    {annotationRows.length > 0 && <ul className="mt-2 space-y-1">
      {annotationRows.map((a, i) => <li key={i} className="flex items-start gap-2 break-words text-xs text-ink-2"><span aria-hidden="true" className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: "var(--accent-ink)" }} /><span><span className="font-medium text-ink">{String(data[a.index]?.label ?? "")}:</span> {a.text}</span></li>)}
    </ul>}
    {footnote && <p className="mt-2 break-words text-xs leading-relaxed text-ink-3">{footnote}</p>}
    <QuietDetails label="View chart data">
      <ArtifactTable title={`${title} data`} columns={[{ key: "label", label: "Observation" }, ...series.map((s, i) => ({ key: `series${i}`, label: `${s.name}${s.unit ? ` (${s.unit})` : unit ? ` (${unit})` : ""}`, numeric: true }))]} rows={data.map(row => [String(row.label), ...series.map((_, i) => row[`series${i}`] as number | null)])} />
    </QuietDetails>
  </figure>;
}

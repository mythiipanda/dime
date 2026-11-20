"use client";

import type { ReactNode } from "react";
import ArtifactChart, { type ChartSeries } from "@/components/dime/ArtifactChart";
import ArtifactCompare from "@/components/dime/ArtifactCompare";
import ArtifactScatter from "@/components/dime/ArtifactScatter";
import ArtifactShell from "@/components/dime/ArtifactShell";
import ArtifactShotChart from "@/components/dime/ArtifactShotChart";
import ArtifactTable from "@/components/dime/ArtifactTable";
import ArtifactMemo from "@/components/dime/ArtifactMemo";
import ArtifactPlayerCard from "@/components/dime/ArtifactPlayerCard";
import PinButton from "@/components/dime/PinButton";
import {
  memoToMarkdown,
  originPhrase,
  undeclaredProvenance,
  type ChartSeriesPayload,
  type DimeArtifact,
  type DimeProvenance,
  type ProvenanceEvidence,
} from "@/lib/dime-stream";

function toChartSeries(series: ChartSeriesPayload[]): ChartSeries[] {
  return series
    .filter((s) => s.values.length > 0)
    .map((s) => ({
      name: s.name,
      values: s.values,
      ...(s.tone ? { tone: s.tone } : {}),
    }));
}

export function ArtifactBody({ artifact }: { artifact: DimeArtifact }) {
  if (artifact.kind === "memo") return artifact.sections ? <ArtifactMemo artifact={artifact} /> : <div className="p-4"><p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink">{artifact.text}</p></div>;
  if (artifact.kind === "player_card") return <ArtifactPlayerCard artifact={artifact} />;
  if (artifact.kind === "table") {
    return <ArtifactTable columns={artifact.columns} rows={artifact.rows} title={artifact.title} />;
  }
  if (artifact.kind === "compare") {
    return (
      <ArtifactCompare
        rows={artifact.rows.map((r) => ({
          label: r.label,
          a: r.a,
          b: r.b,
          fmt: (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1)),
        }))}
        aName={artifact.aName}
        bName={artifact.bName}
      />
    );
  }
  if (artifact.kind === "chart") {
    const series = toChartSeries(artifact.series);
    if (!series.length) return null;
    return (
      <ArtifactChart
        title={artifact.title}
        series={series}
        footnote={artifact.footnote}
        unit={artifact.unit}
        xLabels={artifact.xLabels}
      />
    );
  }
  if (artifact.kind === "shot_chart") {
    if (!artifact.zones.length) return null;
    return <ArtifactShotChart zones={artifact.zones} footnote={artifact.footnote} />;
  }
  if (artifact.kind === "scatter") {
    if (!artifact.points.length) return null;
    return (
      <ArtifactScatter
        xLabel={artifact.xLabel}
        yLabel={artifact.yLabel}
        points={artifact.points}
        xMid={artifact.xMid}
        yMid={artifact.yMid}
        footnote={artifact.footnote}
      />
    );
  }
  return null;
}

function ProvenanceRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-[92px] shrink-0 text-ink-3">{label}</dt>
      <dd className="min-w-0 flex-1 break-words text-ink-2">{children}</dd>
    </div>
  );
}

function ProvenanceFields({ provenance }: { provenance: DimeProvenance }) {
  const hasSources =
    provenance.liveSources.length > 0 || (provenance.liveSourceIds?.length ?? 0) > 0;
  return (
    <>
      <ProvenanceRow label="Capability">{provenance.capability ?? "not provided"}</ProvenanceRow>
      <ProvenanceRow label="Origin">{originPhrase(provenance)}</ProvenanceRow>
      {provenance.warehouseId && (
        <ProvenanceRow label="Warehouse">{provenance.warehouseId}</ProvenanceRow>
      )}
      <ProvenanceRow label="Season">{provenance.season ?? "not provided"}</ProvenanceRow>
      <ProvenanceRow label="As of">{provenance.asOf ?? "not provided"}</ProvenanceRow>
      <ProvenanceRow label="Live sources">
        {hasSources ? (
          <span className="flex flex-col gap-0.5">
            {provenance.liveSources.map((url) => (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noreferrer noopener"
                className="break-all text-ink underline decoration-line-strong underline-offset-2"
              >
                {url}
              </a>
            ))}
            {(provenance.liveSourceIds ?? []).map((id) => (
              <span key={id} className="break-all text-ink-2">
                {id}
              </span>
            ))}
          </span>
        ) : (
          "none provided"
        )}
      </ProvenanceRow>
    </>
  );
}

export function ProvenancePanel({ provenance }: { provenance: DimeProvenance }) {
  const evidence: ProvenanceEvidence[] = provenance.evidence?.length
    ? provenance.evidence
    : [{ label: "", provenance }];
  return (
    <details className="mt-3 rounded-[10px] border border-line bg-field px-3 py-2">
      <summary className="cursor-pointer text-[12px] font-medium text-ink-2">
        Sources &amp; provenance
      </summary>
      <dl className="mt-2 flex flex-col gap-2.5 text-[12px] leading-relaxed">
        {evidence.map((entry, i) => (
          <div key={i} className="flex flex-col gap-1">
            {entry.label && <div className="font-medium text-ink-2">{entry.label}</div>}
            <ProvenanceFields provenance={entry.provenance} />
          </div>
        ))}
      </dl>
    </details>
  );
}

function escapeCsvCell(val: unknown): string {
  if (val === null || val === undefined) return "";
  const s = String(val);
  if (s.includes(",") || s.includes('"') || s.includes("\n") || s.includes("\r")) {
    return `"${s.replaceAll('"', '""')}"`;
  }
  return s;
}

export function artifactToCopyText(artifact: DimeArtifact): string {
  if (artifact.kind === "memo") return memoToMarkdown(artifact);
  if (artifact.kind === "player_card") {
    return ["Player,Team,Metric,Value,Unit,Source,Row,Column", ...artifact.metrics.map(metric =>
      [artifact.playerName, artifact.team, metric.label, metric.value, metric.unit, artifact.sourceRef, artifact.sourceRow, metric.column].map(escapeCsvCell).join(",")
    )].join("\n");
  }
  if (artifact.kind === "table") {
    const header = artifact.columns.map((c) => escapeCsvCell(c.label || c.key)).join(",");
    const rows = artifact.rows.map((row) => row.map(escapeCsvCell).join(","));
    return [header, ...rows].join("\n");
  }
  if (artifact.kind === "compare") {
    const header = `Metric,${escapeCsvCell(artifact.aName)},${escapeCsvCell(artifact.bName)}`;
    const rows = artifact.rows.map(
      (r) => `${escapeCsvCell(r.label)},${escapeCsvCell(r.a)},${escapeCsvCell(r.b)}`,
    );
    return [header, ...rows].join("\n");
  }
  if (artifact.kind === "chart") {
    const maxVals = Math.max(0, ...artifact.series.map((s) => s.values.length));
    const valHeaders =
      artifact.xLabels && artifact.xLabels.length >= maxVals
        ? artifact.xLabels.slice(0, maxVals).map(escapeCsvCell)
        : Array.from({ length: maxVals }, (_, i) => `Val ${i + 1}`);
    const header = maxVals > 0 ? `Series,${valHeaders.join(",")}` : "Series";
    const rows = artifact.series.map((s) =>
      [escapeCsvCell(s.name), ...s.values.map(escapeCsvCell)].join(","),
    );
    return [header, ...rows].join("\n");
  }
  if (artifact.kind === "shot_chart") {
    const header = "X,Y,Attempts,Percentage";
    const rows = artifact.zones.map(
      (z) => `${escapeCsvCell(z.x)},${escapeCsvCell(z.y)},${escapeCsvCell(z.att)},${escapeCsvCell(z.pct)}`,
    );
    return [header, ...rows].join("\n");
  }
  if (artifact.kind === "scatter") {
    const header = `Label,${escapeCsvCell(artifact.xLabel)},${escapeCsvCell(artifact.yLabel)}`;
    const rows = artifact.points.map((p) => `${escapeCsvCell(p.label)},${p.x},${p.y}`);
    return [header, ...rows].join("\n");
  }
  return "";
}

export function StreamArtifacts({ artifacts }: { artifacts: DimeArtifact[] }) {
  if (artifacts.length === 0) return null;
  return (
    <div className="mt-5 flex flex-col gap-4">
      {artifacts.map((artifact, i) => (
        <ArtifactShell
          key={i}
          title={artifact.title}
          source={artifact.source}
          copyText={artifactToCopyText(artifact)}
          actions={<PinButton artifact={artifact} />}
        >
          <ArtifactBody artifact={artifact} />
          <ProvenancePanel provenance={artifact.provenance ?? undeclaredProvenance()} />
        </ArtifactShell>
      ))}
    </div>
  );
}

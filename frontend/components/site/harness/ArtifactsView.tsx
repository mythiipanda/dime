"use client";

import type { ReactNode } from "react";
import { QuietDetails } from "@/components/ds/QuietDetails";
import { useState } from "react";
import { ShareAndroid } from "iconoir-react";
import { mintObject, shareLink as objectShareLink } from "@/lib/objects-client";
import { MintedLink, copyToClipboard } from "@/components/dime/MintedLink";
import ArtifactChart, { type ChartSeries } from "@/components/dime/ArtifactChart";
import ArtifactCompare from "@/components/dime/ArtifactCompare";
import ArtifactTradeVerdict from "@/components/dime/ArtifactTradeVerdict";
import ArtifactCapSummary from "@/components/dime/ArtifactCapSummary";
import ArtifactScatter from "@/components/dime/ArtifactScatter";
import ArtifactShell from "@/components/dime/ArtifactShell";
import ArtifactShotChart from "@/components/dime/ArtifactShotChart";
import ArtifactTable from "@/components/dime/ArtifactTable";
import ArtifactMemo from "@/components/dime/ArtifactMemo";
import ArtifactPlayerCard from "@/components/dime/ArtifactPlayerCard";
import ArtifactTeamCard from "@/components/dime/ArtifactTeamCard";
import OpenInViewButton from "@/components/dime/OpenInViewButton";
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
  if (artifact.kind === "team_card") return <ArtifactTeamCard artifact={artifact} />;
  if (artifact.kind === "trade_verdict") return <ArtifactTradeVerdict artifact={artifact} />;
  if (artifact.kind === "cap_summary") return <ArtifactCapSummary artifact={artifact} />;
  if (artifact.kind === "table") {
    return <ArtifactTable columns={artifact.columns} rows={artifact.rows} title={artifact.title} footnote={artifact.footnote} />;
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
        subtitle={artifact.subtitle}
        variant={artifact.variant}
        xLabel={artifact.xLabel}
        yLabel={artifact.yLabel}
        marks={artifact.marks}
        annotations={artifact.annotations}
        labelValues={artifact.labelValues}
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
      {provenance.dataset && (
        <ProvenanceRow label="Dataset">{provenance.dataset}</ProvenanceRow>
      )}
      {provenance.sql && (
        <ProvenanceRow label="SQL"><span className="break-all font-mono text-[11px]">{provenance.sql}</span></ProvenanceRow>
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
    <QuietDetails label={<>Provenance</>}>
      <dl className="mt-2 flex flex-col gap-2.5 text-[12px] leading-relaxed">
        {evidence.map((entry, i) => (
          <div key={i} className="flex flex-col gap-1">
            {entry.label && <div className="font-medium text-ink-2">{entry.label}</div>}
            <ProvenanceFields provenance={entry.provenance} />
          </div>
        ))}
      </dl>
    </QuietDetails>
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
  if (artifact.kind === "trade_verdict") {
    const lines = [`Verdict,${artifact.legal ? "Legal" : "Illegal"}`];
    lines.push("Team,Players Out,Outgoing,Players In,Incoming,Payroll Before,Payroll After,Allowed Incoming,Match Rule,Hard Cap");
    for (const team of artifact.teams) {
      const pickCell = (picks: { year: number; round: number; swap?: boolean; protection?: string }[] | undefined) =>
        (picks ?? []).map(p => `${p.year} ${p.round === 1 ? "1st" : p.round === 2 ? "2nd" : `R${p.round}`}${p.swap ? " swap" : ""}${p.protection ? ` (${p.protection})` : ""}`).join("; ");
      const outAssets = [team.playersOut.join("; "), pickCell(team.picksOut)].filter(Boolean).join("; ");
      const inAssets = [team.playersIn.join("; "), pickCell(team.picksIn)].filter(Boolean).join("; ");
      lines.push([
        team.team,
        outAssets,
        team.outgoing,
        inAssets,
        team.incoming,
        team.payrollBefore,
        team.payrollAfter,
        team.allowedIncoming,
        team.matchRule,
        team.hardCap,
      ].map(escapeCsvCell).join(","));
    }
    for (const issue of artifact.issues ?? []) lines.push(["Issue", issue].map(escapeCsvCell).join(","));
    for (const check of artifact.checks ?? []) lines.push(["Check", check.rule, check.note ?? ""].map(escapeCsvCell).join(","));
    return lines.join("\n");
  }
  if (artifact.kind === "cap_summary") {
    const lines: string[] = [`Team,${artifact.team}${artifact.season ? ` (${artifact.season})` : ""}`];
    lines.push(["Payroll Before", artifact.payrollBefore, "Payroll After", artifact.payrollAfter, "Delta", artifact.delta ?? artifact.payrollAfter - artifact.payrollBefore].map(escapeCsvCell).join(","));
    const rooms: (string | number)[] = [];
    for (const [label, value] of [["Cap Room", artifact.capRoom], ["Cap Room Before", artifact.capRoomBefore], ["Tax Room", artifact.taxRoom], ["Room Under Apron 1", artifact.roomApron1], ["Room Under Apron 2", artifact.roomApron2]] as const) {
      if (value !== undefined) rooms.push(label, value);
    }
    if (rooms.length) lines.push(rooms.map(escapeCsvCell).join(","));
    const flags = [artifact.overTax ? "over tax" : "", artifact.overApron1 ? "over first apron" : "", artifact.overApron2 ? "over second apron" : "", artifact.hardCap ? `hard-cap: ${artifact.hardCap}` : ""].filter(Boolean);
    if (flags.length) lines.push(["Flags", flags.join("; ")].map(escapeCsvCell).join(","));
    for (const step of artifact.steps ?? []) lines.push(["Step", step.detail, step.delta ?? "", step.payroll ?? ""].map(escapeCsvCell).join(","));
    for (const issue of artifact.issues ?? []) lines.push(["Issue", issue].map(escapeCsvCell).join(","));
    for (const restriction of artifact.restrictions ?? []) lines.push(["Restriction", restriction.threshold, restriction.rule].map(escapeCsvCell).join(","));
    return lines.join("\n");
  }
  if (artifact.kind === "memo") return memoToMarkdown(artifact);
  if (artifact.kind === "player_card" || artifact.kind === "team_card") {
    const name = artifact.kind === "player_card" ? artifact.playerName : artifact.teamName;
    const team = artifact.kind === "player_card" ? artifact.team : undefined;
    const lines = artifact.metrics.map(metric =>
      ["", name, team, metric.label, metric.value, metric.unit, artifact.sourceRef, artifact.sourceRow, metric.column].map(escapeCsvCell).join(",")
    );
    for (const section of artifact.sections ?? []) {
      for (const field of section.fields ?? [])
        lines.push([section.label, name, team, field.label, field.value, "", section.sourceRef, section.sourceRow, field.column].map(escapeCsvCell).join(","));
      for (const metric of section.metrics ?? [])
        lines.push([section.label, name, team, metric.label, metric.value, metric.unit, section.sourceRef, section.sourceRow, metric.column].map(escapeCsvCell).join(","));
    }
    return ["Section,Player,Team,Metric,Value,Unit,Source,Row,Column", ...lines].join("\n");
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
    const header = "Zone,X,Y,Attempts,Makes,FG%,Delta vs league";
    const rows = artifact.zones.map(
      (z) => [z.label, z.x, z.y, z.att, z.makes, z.pct, z.delta].map(escapeCsvCell).join(","),
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

type SharePhase =
  | { phase: "idle" }
  | { phase: "minting" }
  | { phase: "minted"; link: string; copied: boolean }
  | { phase: "error" };

function ShareableArtifact({ artifact, shareContext }: { artifact: DimeArtifact; shareContext?: { run_id: string; thread: string; index: number } }) {
  const [share, setShare] = useState<SharePhase>({ phase: "idle" });
  const mint = () => {
    if (!shareContext || share.phase === "minting") return;
    setShare({ phase: "minting" });
    mintObject("artifact_ref", artifact.title || "shared artifact", {
      run_id: shareContext.run_id,
      thread: shareContext.thread,
      artifact_index: shareContext.index,
    })
      .then((created) => setShare({ phase: "minted", link: objectShareLink(created.read_token), copied: false }))
      .catch(() => setShare({ phase: "error" }));
  };
  const copyLink = (link: string) => {
    copyToClipboard(link, () => setShare((current) => current.phase === "minted" ? { ...current, copied: true } : current));
  };
  return (
    <div className="flex flex-col gap-2">
      <ArtifactShell
        title={artifact.title}
        source={artifact.source}
        copyText={artifactToCopyText(artifact)}
        actions={<>
          <OpenInViewButton artifact={artifact} />
          <PinButton artifact={artifact} />
          {shareContext && (
            <button
              className="icon-button"
              aria-label={share.phase === "minting" ? "Creating share link" : "Share artifact"}
              title={share.phase === "error" ? "Could not create share link; try again" : "Share artifact"}
              disabled={share.phase === "minting"}
              onClick={mint}
            >
              <ShareAndroid width={13} height={13} aria-hidden="true" />
            </button>
          )}
        </>}
      >
        <ArtifactBody artifact={artifact} />
        <ProvenancePanel provenance={artifact.provenance ?? undeclaredProvenance()} />
      </ArtifactShell>
      {share.phase === "minted" && (
        <MintedLink
          link={share.link}
          copied={share.copied}
          onCopy={copyLink}
          note="Anyone with this link can view this artifact and its pinned evidence; read-only. Numbers are the capture-time snapshot."
        />
      )}
      {share.phase === "error" && (
        <p role="status" className="text-[11.5px] text-red">Could not create the share link — try again.</p>
      )}
    </div>
  );
}

export function StreamArtifacts({ artifacts, shareContext }: { artifacts: DimeArtifact[]; shareContext?: { run_id: string; thread: string } }) {
  if (artifacts.length === 0) return null;
  return (
    <div className="mt-5 flex flex-col gap-4">
      {artifacts.map((artifact, i) => (
        <ShareableArtifact
          key={i}
          artifact={artifact}
          shareContext={shareContext ? { ...shareContext, index: i } : undefined}
        />
      ))}
    </div>
  );
}

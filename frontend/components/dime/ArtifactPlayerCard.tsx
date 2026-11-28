"use client";

import { Database } from "iconoir-react";
import { Button } from "@/components/ds/Button";
import { StatusPill } from "@/components/ds/StatusPill";
import { Popover, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { CardSection, CardSectionSources, cardSectionCitation } from "@/components/dime/ArtifactCardSections";
import { formatHeadlineMetric, unitEmbeddedInline } from "@/lib/metric-format";
import type { PlayerCardArtifactPayload } from "@/lib/dime-stream";

export default function ArtifactPlayerCard({ artifact }: { artifact: PlayerCardArtifactPayload }) {
  return <div className="p-4">
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 flex-1"><h3 className="mb-1 break-words text-xl font-medium tracking-tight text-ink">{artifact.playerName}</h3><p className="mt-1 break-words text-[13px] text-ink-2">{[artifact.team, artifact.provenance?.season].filter(Boolean).join(" · ")}</p></div>
      <StatusPill dot={false}>Source values</StatusPill>
    </div>
    <dl className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3">
      {artifact.metrics.map((metric, i) => <div key={`${metric.column}-${i}`} className="min-w-0">
        <dt className="break-words text-xs text-ink-2">{metric.label}</dt>
        <dd className="mt-1 break-words text-2xl font-medium tabular-nums tracking-tight text-ink">{metric.value === null ? <span aria-label="Not available">—</span> : formatHeadlineMetric(metric.value, metric.unit)}</dd>
        {!(unitEmbeddedInline(metric.unit)) && <dd className="mt-1 break-words text-xs text-ink-3">{metric.unit || "Unit not declared"}</dd>}
      </div>)}
    </dl>
    {artifact.sections && artifact.sections.length > 0 && (() => {
      const citations = [...new Set(artifact.sections.map(cardSectionCitation).filter(Boolean))];
      const sharedCitation = citations.length === 1 ? citations[0] : undefined;
      return <div className="mt-5 space-y-4">
        {sharedCitation && <p className="text-xs text-ink-3">{sharedCitation}</p>}
        {artifact.sections.map((section, i) => <CardSection key={`${section.label}-${i}`} section={section} sharedCitation={sharedCitation} />)}
      </div>;
    })()}
    <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
      <p className="text-xs text-ink-3">Selected from source rows. Not a verification.</p>
      <Popover><PopoverTrigger asChild><Button size="sm" variant="quiet"><Database width={14} height={14} aria-hidden="true" />Inspect source values</Button></PopoverTrigger>
        <PopoverContent align="end" aria-label={`Source values for ${artifact.playerName}`} className="w-80 bg-surface text-ink">
          <PopoverTitle>Source values</PopoverTitle><PopoverDescription>Raw values and declared units, without conversion. Labels and conclusions are not verified.</PopoverDescription>
          <dl className="mt-3 grid grid-cols-[64px_minmax(0,1fr)] gap-2 text-xs"><dt className="text-ink-3">Reference</dt><dd className="break-all font-mono">{artifact.sourceRef}</dd><dt className="text-ink-3">Row index</dt><dd>{artifact.sourceRow} (zero-based)</dd><dt className="text-ink-3">Identity</dt><dd className="break-all">{artifact.nameColumn}{artifact.teamColumn && ` · ${artifact.teamColumn}`}</dd></dl>
          <dl className="mt-3 space-y-2 border-t border-line pt-3 text-xs">{artifact.metrics.map((metric, i) => <div key={i} className="flex flex-wrap justify-between gap-2"><dt className="break-all font-mono text-ink-2">{metric.column}</dt><dd className="break-words tabular-nums">{metric.value === null ? "Not available" : String(metric.value)} · {metric.unit || "Unit not declared"}</dd></div>)}</dl>
          {artifact.sections && <CardSectionSources sections={artifact.sections} />}
        </PopoverContent>
      </Popover>
    </div>
  </div>;
}

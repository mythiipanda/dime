"use client";

import { Database } from "lucide-react";
import { Button } from "@/components/ds/Button";
import { StatusPill } from "@/components/ds/StatusPill";
import { Popover, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { CardSection, CardSectionSources } from "@/components/dime/ArtifactCardSections";
import type { PlayerCardArtifactPayload } from "@/lib/dime-stream";
=======
import type { PlayerCardArtifactPayload, PlayerCardSectionPayload } from "@/lib/dime-stream";

function sectionCitation(section: PlayerCardSectionPayload): string {
  const parts = [section.provenance?.dataset, section.provenance?.season, section.provenance?.capability].filter(Boolean);
  return parts.join(" · ");
}

function Section({ section }: { section: PlayerCardSectionPayload }) {
  const citation = sectionCitation(section);
  return <div className="border-t border-line pt-4">
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
      <p className="text-sm font-medium text-ink">{section.label}</p>
      <p className="text-xs text-ink-3">{citation || "Source not declared"}</p>
    </div>
    {section.fields && section.fields.length > 0 && <dl className="mb-3 space-y-1.5">
      {section.fields.map((item, i) => <div key={`${item.column}-${i}`} className="flex flex-wrap items-baseline justify-between gap-2">
        <dt className="break-words text-xs text-ink-2">{item.label}</dt>
        <dd className="break-words text-[13px] font-medium text-ink">{item.value === null ? <span aria-label="Not available">—</span> : item.value}</dd>
      </div>)}
    </dl>}
    {section.metrics && section.metrics.length > 0 && <dl className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-3">
      {section.metrics.map((metric, i) => <div key={`${metric.column}-${i}`} className="min-w-0">
        <dt className="break-words text-xs text-ink-2">{metric.label}</dt>
        <dd className="mt-1 break-words text-lg font-medium tabular-nums tracking-tight text-ink">{metric.value === null ? <span aria-label="Not available">—</span> : String(metric.value)}</dd>
        <dd className="mt-0.5 break-words text-xs text-ink-3">{metric.unit || "Unit not declared"}</dd>
      </div>)}
    </dl>}
  </div>;
}
>>>>>>> origin/dev

export default function ArtifactPlayerCard({ artifact }: { artifact: PlayerCardArtifactPayload }) {
  return <div className="p-4">
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 flex-1"><p className="mb-1 text-xs text-ink-3">Player snapshot</p><h3 className="break-words text-xl font-medium tracking-tight text-ink">{artifact.playerName}</h3><p className="mt-1 break-words text-[13px] text-ink-2">{[artifact.team, artifact.provenance?.season].filter(Boolean).join(" · ") || "Scope not declared"}</p></div>
      <StatusPill dot={false}>Source values</StatusPill>
    </div>
    <dl className="grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3">
      {artifact.metrics.map((metric, i) => <div key={`${metric.column}-${i}`} className="min-w-0">
        <dt className="break-words text-xs text-ink-2">{metric.label}</dt>
        <dd className="mt-1 break-words text-2xl font-medium tabular-nums tracking-tight text-ink">{metric.value === null ? <span aria-label="Not available">—</span> : String(metric.value)}</dd>
        <dd className="mt-1 break-words text-xs text-ink-3">{metric.unit || "Unit not declared"}</dd>
      </div>)}
    </dl>
    {artifact.sections && artifact.sections.length > 0 && <div className="mt-5 space-y-4">
      {artifact.sections.map((section, i) => <CardSection key={`${section.label}-${i}`} section={section} />)}
    </div>}
=======
    {artifact.sections && artifact.sections.length > 0 && <div className="mt-5 space-y-4">
      {artifact.sections.map((section, i) => <Section key={`${section.label}-${i}`} section={section} />)}
    </div>}
>>>>>>> origin/dev
    <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
      <p className="text-xs text-ink-3">Selected from source rows. Not a verification.</p>
      <Popover><PopoverTrigger asChild><Button size="sm" variant="quiet"><Database size={14} aria-hidden="true" />Inspect source values</Button></PopoverTrigger>
        <PopoverContent align="end" aria-label={`Source values for ${artifact.playerName}`} className="w-80 bg-surface text-ink">
          <PopoverTitle>Source values</PopoverTitle><PopoverDescription>Raw values and declared units, without conversion. Labels and conclusions are not verified.</PopoverDescription>
          <dl className="mt-3 grid grid-cols-[64px_minmax(0,1fr)] gap-2 text-xs"><dt className="text-ink-3">Reference</dt><dd className="break-all font-mono">{artifact.sourceRef}</dd><dt className="text-ink-3">Row index</dt><dd>{artifact.sourceRow} (zero-based)</dd><dt className="text-ink-3">Identity</dt><dd className="break-all">{artifact.nameColumn}{artifact.teamColumn && ` · ${artifact.teamColumn}`}</dd></dl>
          <dl className="mt-3 space-y-2 border-t border-line pt-3 text-xs">{artifact.metrics.map((metric, i) => <div key={i} className="flex flex-wrap justify-between gap-2"><dt className="break-all font-mono text-ink-2">{metric.column}</dt><dd className="break-words tabular-nums">{metric.value === null ? "Not available" : String(metric.value)} · {metric.unit || "Unit not declared"}</dd></div>)}</dl>
          {artifact.sections && <CardSectionSources sections={artifact.sections} />}
=======
          {artifact.sections && artifact.sections.map((section, i) => <div key={i} className="mt-3 border-t border-line pt-3">
            <p className="mb-2 text-xs font-medium">{section.label} · <span className="font-mono text-ink-3">{section.sourceRef}#{section.sourceRow}</span></p>
            <dl className="space-y-2 text-xs">
              {(section.fields ?? []).map((item, j) => <div key={j} className="flex flex-wrap justify-between gap-2"><dt className="break-all font-mono text-ink-2">{item.column}</dt><dd className="break-words">{item.value === null ? "Not available" : item.value}</dd></div>)}
              {(section.metrics ?? []).map((metric, j) => <div key={j} className="flex flex-wrap justify-between gap-2"><dt className="break-all font-mono text-ink-2">{metric.column}</dt><dd className="break-words tabular-nums">{metric.value === null ? "Not available" : String(metric.value)} · {metric.unit || "Unit not declared"}</dd></div>)}
            </dl>
          </div>)}
>>>>>>> origin/dev
        </PopoverContent>
      </Popover>
    </div>
  </div>;
}

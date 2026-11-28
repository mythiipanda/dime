"use client";

import type { PlayerCardSectionPayload } from "@/lib/dime-stream";
import { formatHeadlineMetric, unitEmbeddedInline } from "@/lib/metric-format";

export function cardSectionCitation(section: PlayerCardSectionPayload): string {
  const parts = [section.provenance?.dataset, section.provenance?.season, section.provenance?.capability].filter(Boolean);
  return parts.join(" · ");
}

export function CardSection({ section, sharedCitation }: { section: PlayerCardSectionPayload; sharedCitation?: string }) {
  const citation = cardSectionCitation(section);
  const showCitation = citation && citation !== sharedCitation;
  return <div className="border-t border-line pt-4">
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
      <p className="text-sm font-medium text-ink">{section.label}</p>
      {showCitation && <p className="text-xs text-ink-3">{citation}</p>}
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
        <dd className="mt-1 break-words text-lg font-medium tabular-nums tracking-tight text-ink">{metric.value === null ? <span aria-label="Not available">—</span> : formatHeadlineMetric(metric.value, metric.unit)}</dd>
        {!(unitEmbeddedInline(metric.unit)) && <dd className="mt-0.5 break-words text-xs text-ink-3">{metric.unit || "Unit not declared"}</dd>}
      </div>)}
    </dl>}
  </div>;
}

export function CardSectionSources({ sections }: { sections: PlayerCardSectionPayload[] }) {
  return <>{sections.map((section, i) => <div key={i} className="mt-3 border-t border-line pt-3">
    <p className="mb-2 text-xs font-medium">{section.label} · <span className="font-mono text-ink-3">{section.sourceRef}#{section.sourceRow}</span></p>
    <dl className="space-y-2 text-xs">
      {(section.fields ?? []).map((item, j) => <div key={j} className="flex flex-wrap justify-between gap-2"><dt className="break-all font-mono text-ink-2">{item.column}</dt><dd className="break-words">{item.value === null ? "Not available" : item.value}</dd></div>)}
      {(section.metrics ?? []).map((metric, j) => <div key={j} className="flex flex-wrap justify-between gap-2"><dt className="break-all font-mono text-ink-2">{metric.column}</dt><dd className="break-words tabular-nums">{metric.value === null ? "Not available" : String(metric.value)} · {metric.unit || "Unit not declared"}</dd></div>)}
    </dl>
  </div>)}</>;
}

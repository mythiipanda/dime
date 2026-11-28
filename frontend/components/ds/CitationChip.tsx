"use client";

import { useRef, useState } from "react";
import { ArrowDown } from "lucide-react";
import { Popover, PopoverTrigger, PopoverContent } from "../ui/popover";
import type { citationDetails } from "../../lib/citation-details";

export function EvidenceAction({ target, onNavigate }: { target: string | null; onNavigate: () => void }) {
  if (!target) return null;
  return <button onClick={() => { const element = document.getElementById(target); for (let parent = element?.parentElement; parent; parent = parent.parentElement) { if (parent instanceof HTMLDetailsElement) parent.open = true; } element?.scrollIntoView({ block: "center", behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); element?.focus({ preventScroll: true }); onNavigate(); }}>View evidence <ArrowDown width={11} height={11} className="inline" /></button>;
}

export function CitationChip({ index, detail, claim, onAccept, onFlag }: {
  index: number; detail: ReturnType<typeof citationDetails>; claim: string; onAccept?: () => void; onFlag?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const navigating = useRef(false);
  return <Popover open={open} onOpenChange={setOpen}>
    <PopoverTrigger className="citation-chip" aria-label={`Show source: ${claim || detail.label}`}>
      {index + 1}
    </PopoverTrigger>
    <PopoverContent side="top" align="start" aria-label={`Source details: ${detail.label}`} onCloseAutoFocus={event => {
      if (navigating.current) { event.preventDefault(); navigating.current = false; }
    }} className="citation-card w-80 gap-3 border border-line bg-surface p-4 text-ink shadow-overlay ring-0">
      <div className="flex items-center gap-2 text-[12px] font-medium">{detail.label}<span className="ml-auto text-[10px] font-normal text-ink-3">Source {index + 1}</span></div>
      {claim && <p className="text-[12px] leading-relaxed text-ink-2">{claim}</p>}
      <dl className="grid grid-cols-[52px_1fr] gap-x-3 gap-y-2 border-y border-line py-3 text-[11px]"><dt className="text-ink-3">Table</dt><dd className="break-all font-mono">{detail.table}</dd><dt className="text-ink-3">Season</dt><dd>{detail.season}</dd><dt className="text-ink-3">Rows</dt><dd>{detail.count || "Not recorded"}</dd><dt className="text-ink-3">Source</dt><dd>{detail.origin}</dd></dl>
      <div><p className="mb-1.5 text-[10px] text-ink-3">QUERY</p><pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-md bg-inset p-2 font-mono text-[10px] leading-relaxed text-ink-2">{detail.query || "Query not recorded for this evidence."}</pre></div>
      {detail.rows.length > 0 && <dl className="max-h-32 overflow-auto rounded-md border border-line px-2.5 py-1.5">{detail.rows.flatMap((row, i) => Object.entries(row).filter(([, value]) => value == null || typeof value !== "object").map(([key, value], j) => <div key={`${i}-${j}`} className="flex items-baseline justify-between gap-3 border-b border-line py-1 text-[10px] last:border-b-0"><dt className="shrink-0 text-ink-3">{key}</dt><dd className="break-words text-right font-medium text-ink">{String(value ?? "—")}</dd></div>))}</dl>}
      <div className="flex items-center gap-3 text-[11px] text-ink-2"><EvidenceAction target={detail.target} onNavigate={() => { navigating.current = true; setOpen(false); }} />{onAccept && <button onClick={onAccept}>Accept</button>}{onFlag && <button onClick={onFlag}>Flag</button>}</div>
    </PopoverContent>
  </Popover>;
}

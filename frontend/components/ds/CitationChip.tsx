"use client";

import { useState } from "react";
import { Database, ArrowDown } from "iconoir-react";
import { Popover, PopoverTrigger, PopoverContent } from "../ui/popover";
import type { citationDetails } from "../../lib/citation-details";

export function EvidenceAction({ target, onNavigate }: { target: string | null; onNavigate: () => void }) {
  if (!target) return null;
  return <button onClick={() => { const element = document.getElementById(target); element?.scrollIntoView({ block: "center", behavior: "smooth" }); element?.focus({ preventScroll: true }); onNavigate(); }}>View evidence <ArrowDown width={11} height={11} className="inline" /></button>;
}

export function CitationChip({ index, detail, claim, onAccept, onFlag }: {
  index: number; detail: ReturnType<typeof citationDetails>; claim: string; onAccept?: () => void; onFlag?: () => void;
}) {
  const [open, setOpen] = useState(false);
  return <Popover open={open} onOpenChange={setOpen}>
    <PopoverTrigger className="citation-chip" aria-label={`Show source: ${claim || detail.label}`} openOnHover delay={120} closeDelay={150}>
      <Database width={10} height={10} aria-hidden />{index + 1}<span className="max-w-28 truncate">{detail.label}</span>
    </PopoverTrigger>
    <PopoverContent side="top" align="start" initialFocus={false} className="citation-card w-80 gap-3 border border-line bg-surface p-4 text-ink shadow-overlay ring-0">
      <div className="flex items-center gap-2 text-[12px] font-medium"><Database width={14} height={14} />{detail.label}<span className="ml-auto text-[10px] font-normal text-ink-3">Source {index + 1}</span></div>
      {claim && <p className="text-[12px] leading-relaxed text-ink-2">{claim}</p>}
      <dl className="grid grid-cols-[52px_1fr] gap-x-3 gap-y-2 border-y border-line py-3 text-[11px]"><dt className="text-ink-3">Table</dt><dd className="break-all font-mono">{detail.table}</dd><dt className="text-ink-3">Season</dt><dd>{detail.season}</dd><dt className="text-ink-3">Rows</dt><dd>{detail.count || "Not recorded"}</dd><dt className="text-ink-3">Source</dt><dd>{detail.origin}</dd></dl>
      <div><p className="mb-1.5 text-[10px] text-ink-3">QUERY</p><pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-md bg-inset p-2 font-mono text-[10px] leading-relaxed text-ink-2">{detail.query || "Query not recorded for this evidence."}</pre></div>
      {detail.rows.length > 0 && <div className="max-h-24 overflow-auto rounded-md border border-line"><table className="w-full text-left text-[10px]"><tbody>{detail.rows.map((row, i) => <tr key={i}>{Object.entries(row).filter(([, value]) => value == null || typeof value !== "object").slice(0, 4).map(([key, value]) => <td key={key} className="border-b border-line px-2 py-1.5 last:border-r-0"><span className="block text-ink-3">{key}</span>{String(value ?? "—")}</td>)}</tr>)}</tbody></table></div>}
      <div className="flex items-center gap-3 text-[11px] text-ink-2"><EvidenceAction target={detail.target} onNavigate={() => setOpen(false)} />{onAccept && <button onClick={onAccept}>Accept</button>}{onFlag && <button onClick={onFlag}>Flag</button>}</div>
    </PopoverContent>
  </Popover>;
}

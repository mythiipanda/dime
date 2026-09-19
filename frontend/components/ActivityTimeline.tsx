"use client";

import { useEffect, useRef, useState } from "react";
import type { ActivityRecord } from "../lib/chat";

type Tone = "stage" | "tool" | "evidence" | "verify";
type View = { headline: string; description?: string; tone: Tone; fields: [string, string][] };
const pretty = (value: unknown) => String(value ?? "").replace(/_/g, " ");
const count = (n: unknown, noun: string) => `${Number(n) || 0} ${noun}${Number(n) === 1 ? "" : "s"}`;

function payload(item: ActivityRecord): Record<string, unknown> {
  const value = item.data.data;
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function describe(item: ActivityRecord): View {
  const d = payload(item);
  const name = pretty(d.name || d.capability || "data");
  if (item.kind === "stage_summary") return {
    headline: "Understood the question", tone: "stage",
    description: `${pretty(d.mode || "quick")} analysis · ${count(d.entity_count, "entity")} · ${count(d.requirement_count, "requirement")}`,
    fields: [["Season", pretty(d.season || "Current")], ["Calculations", String(d.calculation_count ?? 0)]],
  };
  if (item.kind === "plan_update") return {
    headline: `Built a ${Number(d.node_count) || 0}-step research plan`, tone: "stage",
    description: Array.isArray(d.capabilities) && d.capabilities.length ? d.capabilities.map(pretty).join(" · ") : "No data tools needed",
    fields: [["Known tools", String(Array.isArray(d.capabilities) ? d.capabilities.length : 0)], ["Unknown tools", String(d.unknown_capability_count ?? 0)]],
  };
  if (item.kind === "tool_call") return {
    headline: `Checking ${name}`, tone: "tool", description: "Query started",
    fields: [["Inputs", count(d.argument_count, "field")], ["Unrecognized inputs", String(d.unknown_argument_count ?? 0)]],
  };
  if (item.kind === "tool_result") {
    const failed = item.transition === "failed" || item.status === "fail" || item.status === "failed";
    return { headline: failed ? `Could not check ${name}` : `Checked ${name}`, tone: "tool",
      description: failed ? "The data source did not return a usable result" : d.rows == null ? "Query completed" : `${count(d.rows, "row")} returned`,
      fields: [["Result", failed ? "Failed" : "Complete"], ...(d.rows == null ? [] : [["Rows", String(d.rows)] as [string, string]])] };
  }
  if (item.kind === "evidence_update") {
    const admitted = item.transition === "admitted";
    return { headline: admitted ? `Added ${name} evidence` : `Set aside ${name} evidence`, tone: "evidence",
      description: admitted ? `${count(d.rows, "row")} passed the evidence check` : "This result did not meet the evidence bar",
      fields: [["Season", pretty(d.season || "Not specified")], ["Coverage", pretty(d.coverage)], ["Quality", pretty(d.qualification)], ["Warnings", String(d.warning_count ?? 0)], ["Source date", pretty(d.as_of || "Not supplied")]] };
  }
  if (item.kind === "verification_update") return {
    headline: `Verified ${Number(d.supported_count) || 0} of ${Number(d.claim_count) || 0} claims`, tone: "verify",
    description: Number(d.missing_count) || Number(d.contradiction_count) ? `${count(d.missing_count, "gap")} · ${count(d.contradiction_count, "conflict")}` : "All checked claims are supported",
    fields: [["Round", pretty(d.round)], ["Repairs", String(d.repair_count ?? 0)]],
  };
  return { headline: item.title, description: item.summary, tone: "stage", fields: [] };
}

const icons: Record<Tone, React.ReactNode> = {
  stage: <path d="M4 7h8M4 12h5M4 2h8"/>,
  tool: <><circle cx="6.5" cy="6.5" r="3.5"/><path d="m9 9 4 4"/></>,
  evidence: <><path d="M3 3h10v10H3z"/><path d="m5 8 2 2 4-5"/></>,
  verify: <path d="m2.5 8 3 3 8-8"/>,
};
const colors: Record<Tone, { bg: string; fg: string }> = {
  stage: { bg: "color-mix(in srgb, var(--color-cyan-signal) 11%, transparent)", fg: "var(--color-cyan-edge)" },
  tool: { bg: "var(--color-stone-canvas)", fg: "var(--color-warm-gray)" },
  evidence: { bg: "color-mix(in srgb, #8b6f3d 12%, transparent)", fg: "#a98749" },
  verify: { bg: "color-mix(in srgb, #4f8a67 13%, transparent)", fg: "#69a77f" },
};

function EventRow({ item, active, last }: { item: ActivityRecord; active: boolean; last: boolean }) {
  const [open, setOpen] = useState(false);
  const [technical, setTechnical] = useState(false);
  const view = describe(item); const color = colors[view.tone];
  const failed = item.transition === "failed" || item.status === "fail" || item.status === "failed";
  const time = item.emittedAt ? new Date(item.emittedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
  return <li style={{ display: "grid", gridTemplateColumns: "30px minmax(0,1fr)", gap: 10, position: "relative", paddingBottom: last ? 2 : 14 }}>
    {!last && <span aria-hidden style={{ position: "absolute", left: 14, top: 28, bottom: -3, width: 1, background: "var(--color-stone-border)" }}/>}
    <span aria-hidden className={active ? "pulse-dot" : undefined} style={{ width: 28, height: 28, borderRadius: 9, display: "grid", placeItems: "center", background: failed ? "color-mix(in srgb, var(--color-ember) 12%, transparent)" : color.bg, color: failed ? "var(--color-ember)" : color.fg, zIndex: 1 }}>
      {active ? <span style={{ width: 7, height: 7, borderRadius: 99, background: "currentColor" }}/> : <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{icons[view.tone]}</svg>}
    </span>
    <div style={{ minWidth: 0, paddingTop: 2 }}>
      <button type="button" onClick={() => setOpen(v => !v)} aria-expanded={open} style={{ width: "100%", display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: 10, background: "none", border: 0, padding: 0, textAlign: "left", cursor: "pointer" }}>
        <span><span style={{ display: "block", fontSize: 13, lineHeight: 1.35, fontWeight: active ? 650 : 580, color: "var(--color-ink-black)" }}>{view.headline}</span>{view.description && <span style={{ display: "block", marginTop: 3, fontSize: 11.5, lineHeight: 1.4, color: "var(--color-ash-gray)" }}>{view.description}</span>}</span>
        <span style={{ display: "flex", gap: 7, alignItems: "center", color: "var(--color-ash-gray)", fontSize: 10.5 }}><span>{time}</span><span aria-hidden style={{ transform: open ? "rotate(90deg)" : "none", transition: "transform .18s" }}>›</span></span>
      </button>
      {open && <div style={{ marginTop: 9, padding: "10px 11px", border: "1px solid var(--color-stone-border)", borderRadius: 9, background: "var(--color-stone-canvas)" }}>
        <dl style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: "9px 16px", margin: 0 }}>{view.fields.filter(([,v]) => v).map(([k,v]) => <div key={k}><dt style={{ fontSize: 9.5, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--color-ash-gray)" }}>{k}</dt><dd style={{ margin: "2px 0 0", fontSize: 11.5, color: "var(--color-warm-gray)", overflowWrap: "anywhere" }}>{v}</dd></div>)}</dl>
        <button type="button" onClick={() => setTechnical(v => !v)} style={{ marginTop: view.fields.length ? 10 : 0, padding: 0, border: 0, background: "none", color: "var(--color-ash-gray)", fontSize: 10.5, cursor: "pointer", textDecoration: "underline", textUnderlineOffset: 3 }}>{technical ? "Hide technical view" : "Technical view"}</button>
        {technical && <pre style={{ margin: "8px 0 0", padding: 9, maxHeight: 220, overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere", borderRadius: 7, background: "var(--color-paper-white)", color: "var(--color-warm-gray)", fontSize: 10, lineHeight: 1.45 }}>{JSON.stringify(item.data, null, 2)}</pre>}
      </div>}
    </div>
  </li>;
}

export default function ActivityTimeline({ items, running }: { items: ActivityRecord[]; running: boolean }) {
  const viewport = useRef<HTMLDivElement>(null); const [following, setFollowing] = useState(true); const [seen, setSeen] = useState(items.length);
  useEffect(() => { if (following && viewport.current) { viewport.current.scrollTo({ top: viewport.current.scrollHeight, behavior: "smooth" }); setSeen(items.length); } }, [items.length, following]);
  const unseen = Math.max(0, items.length - seen);
  return <div style={{ position: "relative" }}><div ref={viewport} role="log" aria-live="polite" aria-label="Live analysis activity" onScroll={e => { const el=e.currentTarget; const bottom=el.scrollHeight-el.scrollTop-el.clientHeight<28; setFollowing(bottom); if(bottom)setSeen(items.length); }} style={{ maxHeight: running ? 390 : 520, overflowY: "auto", padding: "5px 5px 3px 0" }}><ol style={{ listStyle: "none", margin: 0, padding: 0 }}>{items.map((item,i)=><EventRow key={item.eventId} item={item} active={running&&i===items.length-1} last={i===items.length-1}/>)}</ol></div>{!following&&unseen>0&&<button type="button" className="pill-ghost" onClick={()=>{setFollowing(true);setSeen(items.length)}} style={{position:"sticky",bottom:4,left:"50%",transform:"translateX(-50%)",fontSize:11,background:"var(--color-paper-white)"}}>{unseen} new update{unseen===1?"":"s"}</button>}</div>;
}

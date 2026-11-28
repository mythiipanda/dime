"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, BarChart3, Check, ChevronDown, Users } from "lucide-react";
import { BasketballIcon } from "@/components/ds/BasketballIcon";
import { TEAM_ABBR_BY_FULL_NAME } from "../lib/teams";
import { workflows, validateWorkflow, type Workflow, type WorkflowValues } from "../lib/workflows";
import { Button } from "./ds/Button";
import { Chip } from "./ds/Chip";
import { SegmentedControl } from "./ds/SegmentedControl";
import { ValuePill } from "./ds/ValuePill";

const categories = ["All tasks", "Game prep", "Roster", "Player evaluation"] as const;
const categoryIcons = { "Game prep": BasketballIcon, Roster: Users, "Player evaluation": BarChart3 };
const countLabel = (count: number, label: string) => `${count} ${label}${count === 1 ? "" : "s"}`;

export default function WorkflowsPanel({ onRun }: { onRun: (request: string) => void }) {
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [values, setValues] = useState<WorkflowValues>({});
  const [category, setCategory] = useState<typeof categories[number]>("All tasks");
  const issues = selected ? validateWorkflow(selected, values) : [];
  const missing = issues.filter(issue => issue.kind === "required");
  return <div className="workflow-page">
    {!selected ? <>
      <div className="mb-8 flex items-start justify-between gap-6"><div><p className="mb-3 text-[11px] font-medium tracking-wider text-ink-3">THE ANALYST’S PLAYBOOK</p><h1 className="text-[28px] font-medium tracking-[-.04em]">Good questions. Better decisions.</h1><p className="mt-3 max-w-md text-[13px] leading-relaxed text-ink-2">Start with a task. Dime brings the structure, finds the evidence, and builds a cited analysis you can work with.</p></div><span className="mt-9 hidden sm:block"><Chip>{countLabel(workflows.length, "workflow")}</Chip></span></div>
      <div className="mb-8 overflow-x-auto pb-1"><SegmentedControl options={categories} value={category} onChange={setCategory} /></div>
      {categories.slice(1).filter((c) => category === "All tasks" || category === c).map((c) => <section key={c} className="mb-8"><h2 className="mb-3 text-[11px] font-medium text-ink-3">{c}</h2><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{workflows.filter((w) => w.category === c).map((w) => { const Icon = categoryIcons[w.category]; return <button key={w.id} className="workflow-card group" onClick={() => { setSelected(w); setValues({}); }}>
        <div className="mb-4 flex w-full items-center justify-between"><span className="rounded-lg border border-line bg-inset p-2 text-ink-2"><Icon width={17} height={17} /></span><ArrowRight width={15} height={15} className="text-ink-3 transition-transform group-hover:translate-x-1 group-hover:text-ink" /></div>
        <h3 className="text-[13px] font-medium">{w.title}</h3><p className="mt-2 mb-5 text-[12px] leading-relaxed text-ink-2">{w.summary}</p><span className="mt-auto text-[10px] text-ink-3">{countLabel(w.deliverable.length, "section")} <span className="mx-1.5">·</span> {countLabel(w.fields.filter((f) => f.required).length, "input")} <span className="mx-1.5">·</span> Cited analysis</span>
      </button>; })}</div></section>)}
      <div className="mt-10 border-t border-line pt-5 text-[11px] text-ink-3">Grounded in your warehouse. Clear about what’s missing. Always open to a follow-up.</div>
    </> : <>
      <Button size="xs" variant="quiet" onClick={() => setSelected(null)}><ArrowLeft width={13} height={13} />All workflows</Button>
      <div className="mt-7 mb-8"><div className="mb-3"><Chip>{selected.category}</Chip></div><h1 className="text-[28px] font-medium tracking-[-.04em]">{selected.title}</h1><p className="mt-2 text-[13px] text-ink-2">{selected.summary}</p></div>
      <form onSubmit={(e) => { e.preventDefault(); if (!issues.length) onRun(selected.buildRequest(values)); }}>
        <div className="grid gap-8 lg:grid-cols-[1.35fr_1fr]">
          <div><div className="rounded-xl border border-line bg-surface p-6"><div className="mb-6 flex items-center justify-between"><h2 className="text-[13px] font-medium">Set the context</h2><span className="text-[10px] text-ink-3">2025–26 season</span></div><div className="grid gap-5">{selected.fields.map((f) => <label key={f.id} className="workflow-field"><span>{f.label}{!f.required && <span className="ml-1 text-ink-3">(optional)</span>}</span>{f.kind === "team" || f.kind === "select" ? <select required={f.required} aria-invalid={issues.some(issue => issue.field.id === f.id && issue.kind === "same-team") || undefined} aria-describedby={issues.some(issue => issue.field.id === f.id && issue.kind === "same-team") ? `workflow-error-${f.id}` : undefined} value={values[f.id] || ""} onChange={(e) => setValues({ ...values, [f.id]: e.target.value })}><option value="">{f.placeholder}</option>{f.kind === "team" ? Object.entries(TEAM_ABBR_BY_FULL_NAME).map(([name, abbr]) => <option key={abbr} value={abbr}>{name} ({abbr})</option>) : f.options?.map((o) => <option key={o}>{o}</option>)}</select> : <input required={f.required} placeholder={f.placeholder} value={values[f.id] || ""} onChange={(e) => setValues({ ...values, [f.id]: e.target.value })} />}</label>)}</div>{issues.filter(issue => issue.kind === "same-team").map(issue => <p key={issue.field.id} id={`workflow-error-${issue.field.id}`} role="alert" className="mt-3 text-[12px] text-red">{issue.message}</p>)}</div>
            <details className="mt-4 rounded-xl border border-line"><summary className="flex list-none items-center justify-between px-5 py-4 text-[12px] text-ink-2">Preview request<ChevronDown width={13} height={13} /></summary><pre className="whitespace-pre-wrap border-t border-line p-5 font-mono text-[11px] leading-[1.8] text-ink-2">{selected.buildRequest(values)}</pre></details>
          </div>
          <div className="pt-1"><h2 className="mb-4 text-[13px] font-medium">What you’ll get</h2><ol className="grid gap-4">{selected.deliverable.map((section, i) => <li key={section} className="flex items-center gap-3 text-[12px] text-ink-2"><span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-line text-[10px] tabular-nums text-ink-3">{String(i + 1).padStart(2, "0")}</span>{section}</li>)}</ol><div className="mt-6 border-t border-line pt-5"><p className="flex items-center gap-2 text-[11px] text-ink-2"><Check width={13} height={13} />Warehouse sources and citations</p><p className="mt-2 text-[11px] leading-relaxed text-ink-3">Missing data is called out, never filled in. Continue the analysis in a new chat.</p></div></div>
        </div>
        <div className="mt-8 flex items-center justify-between gap-4 border-t border-line pt-6"><span className="text-[11px] text-ink-3">{missing.length ? `${missing.length} required ${missing.length === 1 ? "field" : "fields"} left` : issues.length ? "Choose different teams" : <ValuePill tone="green">Ready to run</ValuePill>}</span><Button type="submit" variant="primary" size="md" disabled={issues.length > 0}>Run workflow<ArrowRight width={14} height={14} /></Button></div>
      </form>
    </>}
  </div>;
}

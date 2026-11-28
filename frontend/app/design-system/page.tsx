"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, Command, Moon, Search, Sun } from "lucide-react";
import { Button } from "@/components/ds/Button";
import { Panel, PageHeader, Surface } from "@/components/ds/Panel";
import { SegmentedControl } from "@/components/ds/SegmentedControl";
import { StatusPill } from "@/components/ds/StatusPill";
import { Form, FormField, TextField } from "@/components/ds/TextField";
import { RecordsTable } from "@/components/ds/RecordsTable";
import { Popover, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import DimeCommandPalette from "@/components/site/DimeCommandPalette";
import { StreamArtifacts } from "@/components/site/harness/ArtifactsView";
import { generativeFixtures } from "@/lib/generative-fixture";
import { EvidenceTrace } from "@/components/ds/EvidenceTrace";

const foundations = [
  { name: "Canvas", token: "canvas", className: "bg-canvas" },
  { name: "Page", token: "page", className: "bg-page" },
  { name: "Surface", token: "surface", className: "bg-surface" },
  { name: "Inset", token: "inset", className: "bg-inset" },
  { name: "Ink", token: "ink", className: "bg-ink" },
  { name: "Accent", token: "accent-ink", className: "bg-accent-ink" },
];
const sections = ["Overview", "Foundations", "Controls", "Evidence", "Generative", "States"] as const;
const researchRows = [
  { player: "Wing A", minutes: 1240, points_per_36: 18.4, contract_years: 2 },
  { player: "Wing B", minutes: 986, points_per_36: 16.2, contract_years: 1 },
  { player: "Wing C", minutes: 722, points_per_36: null, contract_years: 3 },
];

export default function DesignSystemPage() {
  const [dark, setDark] = useState(true);
  const [filter, setFilter] = useState("All research");
  const [palette, setPalette] = useState(false);
  const [name, setName] = useState("");
  const [evidenceState, setEvidenceState] = useState("With records");
  const [state, setState] = useState<"idle" | "error" | "saving" | "saved">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, []);
  const toggleTheme = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("bui-theme", next ? "dark" : "light"); } catch {}
  };
  const navigate = (section: typeof sections[number]) => {
    requestAnimationFrame(() => {
      const target = document.getElementById(section.toLowerCase());
      target?.focus({ preventScroll: true });
      target?.scrollIntoView({ block: "start" });
    });
  };
  return <main className="min-h-dvh bg-page text-ink">
    <div className="system-page">
      <header className="mb-12 flex flex-wrap items-center justify-between gap-4 border-b border-line pb-5">
        <a href="/" className="inline-flex items-center gap-2 text-sm font-medium"><ArrowLeft size={15} aria-hidden="true" /> Dime <span className="font-normal text-ink-3">/ Design system</span></a>
        <div className="flex items-center gap-2"><Button size="sm" onClick={() => setPalette(true)}><Command size={14} aria-hidden="true" /> Commands</Button><Button size="icon" variant="quiet" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={toggleTheme}>{dark ? <Sun size={16} /> : <Moon size={16} />}</Button></div>
      </header>
      <section id="overview" tabIndex={-1} aria-label="Overview" className="system-section">
        <PageHeader eyebrow="Dime foundations / 01" title="Less interface. More intelligence." description="A quiet, precise workspace for basketball decisions. One visual language, accessible controls, and evidence always within reach." actions={<StatusPill tone="neutral" dot={false}>Component reference</StatusPill>} />
        <div className="mb-10 flex flex-wrap items-center justify-between gap-4"><nav aria-label="Reference sections" className="ds-segmented">{sections.map(section => <a key={section} href={`#${section.toLowerCase()}`} className="ds-segment">{section}</a>)}</nav><p className="system-label">Beautiful UI surfaces. shadcn/ui · Radix components.</p></div>
        <div className="system-preview mb-12">
          <Surface className="flex flex-col justify-between gap-8 p-7">
            <div><p className="system-label mb-3">The design direction</p><h2 className="max-w-sm text-2xl leading-snug font-medium tracking-tight">Make the next decision clearer.</h2><p className="mt-4 max-w-md text-sm leading-relaxed text-ink-2">Neutral surfaces keep the research in focus. A restrained accent signals an action, not decoration. Compact controls leave room for the work.</p></div>
            <div className="flex flex-wrap items-center gap-2"><Button variant="primary" onClick={() => { window.location.href = "/?tab=chat"; }}>Open workbench <ArrowRight size={14} aria-hidden="true" /></Button><a href="#controls" className="system-link px-2 text-xs">Explore the controls</a></div>
          </Surface>
          <Surface className="p-7">
            <div className="mb-6 flex flex-wrap items-center justify-between gap-2"><h2 className="text-sm font-medium">Research, at a glance</h2><StatusPill tone="accent">Illustrative</StatusPill></div>
            <p className="mb-6 text-xs leading-relaxed text-ink-2">A sample research card, not a live scouting result.</p>
            <div className="divide-y divide-line">{[["Question", "Which wings fit our rotation?"], ["Evidence", "Shooting, defense, and contract"], ["Next step", "Review the source rows"]].map(([label, value]) => <div key={label} className="flex flex-wrap items-center justify-between gap-3 py-4 text-xs"><span className="text-ink-3">{label}</span><span>{value}</span></div>)}</div>
            <p className="mt-6 border-t border-line pt-4 text-xs leading-relaxed text-ink-3">Status uses words as well as color. Numbers and sources remain attached to the claim.</p>
          </Surface>
        </div>
      </section>
      <section id="foundations" tabIndex={-1} aria-label="Foundations" className="system-section mb-12">
        <PageHeader eyebrow="01 / Foundations" title="One palette, two themes." description="Semantic roles adapt to the theme. Typography, density, corners, and elevation come from the same small set of tokens." />
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">{foundations.map(item => <div key={item.token}><div className={`system-swatch ${item.className}`} /><p className="mt-3 text-xs font-medium">{item.name}</p><code className="mt-1 block text-xs text-ink-3">--{item.token}</code></div>)}</div>
        <div className="grid gap-5 md:grid-cols-2">
          <Panel title="Type hierarchy" description="Inter for reading. JetBrains Mono for data, not paragraphs."><p className="mb-4 text-[length:var(--type-title)] leading-tight font-medium tracking-tight">Your next question.</p><p className="mb-3 text-[length:var(--type-body)] leading-relaxed text-ink-2">Body text gives the analysis room to breathe.</p><p className="text-[length:var(--type-meta)] text-ink-3">Supporting text stays readable in both themes.</p><p className="mt-5 font-mono text-sm tabular-nums">32.7 PPG <span className="px-2 text-ink-3">/</span> 63.7% TS</p></Panel>
          <Panel title="Density and motion" description="Compact on a pointer. Comfortable on touch."><dl className="grid grid-cols-2 gap-y-4 text-xs"><dt className="text-ink-3">Control heights</dt><dd className="text-right font-mono">28 / 32 / 36 px</dd><dt className="text-ink-3">Touch targets</dt><dd className="text-right font-mono">44 px minimum</dd><dt className="text-ink-3">Control / panel corners</dt><dd className="text-right font-mono">8 / 12 px</dd><dt className="text-ink-3">Feedback / transition</dt><dd className="text-right font-mono">150 / 200 ms</dd></dl><p className="mt-5 border-t border-line pt-4 text-xs leading-relaxed text-ink-2">Library enter transitions only. Reduced motion removes nonessential animation. No decorative movement in the analysis.</p></Panel>
        </div>
      </section>
      <section aria-label="Shape and space" className="system-section mb-12">
        <div className="grid gap-5 sm:grid-cols-3">
          <Panel title="Space is structure" description="A 4px rhythm, not a box around every thought."><div className="system-specimen gap-2 px-4" aria-hidden="true"><span className="size-2 rounded bg-line-strong" /><span className="size-3 rounded bg-line-strong" /><span className="size-4 rounded bg-line-strong" /><span className="size-6 rounded bg-line-strong" /><span className="size-8 rounded bg-line-strong" /></div><p className="mt-3 font-mono text-xs text-ink-3">8 / 12 / 16 / 24 / 32</p></Panel>
          <Panel title="Corners have roles" description="Pill actions. Shaped controls. Quiet panels."><div className="system-specimen gap-3" aria-hidden="true"><span className="size-9 rounded-full border border-line-strong bg-surface" /><span className="size-9 rounded-[var(--radius-control)] border border-line-strong bg-surface" /><span className="size-12 rounded-[var(--radius-panel)] border border-line-strong bg-surface" /></div><p className="mt-3 font-mono text-xs text-ink-3">Pill / 8 / 12 px</p></Panel>
          <Panel title="Depth has a purpose" description="Only floating content needs to feel raised."><div className="system-specimen" aria-hidden="true"><span className="rounded-[var(--radius-control)] bg-surface px-4 py-2 text-xs shadow-overlay">Source details</span></div><p className="mt-3 font-mono text-xs text-ink-3">--shadow-overlay</p></Panel>
        </div>
      </section>
      <section id="controls" tabIndex={-1} aria-label="Controls" className="system-section mb-12">
        <PageHeader eyebrow="02 / Controls" title="Familiar by design." description="Library primitives own keyboard behavior and focus. Dime supplies the tokens, the density, and the basketball context." />
        <div className="grid gap-5 md:grid-cols-2">
          <Panel title="Actions" description="One primary action per task. Quiet controls for everything else."><div className="flex flex-wrap gap-3"><Button variant="primary" onClick={() => setPalette(true)}>Primary action</Button><Button onClick={() => setPalette(true)}>Secondary</Button><Button variant="quiet" onClick={() => setPalette(true)}>Quiet</Button><Button variant="accent" onClick={() => setPalette(true)}>Accent</Button></div><div className="mt-5 flex flex-wrap items-center gap-3"><Button disabled>Unavailable</Button><Button loading>Save research</Button><Button size="icon" aria-label="Search commands" onClick={() => setPalette(true)}><Search size={15} /></Button></div><p className="mt-5 text-xs leading-relaxed text-ink-3">Pending actions keep their name, width, and focus. Repeated activation is blocked.</p></Panel>
          <Panel title="A complete field" description="Try an empty or short name, then a valid one."><Form noValidate onSubmit={event => {
            event.preventDefault();
            if (state === "saving") return;
            if (name.trim().length < 3) { setState("error"); return; }
            setState("saving");
            timer.current = setTimeout(() => setState("saved"), 700);
          }}><FormField name="research-name" label={<>Research name <span className="font-normal text-ink-3">(required)</span></>} description="Local example only. Nothing is sent or saved to your account." error={state === "error" ? "Use at least 3 characters for the research name." : undefined}><TextField id="research-name" required value={name} onChange={event => { setName(event.target.value); setState("idle"); }} readOnly={state === "saving"} placeholder="e.g. Rotation fits" /></FormField><div className="mt-5 flex flex-wrap items-center gap-3"><Button type="submit" variant="primary" loading={state === "saving"}>Save example</Button><span role="status" className="text-xs text-green">{state === "saved" && <span className="inline-flex items-center gap-1"><Check size={13} aria-hidden="true" /> Example saved locally</span>}</span></div></Form></Panel>
        </div>
      </section>
      <section id="evidence" tabIndex={-1} aria-label="Evidence" className="system-section mb-12">
        <PageHeader eyebrow="03 / Evidence" title="The detail behind the decision." description="Data is part of the answer, not a screenshot of it. Align numbers, state units, keep missing values honest, and make the source reachable without losing your place." />
        <Surface>
          <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="ds-panel-title">Rotation shortlist</h2><p className="ds-panel-description">Fictional players and illustrative values, not a live scouting result.</p></div><StatusPill tone="neutral" dot={false}>Design fixture</StatusPill></div>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3"><SegmentedControl options={["With records", "No matches"]} value={evidenceState} onChange={setEvidenceState} label="Evidence example state" /><Popover><PopoverTrigger asChild><Button size="sm">Source details</Button></PopoverTrigger><PopoverContent align="end" aria-label="Design fixture source details"><PopoverTitle>Design fixture</PopoverTitle><PopoverDescription className="text-xs leading-relaxed text-ink-2">These rows demonstrate density and missing values. No warehouse query was run.</PopoverDescription><dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 border-t border-line pt-3 text-xs"><dt className="text-ink-3">Units</dt><dd>Minutes, points per 36 minutes, years</dd><dt className="text-ink-3">Missing</dt><dd>Dash means not available, never zero.</dd></dl></PopoverContent></Popover></div>
          <RecordsTable title="Illustrative player records" rows={evidenceState === "With records" ? researchRows : []} source="Design fixture · no live warehouse query · minutes / points per 36 / contract years" />
          <p role="status" className="text-xs text-ink-2">{evidenceState === "With records" ? "3 illustrative records. Source and units stay attached to the table." : "No matching records. The table keeps its title, source, and next step."}</p>
        </Surface>
      </section>
      <section id="generative" tabIndex={-1} aria-label="Generative" className="system-section mb-12">
        <PageHeader eyebrow="04 / Generative answers" title="The right shape for the answer." description="A bounded component catalog, not arbitrary generated code. Player snapshots, interactive charts and sortable tables stay inside the conversation, with raw values and source inspection." />
        <div className="max-w-[760px]"><StatusPill dot={false}>Fictional design fixtures · no live data</StatusPill><StreamArtifacts artifacts={generativeFixtures} /></div>
        <div className="mt-8 grid max-w-[760px] gap-5 md:grid-cols-2">
          <Panel title="The run, while it works" description="One quiet status line. Rows appear as the evidence lands."><EvidenceTrace busy thinking={[{ label: "Reading illustrative source rows" }]} tools={[
            { key: "ds-1", name: "get_leaders", label: "Fetching league statistical leaders", status: "ok", rows: 48, ms: 210 },
            { key: "ds-2", name: "sql_exec", label: "Queried warehouse", status: "ok", rows: 12, ms: 88 },
            { key: "ds-3", name: "get_shot_zones", label: "Analyzing shot distribution zones", status: "running" },
          ]} /></Panel>
          <Panel title="The evidence, when it settles" description="The trace stays with the answer. Red is reserved for failures."><EvidenceTrace busy={false} thinking={[]} tools={[
            { key: "ds-4", name: "get_leaders", label: "Fetched league statistical leaders", status: "ok", rows: 48, ms: 210 },
            { key: "ds-5", name: "sql_exec", label: "Queried warehouse", status: "ok", rows: 12, ms: 88 },
            { key: "ds-6", name: "web_search", label: "Searched the web", status: "fail", error: "Fixture failure state" },
          ]} /></Panel>
        </div>
      </section>
      <section id="states" tabIndex={-1} aria-label="States" className="system-section">
        <PageHeader eyebrow="04 / States" title="Always say what happened." description="A color is not an explanation. Every status has a label, every error keeps your input, and every empty state points to a useful next step." />
        <Surface><div className="flex flex-wrap gap-3"><StatusPill tone="neutral">Queued</StatusPill><StatusPill tone="accent">Researching</StatusPill><StatusPill tone="green">Ready to review</StatusPill><StatusPill tone="orange">Needs attention</StatusPill><StatusPill tone="red">Could not load</StatusPill></div><div className="mt-6"><SegmentedControl options={["All research", "Conversations", "Projects"]} value={filter} onChange={setFilter} label="Example research filter" /><p role="status" className="mt-2 text-xs text-ink-3">Selected: {filter}. Illustrative filter only.</p></div><div className="mt-7 grid gap-5 border-t border-line pt-6 sm:grid-cols-2"><div><label htmlFor="disabled-field" className="mb-2 block text-xs font-medium">Unavailable field</label><TextField id="disabled-field" disabled value="Not available for this example" /></div><div><label htmlFor="long-field" className="mb-2 block text-xs font-medium">Long text</label><TextField id="long-field" readOnly defaultValue="A long research title stays inside its container without breaking the layout" /></div></div></Surface>
      </section>
      <footer className="mt-12 flex flex-wrap justify-between gap-4 border-t border-line pt-5 text-xs text-ink-3"><p>Shared foundations for every Dime workspace.</p><div className="flex flex-wrap gap-4"><a href="https://beautifului.dev/harness" className="system-link">Beautiful UI</a><a href="https://ui.shadcn.com/docs/components/radix" className="system-link">shadcn/ui · Radix</a><a href="https://design.how/directory/ui-libraries" className="system-link">design.how</a></div></footer>
    </div>
    <DimeCommandPalette open={palette} onClose={() => setPalette(false)} entries={[
      ...sections.map(section => ({ id: section, label: section, kind: "view" as const, run: () => navigate(section) })),
      { id: "theme", label: "Toggle theme", kind: "action", run: toggleTheme },
    ]} />
  </main>;
}

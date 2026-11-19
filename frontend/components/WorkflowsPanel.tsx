"use client";

import { useState } from "react";
import { TEAM_ABBR_BY_FULL_NAME } from "../lib/teams";
import { workflows, validateWorkflow, type Workflow, type WorkflowValues } from "../lib/workflows";

export default function WorkflowsPanel({ onRun }: { onRun: (request: string) => void }) {
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [values, setValues] = useState<WorkflowValues>({});
  return <div style={{ height: "100%", overflowY: "auto", color: "var(--color-ink-black)" }}>
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "32px 24px 64px", fontSize: 13 }}>
      <h1 style={{ fontSize: 24, fontWeight: 600 }}>Workflows</h1>
      <p style={{ color: "var(--color-warm-gray)", margin: "8px 0 24px" }}>A clear starting point for your next basketball decision.</p>
      {selected ? <>
        <button className="pill-ghost" onClick={() => setSelected(null)}>← All workflows</button>
        <h2 style={{ fontSize: 20, marginTop: 24 }}>{selected.title}</h2>
        <p style={{ color: "var(--color-warm-gray)", margin: "8px 0 24px" }}>{selected.summary}</p>
        <form onSubmit={(event) => { event.preventDefault(); if (!validateWorkflow(selected, values).length) onRun(selected.buildRequest(values)); }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
            {selected.fields.map((f) => <label key={f.id} style={{ display: "grid", gap: 8 }}>{f.label}{!f.required && " (optional)"}
              {f.kind === "team" || f.kind === "select" ? <select required={f.required} value={values[f.id] || ""} onChange={(e) => setValues({ ...values, [f.id]: e.target.value })} style={inputStyle}>
                <option value="">{f.placeholder}</option>
                {f.kind === "team" ? Object.entries(TEAM_ABBR_BY_FULL_NAME).map(([name, abbr]) => <option key={abbr} value={abbr}>{name} ({abbr})</option>) : f.options?.map((option) => <option key={option}>{option}</option>)}
              </select> : <input required={f.required} value={values[f.id] || ""} placeholder={f.placeholder} onChange={(e) => setValues({ ...values, [f.id]: e.target.value })} style={inputStyle} />}
            </label>)}
          </div>
          <h3 style={{ fontWeight: 600, margin: "28px 0 12px" }}>What you’ll get</h3>
          <ol style={{ listStyle: "decimal", paddingLeft: 20, lineHeight: 2 }}>{selected.deliverable.map((section) => <li key={section}>{section}</li>)}</ol>
          <details style={{ margin: "24px 0", padding: 16, border: "1px solid var(--color-stone-border)", borderRadius: 8 }}><summary style={{ cursor: "pointer" }}>Preview request</summary><pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", lineHeight: 1.7, marginTop: 12 }}>{selected.buildRequest(values)}</pre></details>
          <button type="submit" className="pill-ghost" disabled={validateWorkflow(selected, values).length > 0} style={{ opacity: validateWorkflow(selected, values).length ? 0.4 : 1 }}>Run workflow →</button>
          <p style={{ color: "var(--color-warm-gray)", marginTop: 12, fontSize: 12 }}>Starts a new analyst chat. Uses warehouse evidence for the 2025-26 season.</p>
        </form>
      </> : [...new Set(workflows.map((w) => w.category))].map((category) => <section key={category} style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 12 }}>{category}</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: 12 }}>
          {workflows.filter((w) => w.category === category).map((w) => <button key={w.id} className="interactive-tactile" onClick={() => { setSelected(w); setValues({}); }} style={{ textAlign: "left", padding: 20, border: "1px solid var(--color-stone-border)", borderRadius: 10, background: "var(--color-pure-white)", cursor: "pointer", color: "inherit" }}>
            <h3 style={{ fontWeight: 600 }}>{w.title} <span aria-hidden="true" style={{ float: "right" }}>↗</span></h3>
            <p style={{ color: "var(--color-warm-gray)", margin: "8px 0 20px", lineHeight: 1.6 }}>{w.summary}</p>
            <span style={{ color: "var(--color-ash-gray)", fontSize: 12 }}>{w.deliverable.length} sections · {w.fields.length} inputs</span>
          </button>)}
        </div>
      </section>)}
    </div>
  </div>;
}

const inputStyle = { width: "100%", padding: "10px 12px", border: "1px solid var(--color-stone-border)", borderRadius: 6, background: "var(--color-field)", color: "var(--color-ink-black)", fontSize: 13 };

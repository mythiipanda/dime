"use client";

import { useMemo, useState } from "react";
import type { AiMessage, NodeName, ToolCall } from "../lib/chat";
import ActivityTimeline from "./ActivityTimeline";
import { rerunSql, type SqlRerunRows } from "../lib/api";

const AGENT_NODES: NodeName[] = ["data_retrieval", "tools", "analytics", "presentation"];

function thoughtsFor(ai: AiMessage): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const n of AGENT_NODES) {
    const s = ai.nodes[n];
    if (!s) continue;
    for (const t of s.thoughts) {
      const key = t.trim().toLowerCase();
      if (key && !seen.has(key)) {
        seen.add(key);
        out.push(t);
      }
    }
  }
  return out;
}

function callsFor(ai: AiMessage): ToolCall[] {
  const out: ToolCall[] = [];
  for (const n of AGENT_NODES) {
    const s = ai.nodes[n];
    if (s) out.push(...s.toolCalls.filter((c) => c.status !== "fail"));
  }
  return out;
}

function reasoningFor(ai: AiMessage): string {
  const parts: string[] = [];
  for (const n of AGENT_NODES) {
    const s = ai.nodes[n];
    if (s?.liveThought) parts.push(stripMd(s.liveThought));
  }
  return parts.join("\n").trim();
}

const stripMd = (s: string) => s.replace(/\*\*|__|`/g, "");

function thoughtTitle(text: string): string {
  const line = text.split("\n").map((l) => l.trim()).find((l) => l.length > 0) || "Reasoning";
  return line.length > 80 ? `${line.slice(0, 80)}…` : line;
}

function fmtMs(ms?: number): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function callMs(c: ToolCall, live: boolean): number | undefined {
  if (typeof c.ms === "number") return c.ms;
  if (c.startedAt === undefined) return undefined;
  const end = c.endedAt ?? (live ? Date.now() : undefined);
  return end === undefined ? undefined : Math.max(0, end - c.startedAt);
}

function metaLine(c: ToolCall, live: boolean): string {
  if (c.status === "fail") return (c.error || "failed").slice(0, 160);
  const bits: string[] = [];
  if (typeof c.rows === "number") bits.push(`${c.rows} row${c.rows === 1 ? "" : "s"}`);
  const ms = callMs(c, live);
  if (ms !== undefined) bits.push(fmtMs(ms));
  if (c.status === "running" && !live) bits.push("No result");
  return bits.join(" · ");
}

function toolLabel(c: ToolCall): string {
  return (
    c.label ||
    (c.name.replace(/_/g, " ").replace(/^get /, "").replace(/^\w/, (ch) => ch.toUpperCase()))
  );
}

interface ToolGroup {
  key: string;
  name: string;
  agent?: string;
  label: string;
  calls: ToolCall[];
}

function groupCalls(calls: ToolCall[]): (ToolCall | ToolGroup)[] {
  const out: (ToolCall | ToolGroup)[] = [];
  let current: ToolGroup | null = null;
  for (const c of calls) {
    if (current && current.name === c.name && current.agent === c.agent) {
      current.calls.push(c);
    } else {
      if (current) out.push(current.calls.length > 1 ? current : current.calls[0]);
      current = { key: `group-${out.length}`, name: c.name, agent: c.agent, label: toolLabel(c), calls: [c] };
    }
  }
  if (current) out.push(current.calls.length > 1 ? current : current.calls[0]);
  return out;
}

function groupState(g: ToolGroup): "running" | "ok" | "fail" {
  if (g.calls.some((c) => c.status === "running")) return "running";
  if (g.calls.some((c) => c.status === "fail")) return "fail";
  return "ok";
}

function groupMeta(g: ToolGroup, live: boolean): string {
  const state = groupState(g);
  if (state === "fail") {
    const failed = g.calls.find((c) => c.status === "fail");
    return (failed?.error || "failed").slice(0, 160);
  }
  const rows = g.calls.reduce((sum, c) => sum + (typeof c.rows === "number" ? c.rows : 0), 0);
  const hasRows = g.calls.some((c) => typeof c.rows === "number");
  const ms = g.calls.reduce((sum, c) => {
    const m = callMs(c, live);
    return m === undefined ? sum : sum + m;
  }, 0);
  const bits = [`${g.calls.length} runs`, ...(hasRows ? [`${rows} row${rows === 1 ? "" : "s"}`] : []), fmtMs(ms)];
  return bits.filter(Boolean).join(" · ");
}

function ToolRow({ c, live }: { c: ToolCall; live: boolean }) {
  const [open, setOpen] = useState(true);
  const [sqlOpen, setSqlOpen] = useState(false);
  const [rerun, setRerun] = useState<
    | null
    | { loading: true }
    | { loading: false; data?: SqlRerunRows; error?: string }
  >(null);
  const [draftSql, setDraftSql] = useState(c.sql || "");
  const spinning = c.status === "running" && live;
  const dotColor = spinning
    ? "var(--color-cyan-signal)"
    : c.status === "fail"
      ? "var(--color-ember)"
      : c.status === "running"
        ? "var(--color-ash-gray)"
        : "var(--color-ink-black)";
  const glyph = spinning ? "" : c.status === "fail" ? "✗" : c.status === "running" ? "○" : "·";
  const label = toolLabel(c);
  const prefix = c.agent ? `${c.agent.charAt(0).toUpperCase() + c.agent.slice(1)} desk · ` : "";
  return (
    <div
      style={{
        paddingLeft: c.agent ? 16 : 0,
        borderBottom: "1px solid var(--color-stone-border)",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 8,
          width: "100%",
          textAlign: "left",
          background: "none",
          border: "none",
          padding: "6px 0",
          cursor: "pointer",
        }}
      >
        <span
          aria-hidden
          className={spinning ? "pulse-dot" : undefined}
          style={{
            width: 7,
            height: 7,
            borderRadius: 9999,
            background: dotColor,
            flexShrink: 0,
            transform: "translateY(-1px)",
            fontSize: 10,
            color: dotColor,
            fontWeight: 600,
          }}
        >
          {glyph}
        </span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span
            style={{
              display: "block",
              fontSize: 13,
              color: "var(--color-ink-black)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {prefix}
            {label}
          </span>
          {metaLine(c, live) && (
            <span
              style={{
                display: "block",
                fontSize: 12,
                color: c.status === "fail" ? "var(--color-ember)" : "var(--color-ash-gray)",
              }}
            >
              {metaLine(c, live)}
            </span>
          )}
        </span>
      </button>
      {open && (
        <div
          style={{
            padding: "4px 0 8px 15px",
            fontSize: 11,
            color: "var(--color-warm-gray)",
          }}
        >
          {c.summary && <div style={{ marginBottom: 4 }}>{c.summary}</div>}
          {c.sql && (
            <div style={{ marginBottom: 4 }}>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSqlOpen((o) => !o);
                }}
                style={{
                  background: "none",
                  border: "none",
                  padding: 0,
                  cursor: "pointer",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--color-cyan-edge)",
                }}
              >
                SQL {sqlOpen ? "▾" : "▸"}
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSqlOpen(true);
                }}
                style={{
                  background: "none",
                  border: "none",
                  padding: 0,
                  marginLeft: 10,
                  cursor: "pointer",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--color-cyan-edge)",
                }}
              >
                Edit & run
              </button>
              {sqlOpen && (
                <div style={{ marginTop: 4 }}>
                  <textarea
                    aria-label="SQL query"
                    value={draftSql}
                    onChange={(e) => setDraftSql(e.target.value)}
                    spellCheck={false}
                    style={{
                      display: "block",
                      width: "100%",
                      minHeight: 96,
                      resize: "vertical",
                      fontFamily: "ui-monospace, monospace",
                      fontSize: 11,
                      lineHeight: 1.5,
                      background: "var(--color-stone-canvas)",
                      border: "1px solid var(--color-stone-border)",
                      borderRadius: 6,
                      padding: 8,
                      color: "var(--color-ink-black)",
                    }}
                  />
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                    <button
                      type="button"
                      className="pill-ghost"
                      disabled={rerun?.loading === true || !draftSql.trim()}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (rerun?.loading || !draftSql.trim()) return;
                        setRerun({ loading: true });
                        rerunSql(draftSql).then(
                          (data) => setRerun({ loading: false, data }),
                          (err) =>
                            setRerun({
                              loading: false,
                              error:
                                err instanceof Error ? err.message : "query failed",
                            }),
                        );
                      }}
                      style={{
                        fontSize: 11,
                        opacity: rerun?.loading || !draftSql.trim() ? 0.5 : 1,
                      }}
                    >
                      {rerun?.loading ? "Running…" : "Run query"}
                    </button>
                    <span style={{ color: "var(--color-ash-gray)" }}>
                      Read-only · 25 row cap
                    </span>
                  </div>
                </div>
              )}
              {rerun && !rerun.loading && rerun.error && (
                <div style={{ marginTop: 4, color: "var(--color-ember)" }}>
                  {rerun.error.slice(0, 160)}
                </div>
              )}
              {rerun && !rerun.loading && rerun.data && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ marginBottom: 2 }}>
                    Re-ran · {rerun.data.rows.length} row
                    {rerun.data.rows.length === 1 ? "" : "s"}
                    {rerun.data.capped ? " (capped)" : ""} ·{" "}
                    {fmtMs(rerun.data.ms)}
                  </div>
                  <div style={{ overflowX: "auto" }}>
                    <table
                      style={{
                        borderCollapse: "collapse",
                        fontFamily: "ui-monospace, monospace",
                        fontSize: 11,
                        color: "var(--color-ink-black)",
                      }}
                    >
                      <thead>
                        <tr>
                          {rerun.data.columns.map((col) => (
                            <th
                              key={col}
                              style={{
                                textAlign: "left",
                                fontWeight: 600,
                                padding: "3px 8px 3px 0",
                                borderBottom:
                                  "1px solid var(--color-stone-border)",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {rerun.data.rows.map((row, i) => (
                          <tr key={i}>
                            {rerun.data!.columns.map((col) => (
                              <td
                                key={col}
                                style={{
                                  padding: "3px 8px 3px 0",
                                  borderBottom:
                                    "1px solid var(--color-stone-border)",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                {String(row[col] ?? "")}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GroupRow({ g, live }: { g: ToolGroup; live: boolean }) {
  const [open, setOpen] = useState(false);
  const state = groupState(g);
  const spinning = state === "running" && live;
  const dotColor =
    state === "fail" ? "var(--color-ember)" : spinning ? "var(--color-cyan-signal)" : "var(--color-ink-black)";
  const glyph = spinning ? "" : state === "fail" ? "✗" : "·";
  const prefix = g.agent ? `${g.agent.charAt(0).toUpperCase() + g.agent.slice(1)} desk · ` : "";
  return (
    <div style={{ borderBottom: "1px solid var(--color-stone-border)" }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 8,
          width: "100%",
          textAlign: "left",
          background: "none",
          border: "none",
          padding: "6px 0",
          cursor: "pointer",
        }}
      >
        <span
          aria-hidden
          className={spinning ? "pulse-dot" : undefined}
          style={{
            width: 7,
            height: 7,
            borderRadius: 9999,
            background: dotColor,
            flexShrink: 0,
            transform: "translateY(-1px)",
            fontSize: 10,
            color: dotColor,
            fontWeight: 600,
          }}
        >
          {glyph}
        </span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span
            style={{
              display: "block",
              fontSize: 13,
              color: "var(--color-ink-black)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {prefix}
            {g.label} · {g.calls.length} runs
          </span>
          <span
            style={{
              display: "block",
              fontSize: 12,
              color: state === "fail" ? "var(--color-ember)" : "var(--color-ash-gray)",
            }}
          >
            {groupMeta(g, live)}
          </span>
        </span>
        <span aria-hidden style={{ fontSize: 12, color: "var(--color-ash-gray)" }}>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && (
        <div style={{ paddingLeft: 15 }}>
          {g.calls.map((c, i) => (
            <ToolRow key={c.id ?? i} c={c} live={live} />
          ))}
        </div>
      )}
    </div>
  );
}

function ThoughtBlock({ text, running, thoughtMs, thoughtStarted }: { text: string; running: boolean; thoughtMs?: number; thoughtStarted?: number }) {
  const [userOpen, setUserOpen] = useState(false);
  if (!text) return null;
  const ms = thoughtMs ?? (thoughtStarted ? Date.now() - thoughtStarted : undefined);
  const suffix = ms === undefined ? "" : ` · ${fmtMs(ms) || "0ms"}`;
  const title = thoughtTitle(text);
  const open = running || userOpen;
  return (
    <details open={open} style={{ marginTop: 8, color: "var(--color-warm-gray)", fontSize: 12 }}>
      <summary
        style={{ cursor: "pointer", listStyle: "none", fontSize: 12 }}
        onClick={(e) => {
          e.preventDefault();
          setUserOpen((o) => !o);
        }}
      >
        <span aria-hidden style={{ marginRight: 7, color: "var(--color-ash-gray)" }}>{running ? "●" : "○"}</span>
        {running ? `Thinking: ${title}` : `Thought: ${title}${suffix}`}
      </summary>
      {open && (
        <div style={{ margin: "7px 0 0 19px", paddingLeft: 10, borderLeft: "1px solid var(--color-stone-border)", whiteSpace: "pre-wrap" }}>
          {text}
        </div>
      )}
    </details>
  );
}

export default function AgentActivity({ ai }: { ai: AiMessage }) {
  const [open, setOpen] = useState(false);
  const [thoughtsOpen, setThoughtsOpen] = useState(false);
  const [liveOpen, setLiveOpen] = useState(false);
  const thoughts = useMemo(() => thoughtsFor(ai), [ai]);
  const calls = useMemo(() => callsFor(ai), [ai]);
  const reasoning = useMemo(() => reasoningFor(ai), [ai]);
  const grouped = useMemo(() => groupCalls(calls), [calls]);
  const running = !ai.done;
  const hasActivity =
    thoughts.length > 0 ||
    calls.length > 0 ||
    reasoning.length > 0 ||
    (ai.activity?.length ?? 0) > 0;

  if (!hasActivity) {
    return (
      <div data-activity-slot style={{ marginBottom: 10 }}>
        {running ? <div role="status" style={{ fontSize: 12, color: "var(--color-ash-gray)" }}>Analyzing…</div> : null}
      </div>
    );
  }

  const label = running
    ? calls.at(-1)?.label || calls.at(-1)?.name.replace(/_/g, " ") || "Analyzing"
    : calls.length > 0
      ? `Used ${calls.length} tool${calls.length === 1 ? "" : "s"}`
      : "Analysis complete";
  const liveRows = (
    <div style={{ margin: "7px 0 0 19px", paddingLeft: 10, borderLeft: "1px solid var(--color-stone-border)" }}>
      {grouped.map((entry) =>
        "calls" in entry ? (
          <GroupRow key={entry.key} g={entry} live={running} />
        ) : (
          <ToolRow key={entry.id ?? entry.name} c={entry} live={running} />
        ),
      )}
    </div>
  );

  return (
    <div data-activity-slot style={{ marginBottom: 10 }}>
      {(ai.activity?.length ?? 0) > 0 ? (
        <ActivityTimeline items={ai.activity!} running={running} />
      ) : running && calls.length >= 2 ? (
        <details open={liveOpen} style={{ color: "var(--color-warm-gray)", fontSize: 12 }}>
          <summary
            style={{ cursor: "pointer", listStyle: "none" }}
            onClick={(e) => {
              e.preventDefault();
              setLiveOpen((o) => !o);
            }}
          >
            <span aria-hidden style={{ marginRight: 7, color: "var(--color-ash-gray)" }}>●</span>
            {`Did ${calls.length} things`}
          </summary>
          {liveOpen && liveRows}
        </details>
      ) : running ? (
        <div style={{ color: "var(--color-warm-gray)", fontSize: 12 }}>
          <div>
            <span aria-hidden style={{ marginRight: 7, color: "var(--color-ash-gray)" }}>●</span>
            {label}
          </div>
          {liveRows}
        </div>
      ) : (
        <details open={open} style={{ color: "var(--color-warm-gray)", fontSize: 12 }}>
          <summary
            style={{ cursor: "pointer", listStyle: "none" }}
            onClick={(e) => {
              e.preventDefault();
              setOpen((o) => !o);
            }}
          >
            <span aria-hidden style={{ marginRight: 7, color: "var(--color-ash-gray)" }}>·</span>
            {label}
          </summary>
          {open && (
          <div style={{ margin: "7px 0 0 19px", paddingLeft: 10, borderLeft: "1px solid var(--color-stone-border)" }}>
            {grouped.map((entry) =>
              "calls" in entry ? (
                <GroupRow key={entry.key} g={entry} live={running} />
              ) : (
                <ToolRow key={entry.id ?? entry.name} c={entry} live={running} />
              ),
            )}
          </div>
          )}
        </details>
      )}
      <ThoughtBlock text={reasoning} running={running} thoughtMs={ai.thoughtMs} thoughtStarted={ai.thoughtStarted} />
      {thoughts.length > 0 && (
        <details open={thoughtsOpen} style={{ marginTop: 8, color: "var(--color-warm-gray)", fontSize: 12 }}>
          <summary
            style={{ cursor: "pointer", listStyle: "none", fontSize: 12, color: "var(--color-ash-gray)" }}
            onClick={(e) => {
              e.preventDefault();
              setThoughtsOpen((o) => !o);
            }}
          >
            Progress updates · {thoughts.length}
          </summary>
          {thoughtsOpen && (
          <div style={{ margin: "7px 0 0 19px", paddingLeft: 10, borderLeft: "1px solid var(--color-stone-border)" }}>
            {thoughts.map((text, index) => <div key={`thought-${index}`}>{text}</div>)}
          </div>
          )}
        </details>
      )}
    </div>
  );
}

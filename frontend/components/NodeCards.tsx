"use client";

import { useState } from "react";
import { AiMessage, NodeName } from "../lib/chat";
import AutoChart from "./AutoChart";
import CompareView from "./CompareView";
import DataTable from "./DataTable";

const ORDER: NodeName[] = ["entry", "data_retrieval", "tools", "analytics", "presentation"];

const LABELS: Record<NodeName, string> = {
  entry: "Planning",
  data_retrieval: "Retrieving data",
  tools: "Running tools",
  analytics: "Analyzing stats",
  presentation: "Synthesizing answer",
};

export default function NodeCards({ ai }: { ai: AiMessage }) {
  const names = ORDER.filter((n) => ai.nodes[n]);
  const [open, setOpen] = useState(false);
  const [pageState, setPageState] = useState<number | null>(null);
  const [heat, setHeat] = useState(false);
  const [viewMode, setViewMode] = useState<"table" | "chart">("table");

  if (!names.length) return null;

  const anyRunning = names.some((n) => ai.nodes[n]!.status === "running");
  const isDone = ai.done;
  const showTrace = open || (!isDone && anyRunning);

  const tables: {
    tool: string;
    rows?: unknown;
    meta?: {
      source?: string;
      fetched_at?: string;
      stat_category?: string;
      sql?: string;
      links?: { watch?: string };
    };
  }[] = [];

  for (const n of names) {
    for (const t of ai.nodes[n]!.tables) tables.push(t);
  }

  const preferred = tables.findIndex(
    (t) =>
      t.tool === "get_compare" ||
      t.tool === "get_preview" ||
      t.tool === "get_rapm" ||
      t.tool === "get_finder",
  );
  const fallback = preferred >= 0 ? preferred : tables.length - 1;
  const table = tables[Math.min(pageState ?? fallback, Math.max(tables.length - 1, 0))];
  const page = Math.min(pageState ?? fallback, Math.max(tables.length - 1, 0));
  const setPage = (n: number) => setPageState(Math.max(0, Math.min(n, tables.length - 1)));

  // Extract all thoughts and tool calls in chronological sequence
  const allEvents: { type: "thought" | "tool" | "result" | "summary"; text: string; sub?: string }[] = [];
  for (const n of names) {
    const s = ai.nodes[n]!;
    for (const c of s.toolCalls) {
      allEvents.push({ type: "tool", text: c.name, sub: JSON.stringify(c.args) });
    }
    for (const t of s.thoughts) {
      allEvents.push({ type: "thought", text: t });
    }
    for (const r of s.toolResults) {
      const rec = r as unknown as Record<string, unknown>;
      if (rec.agent && typeof rec.summary === "string") {
        allEvents.push({ type: "summary", text: `${String(rec.agent)} desk`, sub: rec.summary.slice(0, 300) });
      } else if (rec.error) {
        allEvents.push({ type: "result", text: `${String(rec.tool || "tool")} failed`, sub: String(rec.error).slice(0, 160) });
      }
    }
  }

  const durationSec = ai.thoughtMs ? (ai.thoughtMs / 1000).toFixed(1) : null;

  return (
    <div style={{ marginTop: 14 }}>
      {/* Reasoning Trigger Header (OpenAI / Claude 3.7 style) */}
      <div style={{ marginBottom: 10 }}>
        <button
          onClick={() => setOpen(!open)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 12px",
            background: "var(--color-stone-canvas)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 8,
            fontSize: 12,
            color: "var(--color-warm-gray)",
            cursor: "pointer",
            transition: "all 140ms ease",
          }}
        >
          {!isDone ? (
            <>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "var(--color-cyan-signal)",
                  display: "inline-block",
                }}
                className="shimmer"
              />
              <span style={{ fontWeight: 500, color: "var(--color-ink-black)" }}>
                Thinking...
              </span>
            </>
          ) : (
            <>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--color-cyan-signal)" }}>
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>
                Thought {durationSec ? `for ${durationSec}s` : "process"}
              </span>
            </>
          )}
          <span style={{ fontSize: 10, opacity: 0.7 }}>
            {showTrace ? "▲ Hide" : "▼ Show"}
          </span>
        </button>
      </div>

      {/* Expanded Live Reasoning Stream */}
      {showTrace && (
        <div
          style={{
            background: "var(--color-stone-canvas)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 10,
            padding: "14px 16px",
            marginBottom: 14,
            fontSize: 13,
            lineHeight: 1.6,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {names.map((n) => {
              const s = ai.nodes[n]!;
              const isRunning = s.status === "running";
              return (
                <div key={n} style={{ borderBottom: "1px solid var(--color-stone-border)", paddingBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: isRunning
                          ? "var(--color-cyan-signal)"
                          : s.status === "complete"
                          ? "var(--color-ink-black)"
                          : "var(--color-warm-gray)",
                      }}
                    />
                    <span style={{ fontWeight: 600, fontSize: 12, color: "var(--color-ink-black)" }}>
                      {LABELS[n]}
                    </span>
                    {s.toolCalls.length > 0 && (
                      <span style={{ fontSize: 11, color: "var(--color-warm-gray)" }}>
                        ({s.toolCalls.length} tool{s.toolCalls.length > 1 ? "s" : ""})
                      </span>
                    )}
                  </div>

                  {s.thoughts.map((th, idx) => (
                    <div key={`th-${idx}`} style={{ color: "var(--color-warm-gray)", fontSize: 12, paddingLeft: 14, marginTop: 2 }}>
                      {th}
                    </div>
                  ))}

                  {s.toolCalls.length > 0 && (
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", paddingLeft: 14, marginTop: 6 }}>
                      {s.toolCalls.map((c, idx) => (
                        <span
                          key={idx}
                          style={{
                            fontSize: 11,
                            fontFamily: "monospace",
                            background: "var(--color-pure-white)",
                            border: "1px solid var(--color-stone-border)",
                            borderRadius: 6,
                            padding: "2px 8px",
                            color: "var(--color-ink-black)",
                          }}
                        >
                          ⚡ {c.name}
                        </span>
                      ))}
                    </div>
                  )}

                  {s.toolResults.map((r, idx) => {
                    const rec = r as unknown as Record<string, unknown>;
                    if (rec.agent && typeof rec.summary === "string") {
                      return (
                        <div key={`sum-${idx}`} style={{ fontSize: 12, color: "var(--color-warm-gray)", paddingLeft: 14, marginTop: 4 }}>
                          <strong style={{ color: "var(--color-ink-black)" }}>{String(rec.agent)} desk:</strong> {rec.summary.slice(0, 240)}
                        </div>
                      );
                    }
                    if (rec.error) {
                      return (
                        <div key={`err-${idx}`} style={{ fontSize: 12, color: "#e11d48", paddingLeft: 14, marginTop: 4 }}>
                          {String(rec.tool || "tool")} failed: {String(rec.error).slice(0, 140)}
                        </div>
                      );
                    }
                    return null;
                  })}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Interactive Data Artifact Card (Claude Artifact style) */}
      {table && (
        <div
          style={{
            border: "1px solid var(--color-stone-border)",
            borderRadius: 12,
            padding: "16px",
            background: "var(--color-pure-white)",
            boxShadow: "var(--shadow-card)",
            marginTop: 12,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 8,
              borderBottom: "1px solid var(--color-stone-border)",
              paddingBottom: 12,
              marginBottom: 12,
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: 13, color: "var(--color-ink-black)" }}>
                {table.tool.replace("get_", "").replace(/_/g, " ").toUpperCase()}
                {table.meta?.stat_category ? ` · ${table.meta.stat_category}` : ""}
              </div>
              <div style={{ fontSize: 11, color: "var(--color-ash-gray)", marginTop: 2 }}>
                {table.meta?.source ? `Source: ${table.meta.source}` : "Source: NBA Warehouse"}
                {table.meta?.fetched_at ? ` · ${String(table.meta.fetched_at).slice(0, 10)}` : ""}
                {table.meta?.links?.watch && (
                  <a href={table.meta.links.watch} target="_blank" rel="noreferrer" style={{ marginLeft: 6, color: "var(--color-cyan-edge)" }}>
                    Watch video
                  </a>
                )}
              </div>
            </div>

            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <button
                className={viewMode === "table" ? "tab-active" : "pill-ghost"}
                style={{ fontSize: 11, padding: "3px 10px" }}
                onClick={() => setViewMode("table")}
              >
                Table
              </button>
              <button
                className={viewMode === "chart" ? "tab-active" : "pill-ghost"}
                style={{ fontSize: 11, padding: "3px 10px" }}
                onClick={() => setViewMode("chart")}
              >
                Chart
              </button>
              <button
                className={heat ? "tab-active" : "pill-ghost"}
                style={{ fontSize: 11, padding: "3px 10px" }}
                onClick={() => setHeat(!heat)}
                title="Toggle heat map gradient"
              >
                Heat
              </button>
              {tables.length > 1 && (
                <div style={{ display: "flex", gap: 4, marginLeft: 6 }}>
                  <button
                    className="pill-ghost"
                    style={{ fontSize: 11, padding: "3px 8px" }}
                    disabled={page === 0}
                    onClick={() => setPage(page - 1)}
                  >
                    ‹ Prev
                  </button>
                  <span style={{ fontSize: 11, color: "var(--color-warm-gray)", display: "flex", alignItems: "center" }}>
                    {page + 1}/{tables.length}
                  </span>
                  <button
                    className="pill-ghost"
                    style={{ fontSize: 11, padding: "3px 8px" }}
                    disabled={page >= tables.length - 1}
                    onClick={() => setPage(page + 1)}
                  >
                    Next ›
                  </button>
                </div>
              )}
            </div>
          </div>

          {table.meta?.sql && (
            <details style={{ fontSize: 11, color: "var(--color-warm-gray)", marginBottom: 12 }}>
              <summary style={{ cursor: "pointer", fontWeight: 500 }}>View SQL</summary>
              <pre style={{ whiteSpace: "pre-wrap", margin: "6px 0 0", background: "var(--color-stone-canvas)", padding: 8, borderRadius: 6, fontSize: 11 }}>
                {table.meta.sql}
              </pre>
            </details>
          )}

          {table.tool === "get_compare" || table.tool === "get_preview" ? (
            <CompareView rows={table.rows} />
          ) : viewMode === "chart" ? (
            <AutoChart table={table as { rows?: unknown }} />
          ) : (
            <DataTable rows={(table.rows as { rows?: unknown })?.rows ?? table.rows} heat={heat} />
          )}
        </div>
      )}
    </div>
  );
}

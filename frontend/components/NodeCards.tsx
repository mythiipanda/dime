"use client";

import { useState } from "react";
import { AiMessage, NodeName } from "../lib/chat";
import AutoChart from "./AutoChart";
import CompareView from "./CompareView";
import DataTable from "./DataTable";

const ORDER: NodeName[] = ["entry", "data_retrieval", "tools", "analytics", "presentation"];

const LABELS: Record<NodeName, string> = {
  entry: "Plan",
  data_retrieval: "Retrieve",
  tools: "Tools",
  analytics: "Analyze",
  presentation: "Answer",
};

function chipStyle(status: string): React.CSSProperties {
  return {
    fontSize: 10,
    borderRadius: 9999,
    padding: "2px 8px",
    background: status === "complete" ? "#1c1917" : status === "error" ? "#e8e6e5" : "#c1e1f7",
    color: status === "complete" ? "#ffffff" : "#0c0a09",
  };
}

export default function NodeCards({ ai }: { ai: AiMessage }) {
  const names = ORDER.filter((n) => ai.nodes[n]);
  const [open, setOpen] = useState(false);
  const [pageState, setPageState] = useState<number | null>(null);
  const [heat, setHeat] = useState(false);
  if (!names.length) return null;
  const done = names.filter((n) => ai.nodes[n]!.status === "complete").length;
  const anyRunning = names.some((n) => ai.nodes[n]!.status === "running");
  const showTrace = open || anyRunning;
  const tables: { tool: string; rows?: unknown; meta?: { source?: string; fetched_at?: string; stat_category?: string; links?: { watch?: string } } }[] = [];
  for (const n of names) {
    for (const t of ai.nodes[n]!.tables) tables.push(t);
  }
  const preferred = tables.findIndex((t) =>
    t.tool === "get_compare" || t.tool === "get_preview" ||
    t.tool === "get_rapm" || t.tool === "get_finder",
  );
  const fallback = preferred >= 0 ? preferred : tables.length - 1;
  const table = tables[Math.min(pageState ?? fallback, Math.max(tables.length - 1, 0))];
  const page = Math.min(pageState ?? fallback, Math.max(tables.length - 1, 0));
  const setPage = (n: number) => setPageState(
    Math.max(0, Math.min(n, tables.length - 1)));
  return (
    <div style={{ marginTop: 12 }}>
      <button
        onClick={() => setOpen(!open)}
        className="pill-ghost"
        style={{ fontSize: 12 }}
      >
        {ai.thoughtMs !== undefined
          ? `Thought for ${(ai.thoughtMs / 1000).toFixed(0)}s · `
          : ""}
        Thinking: {done}/{names.length} steps {open || anyRunning ? "hide" : "show"}
      </button>
      {showTrace && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
          {names.map((n) => {
            const s = ai.nodes[n]!;
            return (
              <div
                key={n}
                style={{
                  border: "1px solid #e8e6e5",
                  borderRadius: 10,
                  padding: "12px 16px",
                  background: "#fafaf9",
                }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ fontWeight: 500 }}>{LABELS[n]}</span>
                  <span style={chipStyle(s.status)}>{s.status}</span>
                </div>
                {s.toolCalls.length > 0 && (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                    {s.toolCalls.map((c, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: 11,
                          border: "1px solid #e8e6e5",
                          borderRadius: 9999,
                          padding: "2px 8px",
                          color: "#78716c",
                          background: "#ffffff",
                        }}
                      >
                        {c.name}
                      </span>
                    ))}
                  </div>
                )}
                {s.thoughts.map((t, i) => (
                  <div key={`th${i}`} style={{ fontSize: 12, color: "#a8a29e", marginTop: 4 }}>
                    {t}
                  </div>
                ))}
                {s.toolResults.map((r, i) => {
                  const rec = r as unknown as Record<string, unknown>;
                  if (rec.agent && typeof rec.summary === "string") {
                    return (
                      <div key={`a${i}`} style={{ fontSize: 12, marginTop: 6 }}>
                        <span style={{ fontWeight: 500 }}>{String(rec.agent)} desk: </span>
                        {rec.summary.slice(0, 300)}
                      </div>
                    );
                  }
                  if (rec.error) {
                    return (
                      <div key={`e${i}`} style={{ fontSize: 12, color: "#78716c", marginTop: 4 }}>
                        {String(rec.tool || "tool")} failed: {String(rec.error).slice(0, 160)}
                      </div>
                    );
                  }
                  return null;
                })}
              </div>
            );
          })}
        </div>
      )}
      {table && (
        <div
          style={{
            border: "1px solid #e8e6e5",
            borderRadius: 10,
            padding: "12px 16px",
            background: "#ffffff",
            marginTop: 8,
          }}
        >
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
            <span style={{ fontSize: 12, color: "#78716c" }}>
              Insight {Math.min(page + 1, tables.length)} of {tables.length}: {table.tool}
              {table.meta?.source ? ` from ${table.meta.source}` : ""}
              {table.meta?.fetched_at ? ` at ${String(table.meta.fetched_at).slice(0, 10)}` : ""}
              {table.meta?.links?.watch ? (
                <a href={table.meta.links.watch} target="_blank" rel="noreferrer"
                  style={{ fontSize: 12, marginLeft: 6 }}>
                  Watch
                </a>
              ) : null}
            </span>
            <span style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
              <button
                className={heat ? "tab-active" : "pill-ghost"}
                style={{ fontSize: 11, padding: "2px 10px" }}
                onClick={() => setHeat(!heat)}
              >
                Heat
              </button>
              {tables.length > 1 && (
                <span style={{ display: "flex", gap: 4 }}>
                  <button
                    className="pill-ghost"
                    style={{ fontSize: 11, padding: "2px 10px" }}
                    disabled={page === 0}
                    onClick={() => setPage(page - 1)}
                  >
                    Prev
                  </button>
                  <button
                    className="pill-ghost"
                    style={{ fontSize: 11, padding: "2px 10px" }}
                    disabled={page >= tables.length - 1}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                  </button>
                </span>
              )}
            </span>
          </div>
          {table.tool === "get_compare" || table.tool === "get_preview" ? (
            <CompareView rows={table.rows} />
          ) : (
            <div>
              <AutoChart table={table as { rows?: unknown }} />
              <DataTable rows={(table.rows as { rows?: unknown })?.rows ?? table.rows} heat={heat} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

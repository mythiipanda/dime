"use client";

import { useState } from "react";
import { NodeName, ToolCall, ToolResult } from "../lib/chat";

const NODE_LABEL: Partial<Record<NodeName, string>> = {
  entry: "Planning",
  data_retrieval: "Retrieving data",
  tools: "Running tools",
  analytics: "Analyzing",
};

function resultSummary(r: ToolResult): string {
  const rec = r as unknown as Record<string, unknown>;
  if (typeof rec.error === "string" && rec.error) return rec.error.slice(0, 160);
  if (rec.agent && typeof rec.summary === "string") return (rec.summary as string).slice(0, 160);
  const rows = rec.rows;
  const count = Array.isArray(rows)
    ? rows.length
    : rows && typeof rows === "object" && Array.isArray((rows as { rows?: unknown }).rows)
      ? ((rows as { rows?: unknown }).rows as unknown[]).length
      : typeof r.meta?.rows === "number"
        ? r.meta.rows
        : null;
  if (count !== null) return `${count} row${count === 1 ? "" : "s"}`;
  if (r.ok === false) return "failed";
  return "done";
}

interface RowProps {
  node: NodeName;
  call: ToolCall;
  result?: ToolResult;
  running: boolean;
}

export function ToolCallRow({ node, call, result, running }: RowProps) {
  const [open, setOpen] = useState(false);
  const failed = Boolean(result && (result.ok === false || result.error));
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 7,
          padding: "2px 0",
          background: "transparent",
          border: "none",
          fontSize: 12.5,
          color: "var(--color-warm-gray)",
          cursor: "pointer",
        }}
      >
        <span
          aria-hidden
          style={{
            width: 13,
            height: 13,
            borderRadius: "50%",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 9,
            fontWeight: 700,
            flexShrink: 0,
            background: failed
              ? "transparent"
              : result
                ? "var(--color-ink-black)"
                : "var(--color-cyan-signal)",
            color: failed ? "#e11d48" : "var(--color-pure-white)",
            border: failed ? "1px solid #e11d48" : "1px solid transparent",
            animation: !result ? "dime-caret 900ms steps(2) infinite" : undefined,
          }}
        >
          {result ? (failed ? "!" : "✓") : ""}
        </span>
        <span style={{ fontFamily: "monospace", fontSize: 12, color: "var(--color-ink-black)" }}>
          {call.name}
        </span>
        {result && (
          <span style={{ fontSize: 11.5, color: failed ? "#e11d48" : "var(--color-ash-gray)" }}>
            {resultSummary(result)}
          </span>
        )}
        {running && !result && <span style={{ fontSize: 11.5 }}>running</span>}
      </button>
      {open && (
        <div
          style={{
            margin: "2px 0 6px 20px",
            background: "var(--color-stone-canvas)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 8,
            padding: "8px 10px",
            fontSize: 11.5,
          }}
        >
          <div style={{ color: "var(--color-ash-gray)", marginBottom: 4 }}>
            {NODE_LABEL[node] || node} · args
          </div>
          <pre
            style={{
              margin: 0,
              whiteSpace: "pre-wrap",
              fontFamily: "monospace",
              fontSize: 11,
              color: "var(--color-ink-black)",
            }}
          >
            {JSON.stringify(call.args, null, 2)}
          </pre>
          {result && (
            <div style={{ marginTop: 6, color: failed ? "#e11d48" : "var(--color-warm-gray)" }}>
              {resultSummary(result)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface GroupProps {
  node: NodeName;
  calls: ToolCall[];
  results: ToolResult[];
  running: boolean;
}

export function ToolCallGroup({ node, calls, results, running }: GroupProps) {
  if (!calls.length && !results.length) return null;
  const used = new Set<number>();
  const pairs = calls.map((call) => {
    const idx = results.findIndex((r, i) => !used.has(i) && r.tool === call.name);
    const result = idx >= 0 ? results[idx] : undefined;
    if (idx >= 0) used.add(idx);
    return { call, result };
  });
  const orphans = results.filter((_, i) => !used.has(i));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, marginBottom: 6 }}>
      {pairs.map((p, i) => (
        <ToolCallRow
          key={`${p.call.name}-${i}`}
          node={node}
          call={p.call}
          result={p.result}
          running={running && !p.result}
        />
      ))}
      {orphans.map((r, i) => (
        <div key={`orphan-${i}`} style={{ fontSize: 12, color: r.error ? "#e11d48" : "var(--color-warm-gray)", paddingLeft: 20 }}>
          {r.error ? `${r.tool} failed: ${String(r.error).slice(0, 140)}` : `${r.tool}: ${resultSummary(r)}`}
        </div>
      ))}
    </div>
  );
}

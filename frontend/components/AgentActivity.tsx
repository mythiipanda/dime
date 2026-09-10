"use client";

import { useEffect, useMemo, useState } from "react";
import type { AiMessage, NodeName, ToolCall } from "../lib/chat";

const AGENT_NODES: NodeName[] = ["entry", "data_retrieval", "tools", "analytics"];

const NODE_LABELS: Record<string, string> = {
  entry: "Planning",
  data_retrieval: "Retrieving data",
  tools: "Running tools",
  analytics: "Analyzing",
  presentation: "Writing answer",
};

function thoughtsFor(ai: AiMessage): string[] {
  const out: string[] = [];
  for (const n of AGENT_NODES) {
    const s = ai.nodes[n];
    if (s) out.push(...s.thoughts);
  }
  return out;
}

function callsFor(ai: AiMessage): ToolCall[] {
  const out: ToolCall[] = [];
  for (const n of AGENT_NODES) {
    const s = ai.nodes[n];
    if (s) out.push(...s.toolCalls);
  }
  return out;
}

function liveThoughtsFor(ai: AiMessage): { node: NodeName; text: string; agent?: string }[] {
  const out: { node: NodeName; text: string; agent?: string }[] = [];
  for (const n of AGENT_NODES) {
    const s = ai.nodes[n];
    if (s?.liveThought) out.push({ node: n, text: stripMd(s.liveThought), agent: s.liveThoughtAgent });
  }
  return out;
}

const stripMd = (s: string) => s.replace(/\*\*|__|`/g, "");

function fmtMs(ms?: number): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function metaLine(c: ToolCall): string {
  if (c.status === "fail") return (c.error || "failed").slice(0, 160);
  const bits: string[] = [];
  if (typeof c.rows === "number") bits.push(`${c.rows} row${c.rows === 1 ? "" : "s"}`);
  if (typeof c.ms === "number") bits.push(fmtMs(c.ms));
  return bits.join(" · ");
}

function ToolRow({ c }: { c: ToolCall }) {
  const [open, setOpen] = useState(false);
  const [sqlOpen, setSqlOpen] = useState(false);
  const dotColor =
    c.status === "running"
      ? "var(--color-cyan-signal)"
      : c.status === "fail"
        ? "#e11d48"
        : "var(--color-ink-black)";
  const glyph = c.status === "running" ? "" : c.status === "fail" ? "!" : "✓";
  const label = c.label || c.name.replace(/_/g, " ");
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
          className={c.status === "running" ? "pulse-dot" : undefined}
          style={{
            width: 7,
            height: 7,
            borderRadius: 9999,
            background: dotColor,
            flexShrink: 0,
            transform: "translateY(-1px)",
            fontSize: 10,
            color: dotColor,
            fontWeight: 700,
          }}
        >
          {glyph}
        </span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span
            style={{
              display: "block",
              fontSize: 12.5,
              color: "var(--color-ink-black)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {prefix}
            {label}
          </span>
          {metaLine(c) && (
            <span
              style={{
                display: "block",
                fontSize: 11.5,
                color: c.status === "fail" ? "#e11d48" : "var(--color-ash-gray)",
              }}
            >
              {metaLine(c)}
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
              {sqlOpen && (
                <pre
                  style={{
                    fontFamily: "ui-monospace, monospace",
                    fontSize: 11,
                    lineHeight: 1.5,
                    background: "var(--color-stone-canvas)",
                    border: "1px solid var(--color-stone-border)",
                    borderRadius: 6,
                    padding: 8,
                    overflowX: "auto",
                    margin: "4px 0 0",
                    color: "var(--color-ink-black)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {c.sql}
                </pre>
              )}
            </div>
          )}
          {c.args && Object.keys(c.args).length > 0 && (
            <pre
              style={{
                fontFamily: "ui-monospace, monospace",
                fontSize: 11,
                background: "var(--color-stone-canvas)",
                border: "1px solid var(--color-stone-border)",
                borderRadius: 6,
                padding: 8,
                overflowX: "auto",
                margin: 0,
              }}
            >
              {JSON.stringify(c.args, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function AgentActivity({ ai }: { ai: AiMessage }) {
  const thoughts = useMemo(() => thoughtsFor(ai), [ai]);
  const calls = useMemo(() => callsFor(ai), [ai]);
  const live = useMemo(() => liveThoughtsFor(ai), [ai]);
  const running = !ai.done;
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (ai.text.length > 0 || ai.done) setOpen(false);
  }, [ai.text, ai.done]);

  const runningCall = [...calls].reverse().find((c) => c.status === "running");
  const runningNode = AGENT_NODES.find(
    (n) => ai.nodes[n]?.status === "running",
  );
  const headerText = runningCall
    ? runningCall.label || runningCall.name.replace(/_/g, " ")
    : ai.streaming || ai.text.length > 0
      ? "Writing answer"
      : runningNode
        ? `${NODE_LABELS[runningNode] || runningNode}…`
        : "Starting…";

  const hasActivity = thoughts.length > 0 || calls.length > 0 || live.length > 0;

  if (!running && !open) {
    const secs = ai.thoughtMs ? `${(ai.thoughtMs / 1000).toFixed(0)}s` : "";
    const pill = secs
      ? `Thought for ${secs} · ${calls.length} tool${calls.length === 1 ? "" : "s"}`
      : "Thought process";
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="pill-ghost"
        style={{ fontSize: 12, marginBottom: 8 }}
      >
        {pill}
      </button>
    );
  }

  return (
    <div style={{ marginBottom: 10 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          background: "none",
          border: "none",
          padding: "4px 0",
          cursor: "pointer",
          width: "100%",
          textAlign: "left",
        }}
      >
        {running && (
          <span
            aria-hidden
            className="pulse-dot"
            style={{
              width: 7,
              height: 7,
              borderRadius: 9999,
              background: "var(--color-cyan-signal)",
              flexShrink: 0,
            }}
          />
        )}
        <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--color-ink-black)" }}>
          {running ? headerText : "Thought process"}
        </span>
        <span style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && (
        <div style={{ marginTop: 2 }}>
          {!hasActivity && running && (
            <div style={{ fontSize: 12, color: "var(--color-ash-gray)", padding: "4px 0" }}>
              Starting…
            </div>
          )}
          {thoughts.map((t, i) => (
            <div
              key={`t-${i}`}
              style={{ fontSize: 12.5, color: "var(--color-warm-gray)", padding: "2px 0" }}
            >
              {t}
            </div>
          ))}
          {live.map((l, i) => {
            const isLive = running && i === live.length - 1;
            const prefix = l.agent
              ? `${l.agent.charAt(0).toUpperCase() + l.agent.slice(1)} desk · `
              : "";
            return (
              <div
                key={`live-${i}`}
                style={{ fontSize: 12.5, color: "var(--color-warm-gray)", padding: "2px 0" }}
              >
                <span style={{ color: "var(--color-ash-gray)" }}>{prefix}</span>
                {l.text}
                {isLive && <span className="caret" aria-hidden />}
              </div>
            );
          })}
          {calls.length > 0 && (
            <div style={{ marginTop: thoughts.length ? 6 : 0 }}>
              {calls.map((c, i) => (
                <ToolRow key={`c-${i}`} c={c} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

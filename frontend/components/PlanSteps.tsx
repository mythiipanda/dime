"use client";

import { AiMessage, NodeName } from "../lib/chat";

const ORDER: NodeName[] = ["entry", "data_retrieval", "tools", "analytics"];

const LABELS: Record<NodeName, string> = {
  entry: "Planning",
  data_retrieval: "Retrieving data",
  tools: "Running tools",
  analytics: "Analyzing",
  presentation: "Writing",
};

function activeLabel(ai: AiMessage): string | null {
  for (const n of ORDER) {
    if (ai.nodes[n]?.status === "running") return `${LABELS[n]}...`;
  }
  if (ai.streaming || (ai.text && !ai.done)) return "Writing answer...";
  return null;
}

export default function PlanSteps({ ai }: { ai: AiMessage }) {
  if (ai.done) return null;
  const label = activeLabel(ai);
  if (!label) return null;
  const completed = ORDER.filter((n) => ai.nodes[n]?.status === "complete").length;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 8,
        fontSize: 12.5,
        color: "var(--color-warm-gray)",
      }}
    >
      <span
        aria-hidden
        style={{
          width: 13,
          height: 13,
          borderRadius: "50%",
          background: "var(--color-cyan-signal)",
          flexShrink: 0,
          animation: "dime-caret 900ms steps(2) infinite",
        }}
      />
      <span style={{ fontWeight: 500, color: "var(--color-ink-black)" }}>{label}</span>
      {completed > 0 && (
        <span style={{ color: "var(--color-ash-gray)" }}>
          {completed}/{ORDER.length} steps done
        </span>
      )}
    </div>
  );
}

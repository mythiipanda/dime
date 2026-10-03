"use client";

import type { CSSProperties } from "react";
import {
  parseSseText,
  runIdOf,
  shortRevision,
  type BindingDiagnostic,
} from "../lib/diagnostics";

function declaredText(value: Record<string, unknown> | null): string {
  if (!value) return "";
  const v = value.value;
  return typeof v === "string" || typeof v === "number" ? String(v) : "";
}

export function RevisionCard({ info }: { info: { revision: string; runtime: string } | null }) {
  return (
    <div
      style={{
        border: "1px solid var(--color-stone-border)",
        borderRadius: 10,
        padding: "10px 14px",
        background: "var(--color-pure-white)",
        fontSize: 12,
        color: "var(--color-warm-gray)",
        marginBottom: 16,
        fontVariantNumeric: "tabular-nums",
      }}
    >
      {info ? (
        <>
          revision{" "}
          <span style={{ fontWeight: 500, color: "var(--color-ink-black)" }}>
            {shortRevision(info.revision)}
          </span>{" "}
          · {info.runtime}
        </>
      ) : (
        "revision unavailable"
      )}
    </div>
  );
}

export function RunMetaHeader({
  text,
  revision,
  runtime,
}: {
  text: string;
  revision: string;
  runtime: string;
}) {
  if (!revision.trim()) return null;
  const runId = text.trim() ? runIdOf(parseSseText(text)) : null;
  return (
    <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 6 }}>
      {runId ? `run ${runId.slice(0, 12)} · ` : ""}
      {revision.trim().slice(0, 8)}
      {runtime.trim() ? ` · ${runtime.trim()}` : ""}
    </div>
  );
}

export function DiagnosticsTable({ rows }: { rows: BindingDiagnostic[] }) {
  if (!rows.length) return null;
  const cell: CSSProperties = {
    padding: "6px 10px 6px 0",
    fontSize: 12,
    color: "var(--color-warm-gray)",
    verticalAlign: "top",
    textAlign: "left",
  };
  return (
    <div style={{ overflowX: "auto", marginTop: 16 }}>
      <table style={{ borderCollapse: "collapse", minWidth: 1100 }}>
        <thead>
          <tr>
            {["#", "Output", "Requirement", "Domain", "Capability", "Selector", "Subject", "Declared", "Reanchored", "Rejection"].map(
              (h) => (
                <th
                  key={h}
                  style={{
                    ...cell,
                    fontSize: 11,
                    fontWeight: 500,
                    whiteSpace: "nowrap",
                    borderBottom: "1px solid var(--color-stone-muted)",
                  }}
                >
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((d, i) => (
            <tr key={`${d.output_id}-${d.claim_index}-${i}`}>
              <td style={{ ...cell, fontVariantNumeric: "tabular-nums" }}>{d.claim_index}</td>
              <td style={{ ...cell, fontWeight: 500, color: "var(--color-ink-black)" }}>
                {d.output_id}
              </td>
              <td style={cell}>
                {d.requirement_kind}
                {d.requirement_id ? ` · ${d.requirement_id}` : ""}
              </td>
              <td style={cell}>{d.domain || ""}</td>
              <td style={cell}>{d.evidence_capability || ""}</td>
              <td style={{ ...cell, fontFamily: "monospace" }}>
                {d.selector || ""}
                <div style={{ color: "var(--color-ash-gray)" }}>
                  {[d.row_selector, d.subject_selector].filter(Boolean).join(" · ")}
                </div>
              </td>
              <td style={cell}>
                {[d.subject_entity_type, d.subject_entity_id].filter(Boolean).join(" · ")}
              </td>
              <td style={{ ...cell, fontVariantNumeric: "tabular-nums" }}>
                {declaredText(d.declared_value)}
              </td>
              <td style={cell}>{d.reanchor_changed ? "changed" : "same"}</td>
              <td style={{ ...cell, color: "var(--color-ink-black)" }}>{d.rejection}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

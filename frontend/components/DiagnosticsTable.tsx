"use client";

import type { CSSProperties } from "react";
import type { BindingDiagnostic } from "../lib/diagnostics";

function declaredText(value: Record<string, unknown> | null): string {
  if (!value) return "";
  const v = value.value;
  return typeof v === "string" || typeof v === "number" ? String(v) : "";
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
      <table style={{ borderCollapse: "collapse", minWidth: 900 }}>
        <thead>
          <tr>
            {["#", "Output", "Requirement", "Selector", "Subject", "Declared", "Reanchored", "Rejection"].map(
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

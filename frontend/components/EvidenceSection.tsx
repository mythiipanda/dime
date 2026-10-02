"use client";

import { useState } from "react";
import type { AiMessage } from "../lib/chat";
import { summarizeEvidence } from "../lib/evidence";
import type { EvidenceRow } from "../lib/evidence";

function CountLine({ backed, total }: { backed: number; total: number }) {
  const missing = total - backed;
  const backedWord = backed === 1 ? "finding backed by data" : "findings backed by data";
  const backedText = backed === 0 ? "No findings backed by data" : backed + " " + backedWord;
  if (missing === 0) {
    return (
      <span style={{ fontSize: 12, color: "var(--color-ash-gray)", fontVariantNumeric: "tabular-nums" }}>
        {backedText}
      </span>
    );
  }
  const missingWord = missing === 1 ? "finding not verified" : "findings not verified";
  return (
    <span style={{ fontSize: 12, color: "var(--color-ash-gray)", fontVariantNumeric: "tabular-nums" }}>
      {backedText} · {missing} {missingWord}
    </span>
  );
}

function ClaimRow({ row, last }: { row: EvidenceRow; last: boolean }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 12,
        padding: "8px 12px",
        borderTop: last ? undefined : "1px solid var(--color-stone-border)",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--color-ink-black)" }}>
          {row.finding}
        </div>
        {row.detail ? (
          <div style={{ fontSize: 12, color: "var(--color-ash-gray)", marginTop: 1 }}>
            {row.ok ? null : (
              <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--color-ember)" }}>
                Not verified ·{" "}
              </span>
            )}
            {row.detail}
          </div>
        ) : null}
        {row.source ? (
          <div style={{ fontSize: 12, color: "var(--color-ash-gray)", marginTop: 1 }}>
            {row.source}
          </div>
        ) : null}
      </div>
      {row.value ? (
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "var(--color-ink-black)",
            fontVariantNumeric: "tabular-nums",
            whiteSpace: "nowrap",
          }}
        >
          {row.value}
        </div>
      ) : null}
    </div>
  );
}

export default function EvidenceSection({ ai, defaultOpen }: { ai: AiMessage; defaultOpen?: boolean }) {
  const summary = summarizeEvidence(ai);
  const rows = summary.rows;
  const [open, setOpen] = useState(
    defaultOpen !== undefined ? defaultOpen : rows.some((r) => !r.ok),
  );
  if (!rows.length) return null;
  return (
    <div
      style={{
        marginTop: 10,
        border: "1px solid var(--color-stone-border)",
        borderRadius: 10,
        background: "var(--color-pure-white)",
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          fontFamily: "inherit",
          textAlign: "left",
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: ".08em",
            textTransform: "uppercase",
            color: "var(--color-warm-gray)",
          }}
        >
          Sources
        </span>
        <CountLine backed={summary.backed} total={summary.total} />
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          style={{
            marginLeft: "auto",
            color: "var(--color-ash-gray)",
            flexShrink: 0,
            transform: open ? "rotate(90deg)" : undefined,
            transition: "transform 160ms ease",
          }}
        >
          <path d="M9 5l7 7-7 7" />
        </svg>
      </button>
      {open ? (
        <div style={{ borderTop: "1px solid var(--color-stone-border)" }}>
          {rows.map((row, i) => (
            <ClaimRow key={row.key} row={row} last={i === rows.length - 1} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

"use client";

import type { ReactNode } from "react";
import type { AiMessage } from "../lib/chat";
import { badgeText, summarizeEvidence } from "../lib/evidence";
import type { BadgeState } from "../lib/evidence";

function Shell({ color, children }: { color: string; children: ReactNode }) {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ color, flexShrink: 0 }}>
      {children}
    </svg>
  );
}

function Mark({ state }: { state: BadgeState }) {
  if (state === "verified") {
    return (
      <Shell color="var(--color-cyan-edge)">
        <circle cx="12" cy="12" r="9" />
        <path d="M8.5 12.5l2.5 2.5 4.5-5.5" />
      </Shell>
    );
  }
  if (state === "partial") {
    return (
      <Shell color="var(--color-warm-gray)">
        <circle cx="12" cy="12" r="9" />
        <path d="M8 12h8" />
      </Shell>
    );
  }
  return (
    <Shell color="var(--color-ember)">
      <path d="M12 4L21 20H3Z" />
      <path d="M12 10v4" />
      <path d="M12 16.8v0.4" />
    </Shell>
  );
}

export default function VerificationBadge({ ai }: { ai: AiMessage }) {
  const summary = summarizeEvidence(ai);
  if (summary.state === "unknown") return null;
  if (summary.total === 0 && summary.state !== "unverified") return null;
  const text = badgeText(summary);
  if (!text) return null;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        fontSize: 12,
        lineHeight: 1.4,
        fontVariantNumeric: "tabular-nums",
        color: summary.state === "unverified" ? "var(--color-ember)" : "var(--color-warm-gray)",
      }}
    >
      <Mark state={summary.state} />
      {text}
    </span>
  );
}

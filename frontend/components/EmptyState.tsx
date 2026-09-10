"use client";

import type { ReactNode } from "react";

interface Props {
  icon: ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export default function EmptyState({ icon, title, description, actionLabel, onAction }: Props) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        textAlign: "center",
        gap: 6,
        padding: "20px 16px",
      }}
    >
      <div style={{ fontSize: 24, lineHeight: 1 }} aria-hidden>
        {icon}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink-black)" }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", maxWidth: 340, lineHeight: 1.5 }}>
        {description}
      </div>
      {actionLabel && onAction && (
        <button
          type="button"
          className="pill-cta"
          style={{ fontSize: 12, marginTop: 6, cursor: "pointer" }}
          onClick={onAction}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

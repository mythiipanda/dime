"use client";

import { useEffect, useRef, useState } from "react";
import { ModelOption } from "../lib/chat";

interface ModelPickerProps {
  models: ModelOption[];
  value: string | null;
  onChange: (id: string | null) => void;
  status?: "loading" | "ready" | "error";
  onRetry?: () => void;
}

export default function ModelPicker({ models, value, onChange, status = "ready", onRetry }: ModelPickerProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedModel = models.find((m) => m.id === value) || models[0];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const exactName = (id?: string) => {
    if (!id) return status === "loading" ? "Loading models..." : "Models unavailable";
    const i = id.indexOf(":");
    return i >= 0 ? id.slice(i + 1) : id;
  };

  return (
    <div ref={containerRef} style={{ position: "relative", display: "inline-block" }}>
      {/* Hidden Accessible Select for Test Automation & Form Support */}
      <select
        aria-label="Model"
        value={value || ""}
        onChange={(e) => onChange(e.target.value || null)}
        style={{
          position: "absolute",
          opacity: 0,
          pointerEvents: "none",
          width: 1,
          height: 1,
          top: 0,
          left: 0,
        }}
      >
        {!models.length && <option value="">{status === "loading" ? "Loading models..." : "Models unavailable"}</option>}
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.id}
          </option>
        ))}
      </select>

      {/* Custom Bespoke Trigger Button */}
      <button
        type="button"
        onClick={() => {
          if (status === "error" && !models.length) onRetry?.();
          else setOpen(!open);
        }}
        className="interactive-tactile"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "4px 8px",
          borderRadius: 6,
          background: "var(--color-stone-canvas)",
          border: "1px solid var(--color-stone-border)",
          fontSize: 12,
          fontWeight: 500,
          color: "var(--color-ink-black)",
          cursor: "pointer",
        }}
        title={status === "error" && !models.length ? "Retry loading models" : "Switch AI reasoning model"}
      >
        <span>{exactName(selectedModel?.id)}</span>
        <svg
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          style={{
            color: "var(--color-warm-gray)",
            transform: open ? "rotate(180deg)" : "none",
            transition: "transform 140ms ease",
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Floating Menu Popover */}
      {open && (
        <div
          style={{
            position: "absolute",
            bottom: "calc(100% + 6px)",
            left: 0,
            background: "var(--color-pure-white)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 12,
            boxShadow: "var(--shadow-focus)",
            padding: "6px",
            minWidth: 200,
            maxWidth: 320,
            maxHeight: "min(340px, calc(100vh - 140px))",
            overflowY: "auto",
            zIndex: 100,
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: "var(--color-ash-gray)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              padding: "4px 8px 6px",
            }}
          >
            Available Reasoning Models
          </div>

          {status === "error" && (
            <button
              type="button"
              onClick={() => { onRetry?.(); setOpen(false); }}
              style={{ border: "none", background: "transparent", color: "var(--color-cyan-edge)", cursor: "pointer", padding: "8px 10px", textAlign: "left" }}
            >
              Retry loading models
            </button>
          )}
          {models.map((m) => {
            const isSelected = (value || models[0]?.id) === m.id;
            const isUnavailable = m.available === false;
            return (
              <button
                key={m.id}
                type="button"
                disabled={isUnavailable}
                onClick={() => {
                  onChange(m.id);
                  setOpen(false);
                }}
                className="interactive-tactile"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "none",
                  background: isSelected ? "var(--color-stone-canvas)" : "transparent",
                  cursor: isUnavailable ? "not-allowed" : "pointer",
                  textAlign: "left",
                  width: "100%",
                  opacity: isUnavailable ? 0.45 : 1,
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: isSelected ? 600 : 400,
                      color: "var(--color-ink-black)",
                    }}
                  >
                    {exactName(m.id)}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--color-warm-gray)" }}>
                    {isUnavailable ? `${m.engine || ""} · unavailable` : (m.engine || "live")}
                  </div>
                </div>

                {isSelected && (
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="var(--color-cyan-signal)"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

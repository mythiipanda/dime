"use client";

import { useEffect, useRef, useState } from "react";
import { ModelOption } from "../lib/chat";

interface ModelPickerProps {
  models: ModelOption[];
  value: string | null;
  onChange: (id: string | null) => void;
}

export default function ModelPicker({ models, value, onChange }: ModelPickerProps) {
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

  const formatName = (id?: string) => {
    if (!id) return "Offline";
    if (id.includes("mercury")) return "Mercury 2.5";
    if (id.includes("ministral")) return "Ministral 8B";
    if (id.includes("gpt-oss")) return "GPT-OSS 20B";
    if (id.includes("gemma")) return "Gemma 31B";
    if (id.includes("nemotron")) return "Nemotron 120B";
    let base = id.replace(/:free$/i, "").replace(/-free$/i, "");
    const segments = base.split(/[/:]/).filter(Boolean);
    const last = (segments.length ? segments[segments.length - 1] : base).replace(/:free$/i, "").replace(/-free$/i, "");
    const tokens = last.split(/[-_]+/).filter(Boolean);
    const filtered = tokens.filter((w) => !/^v\d+(\.\d+)*$/i.test(w) && !/^\d+\.\d+(\.\d+)*$/.test(w));
    const kept = filtered.length ? filtered : tokens;
    const pretty = kept.map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
    return pretty || id;
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
        {!models.length && <option value="">Offline</option>}
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.id}
          </option>
        ))}
      </select>

      {/* Custom Bespoke Trigger Button */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
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
        title="Switch AI reasoning model"
      >
        <span>{formatName(selectedModel?.id)}</span>
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
            boxShadow: "var(--shadow-composer)",
            padding: "6px",
            minWidth: 200,
            zIndex: 100,
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 500,
              color: "var(--color-ash-gray)",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              padding: "4px 8px 6px",
            }}
          >
            Available Reasoning Models
          </div>

          {models.map((m) => {
            const isSelected = (value || models[0]?.id) === m.id;
            return (
              <button
                key={m.id}
                type="button"
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
                  cursor: "pointer",
                  textAlign: "left",
                  width: "100%",
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
                    {formatName(m.id)}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--color-warm-gray)" }}>
                    {m.engine || "live"}
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

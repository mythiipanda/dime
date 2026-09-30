"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ModelOption } from "../lib/chat";
import { modelDisplayName, providerDisplayName } from "../lib/modelNames";

interface ModelPickerProps {
  models: ModelOption[];
  value: string | null;
  onChange: (id: string | null) => void;
  status?: "loading" | "ready" | "error";
  onRetry?: () => void;
}

const RETRY_VALUE = "__dime-retry";

export default function ModelPicker({ models, value, onChange, status = "ready", onRetry }: ModelPickerProps) {
  const selectedModel = models.find((m) => m.id === value) || models[0];

  const displayName = (id?: string) => {
    if (!id) return status === "loading" ? "Loading models..." : "Models unavailable";
    return modelDisplayName(id);
  };

  const handleValueChange = (next: string | null) => {
    if (next === RETRY_VALUE) {
      onRetry?.();
      return;
    }
    onChange(next || null);
  };

  if (status === "error" && !models.length) {
    return (
      <button
        type="button"
        onClick={() => onRetry?.()}
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
        title="Retry loading models"
      >
        <span>Retry loading models</span>
      </button>
    );
  }

  const effectiveValue = value || models[0]?.id || "";

  return (
    <Select value={effectiveValue} onValueChange={handleValueChange}>
      <SelectTrigger
        aria-label="Model"
        title="Switch model"
        className="interactive-tactile"
        style={{
          padding: "4px 8px",
          borderRadius: 6,
          background: "var(--color-stone-canvas)",
          fontSize: 12,
          fontWeight: 500,
          color: "var(--color-ink-black)",
        }}
      >
        <SelectValue placeholder={status === "loading" ? "Loading models..." : "Models unavailable"}>
          {(selected: string | null) => displayName(typeof selected === "string" && selected ? selected : selectedModel?.id)}
        </SelectValue>
      </SelectTrigger>
      <SelectContent style={{ width: 320, maxHeight: 340 }}>
        <SelectLabel
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: "var(--color-ash-gray)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            padding: "4px 8px 6px",
          }}
        >
          Models
        </SelectLabel>
        {status === "error" && (
          <SelectItem value={RETRY_VALUE} label="Retry loading models">
            <span style={{ fontSize: 13, color: "var(--color-cyan-edge)" }}>
              Retry loading models
            </span>
          </SelectItem>
        )}
        {models.map((m) => {
          const isSelected = (value || models[0]?.id) === m.id;
          const isUnavailable = m.available === false;
          return (
            <SelectItem
              key={m.id}
              value={m.id}
              label={modelDisplayName(m.id)}
              disabled={isUnavailable}
            >
              <span style={{ display: "flex", flexDirection: "column", opacity: isUnavailable ? 0.45 : 1 }}>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: isSelected ? 600 : 400,
                    color: "var(--color-ink-black)",
                  }}
                >
                  {displayName(m.id)}
                </span>
                <span style={{ fontSize: 11, fontWeight: 400, color: "var(--color-warm-gray)" }}>
                  {isUnavailable
                    ? `${providerDisplayName(m.engine) || m.engine} · unavailable`
                    : (providerDisplayName(m.engine) || m.engine || "live")}
                </span>
              </span>
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}

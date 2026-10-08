"use client";

import { useEffect, useRef, useState } from "react";

export interface PickerModel {
  id: string;
  engine: string;
  label: string;
  default?: boolean;
  available?: boolean;
}

function shortName(id: string) {
  const raw = id.includes(":") ? id.split(":").slice(1).join(":") : id;
  return raw.replace(/:free$/, "");
}

const ENGINE_LABEL: Record<string, string> = {
  cerebras: "Cerebras",
  gemini: "Gemini",
  groq: "Groq",
  mistral: "Mistral",
  nvidia: "NVIDIA",
  openrouter: "OpenRouter",
};

function Chevron({ dir }: { dir: "up" | "down" }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{ transform: dir === "up" ? "rotate(180deg)" : undefined }}
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export default function DimeModelPicker({
  models,
  value,
  onChange,
  disabled = false,
}: {
  models: PickerModel[];
  value: string | null;
  onChange: (id: string | null) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  const grouped = models.reduce<Record<string, PickerModel[]>>((acc, m) => {
    (acc[m.engine] ??= []).push(m);
    return acc;
  }, {});
  const order = Object.keys(grouped);

  const selected = models.find((m) => m.id === value) ?? null;
  const flat = order.flatMap((engine) => grouped[engine]);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  useEffect(() => {
    if (open) setActive(Math.max(0, flat.findIndex((m) => m.id === value)));
  }, [open, value, flat]);

  const pick = (id: string | null) => {
    onChange(id);
    setOpen(false);
    trigger.current?.focus();
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      setOpen(false);
      trigger.current?.focus();
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const next = event.key === "ArrowDown" ? active + 1 : active - 1;
      setActive(Math.min(flat.length - 1, Math.max(0, next)));
      return;
    }
    if (event.key === "Enter" && open && flat[active]) {
      event.preventDefault();
      pick(flat[active].id);
    }
  };

  return (
    <div ref={wrap} className="relative" onKeyDown={onKeyDown}>
      <button
        ref={trigger}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Model: ${selected ? selected.label : "Automatic"}`}
        onClick={() => setOpen((v) => !v)}
        className="flex h-7 min-w-0 items-center gap-1.5 rounded-[7px] px-2 text-[12px] text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-hover hover:text-ink active:scale-[0.97] disabled:opacity-50"
      >
        <span className="truncate">
          {selected ? selected.label : "Auto"}
        </span>
        <Chevron dir={open ? "up" : "down"} />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute bottom-full left-0 z-50 mb-1 max-h-[min(420px,60vh)] w-[268px] origin-bottom-left overflow-y-auto overscroll-contain rounded-[10px] bg-surface shadow-overlay"
          style={{
            animation:
              "fade-up 160ms cubic-bezier(0.23,1,0.32,1) both",
          }}
        >
          <div
            role="option"
            aria-selected={value === null}
            onClick={() => pick(null)}
            className={`flex h-8 cursor-pointer items-center gap-2 px-3 text-[12.5px] transition-colors duration-100 ${
              value === null ? "bg-hover text-ink" : "text-ink-2 hover:bg-hover"
            }`}
          >
            <span className="min-w-0 flex-1 truncate">Automatic</span>
            {value === null && <span className="text-ink-3">✓</span>}
          </div>

          <div className="my-1 border-t border-line" />

          {order.map((engine) => (
            <div key={engine}>
              <div className="px-3 pb-1 pt-2 text-[11px] font-medium uppercase tracking-[0.04em] text-ink-3">
                {ENGINE_LABEL[engine] ?? engine}
              </div>
              {grouped[engine].map((model) => {
                const on = model.id === value;
                const index = flat.findIndex((m) => m.id === model.id);
                return (
                  <div
                    key={model.id}
                    role="option"
                    aria-selected={on}
                    onClick={() => pick(model.id)}
                    onMouseEnter={() => setActive(index)}
                    className={`flex h-8 cursor-pointer items-center gap-2 px-3 text-[12.5px] transition-colors duration-100 ${
                      index === active ? "bg-hover" : ""
                    } ${on ? "text-ink" : "text-ink-2"}`}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      {shortName(model.id)}
                    </span>
                    {model.default && (
                      <span className="shrink-0 text-[11px] text-ink-3">
                        default
                      </span>
                    )}
                    {on && <span className="shrink-0 text-ink-3">✓</span>}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
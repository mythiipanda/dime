"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowUp, Check, ChevronDown, Square } from "lucide-react";

const providerKeys: Record<string, string> = { gemini: "GEMINI_API_KEY (or GOOGLE_API_KEY)", nvidia: "NVIDIA_NIM_API_KEY", openrouter: "OPENROUTER_API_KEY", mistral: "MISTRAL_API_KEY", cerebras: "CEREBRAS_API_KEY", groq: "GROQ_API_KEY", agnes: "AGNES_API_KEY", reflection: "REFLECTION_API_KEY", inception: "INCEPTION_API_KEY" };

type ModelOption = { id: string; label: string; available?: boolean };

export function PromptBar({ value, onChange, onSend, onStop, busy, models, model, onModelChange, modelError, onRetry, providers, modelsLoading }: {
  value: string; onChange: (text: string) => void; onSend: (text: string) => void; onStop: () => void; busy: boolean;
  models: ModelOption[]; model: string | null; onModelChange: (id: string) => void; modelError?: boolean; onRetry: () => void;
  providers?: string[]; modelsLoading?: boolean;
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const anchorRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState<number | null>(null);
  const [rowBox, setRowBox] = useState<{ top: number; height: number } | null>(null);
  const [menuLeft, setMenuLeft] = useState(0);
  const [menuBottom, setMenuBottom] = useState(0);
  const selected = models.find((item) => item.id === model && item.available !== false);
  useEffect(() => { if (input.current) { input.current.style.height = "auto"; input.current.style.height = Math.min(180, input.current.scrollHeight) + "px"; } }, [value]);
  const disabledReason = modelsLoading ? "Loading models" : modelError ? "Models unavailable; retry loading models" : !selected ? "Send disabled: configure a provider to enable a model" : !value.trim() ? "Enter a message to send" : undefined;
  const names = providers?.length ? providers : [...new Set(models.map(item => item.id.split(":")[0]))];
  const keys = (names.length ? names : ["gemini", "nvidia", "openrouter", "mistral", "cerebras"]).map(name => providerKeys[name]).filter(Boolean);

  const selectedIndex = models.findIndex((item) => item.id === model);
  useLayoutEffect(() => {
    if (!open) return;
    const target = rowRefs.current[hovered ?? (selectedIndex >= 0 ? selectedIndex : 0)];
    if (target) setRowBox({ top: target.offsetTop, height: target.offsetHeight });
  }, [open, hovered, selectedIndex, models.length]);

  useLayoutEffect(() => {
    if (!open || !anchorRef.current || !triggerRef.current) return;
    const anchorRect = anchorRef.current.getBoundingClientRect();
    const triggerRect = triggerRef.current.getBoundingClientRect();
    setMenuLeft(Math.max(0, Math.min(triggerRect.left - anchorRect.left, anchorRect.width - 208)));
    setMenuBottom(anchorRect.bottom - triggerRect.top + 8);
  }, [open, models.length, selected?.id]);

  useEffect(() => {
    if (!open) { setHovered(null); return; }
    const close = (event: PointerEvent) => {
      if (!(event.target as Element).closest("[data-model-picker]")) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  const pick = (item: ModelOption) => {
    if (item.available === false) return;
    onModelChange(item.id);
    setOpen(false);
    input.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        return;
      }
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp" && event.key !== "Enter") return;
      if (!models.length) return;
      event.preventDefault();
      const base = hovered ?? (selectedIndex >= 0 ? selectedIndex : -1);
      if (event.key === "Enter") {
        const item = models[base >= 0 ? base : 0];
        if (item) pick(item);
        return;
      }
      const delta = event.key === "ArrowDown" ? 1 : -1;
      const next = ((base < 0 ? (delta === 1 ? -1 : 0) : base) + delta + models.length) % models.length;
      setHovered(next);
      rowRefs.current[next]?.scrollIntoView({ block: "nearest" });
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, hovered, selectedIndex, models]);

  return <form className="composer relative" ref={anchorRef as never} onSubmit={(e) => { e.preventDefault(); if (!busy && selected) onSend(value); }}>
    {open && !modelError && models.length > 0 && (
      <div
        data-model-picker
        role="listbox"
        aria-label="Choose model"
        onMouseLeave={() => setHovered(null)}
        className="absolute z-10 max-h-72 w-80 overflow-y-auto rounded-[10px] bg-surface p-1 shadow-raised"
        style={{ left: menuLeft, bottom: menuBottom, animation: "pop-in 180ms cubic-bezier(0.23,1,0.32,1) both", transformOrigin: "bottom left" }}
      >
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-1 rounded-[6px] bg-hover"
          style={{
            top: rowBox?.top ?? 0,
            height: rowBox?.height ?? 0,
            opacity: rowBox && hovered !== null ? 1 : 0,
            transition: "top 220ms cubic-bezier(0.23,1,0.32,1), height 220ms cubic-bezier(0.23,1,0.32,1), opacity 150ms ease",
          }}
        />
        {models.map((item, i) => {
          const unavailable = item.available === false;
          return <button
            key={item.id}
            type="button"
            role="option"
            aria-selected={item.id === model}
            aria-disabled={unavailable || undefined}
            ref={(el) => { rowRefs.current[i] = el; }}
            onMouseDown={(event) => event.preventDefault()}
            onMouseEnter={() => setHovered(i)}
            onClick={() => pick(item)}
            className={`relative z-10 flex h-7.5 w-full items-center gap-2 rounded-[6px] px-2 text-left ${unavailable ? "opacity-45" : ""}`}
          >
            <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-ink">{item.label}</span>
            <span className="shrink-0 text-[11px] text-ink-3">{item.id.split(":")[0]}{unavailable ? " · unavailable" : ""}</span>
            <span className={`shrink-0 text-ink ${item.id === model ? "" : "invisible"}`}><Check width={13} height={13} strokeWidth={2.5} /></span>
          </button>;
        })}
      </div>
    )}
    <textarea ref={input} rows={2} aria-label="Message Dime" placeholder="Ask anything about a player, team, or basketball decision…" value={value} onChange={(e) => onChange(e.target.value)} onKeyDown={(e) => {
      if (e.key === "Escape" && open) { setOpen(false); return; }
      if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (!busy && selected) onSend(value); }
    }} />
    <div className="mt-3 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2" data-model-picker>
        {modelError ? <button type="button" className="text-[11px] text-red" onClick={onRetry}>Models unavailable · Retry</button> : <button
          ref={triggerRef}
          type="button"
          aria-expanded={open}
          aria-label="Choose model"
          title={selected?.id || "Configure a provider to send messages"}
          onClick={() => setOpen((current) => !current)}
          className="flex h-7 items-center gap-1 rounded-[8px] px-1.5 text-[12px] font-medium text-ink-2 transition-colors duration-150 hover:bg-hover hover:text-ink"
        >
          {selected?.label ?? (modelsLoading ? "Loading models…" : "No model")}
          <span className="text-ink-3"><ChevronDown width={11} height={11} strokeWidth={2.4} /></span>
        </button>}
      </div>
      <button type={busy ? "button" : "submit"} onClick={busy ? onStop : undefined} disabled={!busy && !!disabledReason} title={busy ? "Stop response" : disabledReason} aria-describedby={!busy && !selected && !modelsLoading && !modelError ? "provider-setup" : undefined} aria-label={busy ? "Stop response" : "Send message"} className="flex size-7 items-center justify-center rounded-lg bg-ink text-page transition-opacity hover:opacity-80 disabled:bg-hover-2 disabled:text-ink-3">{busy ? <Square width={13} height={13} /> : <ArrowUp width={17} height={17} />}</button>
    </div>
    {!selected && !modelsLoading && !modelError && <p id="provider-setup" className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-2">Send is disabled: no models are configured. Add one supported key to <code>backend/.env</code>: <span className="font-mono text-[10px]">{keys.join(", ")}</span>. Restart the Node analyst backend with <code>--env-file=.env</code>, then refresh this page. <a className="underline underline-offset-2" href="https://github.com/mythiipanda/dime/blob/dev/README.md#quickstart" target="_blank" rel="noreferrer">Setup instructions</a>.</p>}
  </form>;
}

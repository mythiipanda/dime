"use client";

import { useRef, useEffect } from "react";
import { ArrowUp, Square } from "iconoir-react";

export function PromptBar({ value, onChange, onSend, onStop, busy, models, model, onModelChange, modelError, onRetry }: {
  value: string; onChange: (text: string) => void; onSend: (text: string) => void; onStop: () => void; busy: boolean;
  models: { id: string; label: string; available?: boolean }[]; model: string | null; onModelChange: (id: string) => void; modelError?: boolean; onRetry: () => void;
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  const selected = models.find((item) => item.id === model && item.available !== false);
  const provider = (selected?.id || models[0]?.id || "Dime").split(":")[0];
  useEffect(() => { if (input.current) { input.current.style.height = "auto"; input.current.style.height = Math.min(180, input.current.scrollHeight) + "px"; } }, [value]);
  return <form className="composer" onSubmit={(e) => { e.preventDefault(); if (!busy) onSend(value); }}>
    <textarea ref={input} rows={2} aria-label="Message Dime" placeholder="Ask anything about a player, team, or basketball decision…" value={value} onChange={(e) => onChange(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (!busy) onSend(value); } }} />
    <div className="mt-3 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2"><span title={provider} aria-label={`${provider} provider`} className="flex size-5 items-center justify-center rounded-md border border-line bg-field text-[10px] font-semibold uppercase text-ink-2">{provider.charAt(0)}</span>{modelError ? <button type="button" className="text-[11px] text-red" onClick={onRetry}>Models unavailable · Retry</button> : <select aria-label="Model" title={selected?.id || "Configure a provider to send messages"} value={model || ""} onChange={(e) => onModelChange(e.target.value)}><option value="" disabled>{models.length ? "No models configured" : "No models available"}</option>{models.map((m) => <option key={m.id} value={m.id} title={m.id} disabled={m.available === false}>{m.label}{m.available === false ? " · Unavailable" : ""}</option>)}</select>}</div>
      <button type={busy ? "button" : "submit"} onClick={busy ? onStop : undefined} disabled={!busy && (!value.trim() || !selected)} aria-label={busy ? "Stop response" : "Send message"} className="flex size-7 items-center justify-center rounded-lg bg-ink text-page transition-opacity hover:opacity-80 disabled:bg-hover-2 disabled:text-ink-3">{busy ? <Square width={13} height={13} /> : <ArrowUp width={17} height={17} />}</button>
    </div>
  </form>;
}

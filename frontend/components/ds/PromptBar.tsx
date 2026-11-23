"use client";

import { useRef, useEffect } from "react";
import { ArrowUp, Square, WarningCircle, Refresh } from "iconoir-react";

const providerKeys: Record<string, string> = { gemini: "GEMINI_API_KEY (or GOOGLE_API_KEY)", nvidia: "NVIDIA_NIM_API_KEY", openrouter: "OPENROUTER_API_KEY", mistral: "MISTRAL_API_KEY", cerebras: "CEREBRAS_API_KEY", groq: "GROQ_API_KEY", agnes: "AGNES_API_KEY", reflection: "REFLECTION_API_KEY", inception: "INCEPTION_API_KEY" };

export function PromptBar({ value, onChange, onSend, onStop, busy, models, model, onModelChange, modelError, onRetry, providers, modelsLoading }: {
  value: string; onChange: (text: string) => void; onSend: (text: string) => void; onStop: () => void; busy: boolean;
  models: { id: string; label: string; available?: boolean }[]; model: string | null; onModelChange: (id: string) => void; modelError?: boolean; onRetry: () => void;
  providers?: string[]; modelsLoading?: boolean;
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  const selected = models.find((item) => item.id === model && item.available !== false);
  const provider = (selected?.id || models[0]?.id || "Dime").split(":")[0];
  useEffect(() => { if (input.current) { input.current.style.height = "auto"; input.current.style.height = Math.min(180, input.current.scrollHeight) + "px"; } }, [value]);
  const disabledReason = modelsLoading ? "Loading models" : modelError ? "Models unavailable; retry loading models" : !selected ? "Send disabled: configure a provider to enable a model" : !value.trim() ? "Enter a message to send" : undefined;
  const names = providers?.length ? providers : [...new Set(models.map(item => item.id.split(":")[0]))];
  const keys = (names.length ? names : ["gemini", "nvidia", "openrouter", "mistral", "cerebras"]).map(name => providerKeys[name]).filter(Boolean);
  return <form className="composer" onSubmit={(e) => { e.preventDefault(); if (!busy && selected) onSend(value); }}>
    <textarea ref={input} rows={2} aria-label="Message Dime" placeholder="Ask anything about a player, team, or basketball decision…" value={value} onChange={(e) => onChange(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (!busy && selected) onSend(value); } }} />
    <div className="mt-3 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2"><span title={provider} aria-label={`${provider} provider`} className="flex size-5 items-center justify-center rounded-md border border-line bg-field text-[10px] font-semibold uppercase text-ink-2">{provider.charAt(0)}</span>{modelError ? <span className="flex items-center gap-1.5 text-[11px] text-ink-2"><WarningCircle width={13} height={13} className="text-ink-3" aria-hidden />Couldn&rsquo;t load models<button type="button" className="flex items-center gap-1 rounded-md border border-line px-1.5 py-0.5 text-ink-2 transition-colors hover:bg-hover hover:text-ink disabled:opacity-50" onClick={onRetry} disabled={modelsLoading}><Refresh width={11} height={11} className={modelsLoading ? "animate-spin" : undefined} aria-hidden />Try again</button></span> : <select aria-label="Model" title={selected?.id || "Configure a provider to send messages"} value={model || ""} onChange={(e) => onModelChange(e.target.value)}><option value="" disabled>{models.length ? "No models configured" : "No models available"}</option>{models.map((m) => <option key={m.id} value={m.id} title={m.id} disabled={m.available === false}>{m.label}{m.available === false ? " · Unavailable" : ""}</option>)}</select>}</div>
      <button type={busy ? "button" : "submit"} onClick={busy ? onStop : undefined} disabled={!busy && !!disabledReason} title={busy ? "Stop response" : disabledReason} aria-describedby={!busy && !selected && !modelsLoading && !modelError ? "provider-setup" : undefined} aria-label={busy ? "Stop response" : "Send message"} className="flex size-7 items-center justify-center rounded-lg bg-ink text-page transition-opacity hover:opacity-80 disabled:bg-hover-2 disabled:text-ink-3">{busy ? <Square width={13} height={13} /> : <ArrowUp width={17} height={17} />}</button>
    </div>
    {!selected && !modelsLoading && !modelError && <p id="provider-setup" className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-2">Send is disabled: no models are configured. Add one supported key to <code>backend/.env</code>: <span className="font-mono text-[10px]">{keys.join(", ")}</span>. Restart the Node analyst backend with <code>--env-file=.env</code>, then refresh this page. <a className="underline underline-offset-2" href="https://github.com/mythiipanda/dime/blob/dev/README.md#quickstart" target="_blank" rel="noreferrer">Setup instructions</a>.</p>}
  </form>;
}

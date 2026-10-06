"use client";

import { useEffect, useRef } from "react";
import type { ModelOption } from "../lib/chat";
import { getComposerDraft, setComposerDraft, useComposerDraft } from "../lib/composer";
import ModelPicker from "./ModelPicker";
import { Button } from "@/components/ui/button";

function resize(el: HTMLTextAreaElement, max: number) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, max) + "px";
}

export default function ChatComposer({
  busy,
  elapsed,
  models,
  model,
  modelStatus,
  onModelChange,
  onRetryModels,
  onSend,
  onStop,
  variant,
  autoFocus,
  placeholder,
}: {
  busy: boolean;
  elapsed: number;
  models: ModelOption[];
  model: string | null;
  modelStatus: "loading" | "ready" | "error";
  onModelChange: (id: string | null) => void;
  onRetryModels: () => void;
  onSend: (text: string) => void;
  onStop: () => void;
  variant: "hero" | "dock";
  autoFocus?: boolean;
  placeholder: string;
}) {
  const draft = useComposerDraft();
  const area = useRef<HTMLTextAreaElement | null>(null);
  const max = variant === "hero" ? 240 : 200;

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    if (document.activeElement !== el && el.value !== draft) {
      el.value = draft;
      resize(el, max);
    }
  }, [draft, max]);

  useEffect(() => {
    const el = area.current;
    if (el) resize(el, max);
  }, [max]);

  const send = () => {
    const text = getComposerDraft();
    if (!text.trim() || busy) return;
    onSend(text);
    const el = area.current;
    if (el) {
      el.value = "";
      resize(el, max);
    }
  };

  const stopButton = (
    <Button
      variant="ghost"
      size="default"
      className="pill-ghost interactive-tactile h-auto font-normal"
      onClick={onStop}
      style={{ borderColor: "var(--color-cyan-signal)", color: "var(--color-cyan-edge)" }}
    >
      Stop {elapsed}s
    </Button>
  );

  const sendButton = (
    <Button
      type="button"
      variant="default"
      size="icon"
      aria-label="Send"
      disabled={!draft.trim()}
      onClick={send}
      className="interactive-tactile chat-send disabled:opacity-100 [&_svg:not([class*='size-'])]:size-[15px]"
      style={{
        width: 28, height: 28, borderRadius: 8, border: "none", cursor: draft.trim() ? "pointer" : "default",
        display: "flex", alignItems: "center", justifyContent: "center",
        background: draft.trim() ? "var(--color-ink-black)" : "var(--color-stone-muted)",
        color: draft.trim() ? "var(--color-pure-white)" : "var(--color-warm-gray)",
        transition: "background 200ms ease, color 200ms ease",
      }}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
    </Button>
  );

  if (variant === "hero") {
    return (
      <div className="composer-card chat-composer chat-composer-hero">
        <textarea
          ref={area}
          aria-label="Chat message"
          style={{
            width: "100%",
            border: "none",
            outline: "none",
            fontSize: 13,
            lineHeight: 1.4,
            resize: "none",
            fontFamily: "inherit",
            background: "transparent",
            minHeight: 48,
            maxHeight: 240,
            overflowY: "auto",
            boxSizing: "border-box",
          }}
          defaultValue={getComposerDraft()}
          rows={2}
          autoFocus={autoFocus}
          onChange={(e) => {
            setComposerDraft(e.target.value);
            resize(e.target, max);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={placeholder}
        />
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
          <ModelPicker models={models} value={model} onChange={onModelChange} status={modelStatus} onRetry={onRetryModels} />
          {busy ? stopButton : sendButton}
        </div>
      </div>
    );
  }

  return (
    <div className="composer-card chat-composer chat-composer-dock">
      <ModelPicker models={models} value={model} onChange={onModelChange} status={modelStatus} onRetry={onRetryModels} />
      <textarea
        ref={area}
        aria-label="Chat message"
        style={{
          flex: 1,
          border: "none",
          outline: "none",
          fontSize: 13,
          resize: "none",
          fontFamily: "inherit",
          background: "transparent",
          maxHeight: 200,
          overflowY: "auto",
        }}
        defaultValue={getComposerDraft()}
        rows={1}
        onChange={(e) => {
          setComposerDraft(e.target.value);
          resize(e.target, max);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        placeholder={placeholder}
      />
      {busy ? (
        <Button
          variant="ghost"
          size="default"
          className="pill-ghost h-auto font-normal"
          onClick={onStop}
          style={{ borderColor: "var(--color-cyan-signal)", color: "var(--color-cyan-edge)" }}
        >
          Stop {elapsed}s
        </Button>
      ) : (
        <Button
          type="button"
          variant="default"
          size="icon"
          aria-label="Send"
          disabled={!draft.trim()}
          onClick={send}
          className="disabled:opacity-100 [&_svg:not([class*='size-'])]:size-[15px]"
          style={{
            width: 28, height: 28, borderRadius: 8, border: "none", flexShrink: 0,
            cursor: draft.trim() ? "pointer" : "default",
            display: "flex", alignItems: "center", justifyContent: "center",
            background: draft.trim() ? "var(--color-ink-black)" : "var(--color-stone-muted)",
            color: draft.trim() ? "var(--color-pure-white)" : "var(--color-warm-gray)",
            transition: "background 200ms ease, color 200ms ease",
          }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </Button>
      )}
    </div>
  );
}

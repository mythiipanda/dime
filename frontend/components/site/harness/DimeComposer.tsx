"use client";

import type { RefObject } from "react";
import DimeModelPicker, { type PickerModel } from "@/components/site/DimeModelPicker";

export function DimeComposer({
  draft,
  setDraft,
  onSubmit,
  inputRef,
  modelOptions,
  model,
  setModel,
}: {
  draft: string;
  setDraft: (v: string) => void;
  onSubmit: () => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  modelOptions: PickerModel[];
  model: string | null;
  setModel: (v: string | null) => void;
}) {
  const canSend = draft.trim().length > 0;
  return (
    <div className="rounded-control border border-line bg-field p-2.5 shadow-[0_1px_2px_rgba(0,0,0,0.035)] transition-[border-color,box-shadow] duration-150 focus-within:border-line-strong">
      <textarea
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit();
          }
        }}
        placeholder="Ask about any team, player, lineup, or market…"
        rows={1}
        className="w-full resize-none bg-transparent px-1 pt-0.5 text-[13.5px] leading-[1.5] text-ink placeholder:text-ink-3 focus:outline-none [@media(pointer:coarse)]:text-base"
      />
      <div className="flex items-center justify-between gap-2 px-1 pb-0.5 pt-1.5">
        <DimeModelPicker
          models={modelOptions}
          value={model}
          onChange={setModel}
          disabled={false}
        />
        <button
          type="button"
          aria-label="Send"
          disabled={!canSend}
          onClick={onSubmit}
          className="flex size-7 items-center justify-center rounded-[8px] transition-[background-color,color,transform] duration-150 enabled:active:scale-[0.96]"
          style={{
            background: canSend ? "var(--ink)" : "var(--line-strong)",
            color: canSend ? "var(--surface)" : "var(--ink-2)",
          }}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
        </button>
      </div>
    </div>
  );
}

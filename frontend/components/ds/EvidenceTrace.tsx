"use client";

import { useEffect, useRef, useState } from "react";
import type { ToolState } from "@/lib/dime-stream";
import { Shimmer } from "./Shimmer";

function Spinner() {
  return <span className="size-3 shrink-0 rounded-full border-[1.5px] border-line-strong border-t-ink-2" style={{ animation: "spin 700ms linear infinite" }} aria-hidden="true" />;
}

function DoneMark() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--ink-3)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="shrink-0" aria-hidden="true">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

function ErrorMark() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0" aria-hidden="true">
      <path d="M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    </svg>
  );
}

function toolMeta(tool: ToolState): string | null {
  const parts: string[] = [];
  if (tool.rows !== undefined) parts.push(`${tool.rows} rows`);
  if (tool.ms !== undefined) parts.push(`${tool.ms}ms`);
  return parts.length ? parts.join(" · ") : null;
}

export function EvidenceTrace({ busy, thinking, tools }: {
  busy: boolean;
  thinking: { label: string }[];
  tools: ToolState[];
}) {
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(null);
  const expanded = manualExpanded ?? busy;
  const count = tools.length;
  const statusLabel = busy
    ? (thinking.length ? thinking[thinking.length - 1].label : "Working through the evidence")
    : null;
  const traceRef = useRef<HTMLDivElement>(null);
  const [lineHeight, setLineHeight] = useState(0);
  useEffect(() => {
    if (traceRef.current) setLineHeight(traceRef.current.offsetHeight);
  }, [count, expanded, busy]);

  if (!busy && count === 0) return null;

  return (
    <div className="mb-3 flex w-full flex-col">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setManualExpanded((current) => !(current ?? busy))}
        className="-mx-1.5 flex w-fit items-center gap-2 rounded-control px-1.5 py-1 transition-colors duration-100 hover:bg-hover-2"
      >
        <span role="status" className="contents">
          {busy ? (
            <Shimmer className="text-[13px] font-medium whitespace-nowrap">{statusLabel}</Shimmer>
          ) : (
            <span className="text-[13px] font-medium whitespace-nowrap text-ink-2" style={{ animation: "fade-in 350ms ease-out both" }}>
              Evidence · {count} {count === 1 ? "step" : "steps"}
            </span>
          )}
        </span>
        <svg
          width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ink-3)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
          className="transition-transform duration-300"
          style={{ transform: expanded ? "rotate(180deg)" : "rotate(0)" }}
          aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      <div
        className="grid transition-[grid-template-rows,opacity] duration-400"
        style={{
          gridTemplateRows: expanded ? "1fr" : "0fr",
          opacity: expanded ? 1 : 0,
          transitionTimingFunction: "cubic-bezier(0.23, 1, 0.32, 1)",
        }}
      >
        <div className="overflow-hidden">
          <div className="relative mt-1 ml-[5px] pl-4">
            <span
              aria-hidden="true"
              className="absolute left-[3px] w-px bg-line"
              style={{ top: -8, height: lineHeight ? lineHeight - 2 : 0, transition: "height 500ms cubic-bezier(0.23,1,0.32,1)" }}
            />
            <div ref={traceRef} className="flex flex-col gap-1 py-1">
              {tools.map((tool, i) => {
                const meta = toolMeta(tool);
                return (
                  <div
                    key={tool.key}
                    className="flex min-h-7 w-full items-center gap-2 rounded-[6px] px-1.5 py-0.5"
                    style={{ animation: `fade-up 320ms cubic-bezier(0.23,1,0.32,1) ${Math.min(i, 8) * 60}ms both` }}
                  >
                    {tool.status === "running" ? <Spinner /> : tool.status === "fail" ? <ErrorMark /> : <DoneMark />}
                    <span className="min-w-0 truncate text-[12.5px] font-medium text-ink">{tool.label}</span>
                    {meta && <span className="shrink-0 font-mono text-[11.5px] tabular-nums text-ink-3">{meta}</span>}
                    {tool.status === "fail" && tool.error && (
                      <span className="min-w-0 truncate text-[11.5px] text-red">{tool.error}</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

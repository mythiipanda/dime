"use client";

import { Check, NavArrowDown } from "iconoir-react";
import { Shimmer } from "./Shimmer";

export function ThinkingState({ busy, steps }: { busy: boolean; steps: { label: string; state: "pending" | "running" | "done" }[] }) {
  return <details className="mb-3 text-[12px] text-ink-2">
    <summary className="flex w-fit list-none items-center gap-2 py-1 hover:text-ink"><NavArrowDown width={13} height={13} />{busy ? <Shimmer>Working through the evidence</Shimmer> : <span>Analysis complete{steps.length ? ` · ${steps.length} steps` : ""}</span>}</summary>
    <ol className="ml-1.5 mt-2 grid gap-2 border-l border-line pl-5">{steps.map((s, i) => <li key={i} className="flex items-center gap-2">{s.state === "done" ? <Check width={13} height={13} /> : <span className={`size-2 rounded-full ${s.state === "running" ? "animate-pulse bg-accent" : "bg-line-strong"}`} />}<span>{s.label}</span></li>)}</ol>
  </details>;
}

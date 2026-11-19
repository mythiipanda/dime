"use client";
import { Database, Check, WarningTriangle } from "iconoir-react";

export function ToolChips({ tools }: { tools: { id: string; label: string; status: "running" | "done" | "error"; detail?: string }[] }) {
  if (!tools.length) return null;
  return <div className="mb-5 flex flex-wrap gap-2">{tools.map((t) => <span key={t.id} title={t.detail} className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-inset px-2 py-1 text-[11px] text-ink-2"><Database width={12} height={12} />{t.label}{t.status === "done" ? <Check width={11} height={11} className="text-green" /> : t.status === "error" ? <WarningTriangle width={11} height={11} className="text-red" /> : <span className="size-1.5 animate-pulse rounded-full bg-accent" />}</span>)}</div>;
}

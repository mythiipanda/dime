"use client";

import { ArrowRight } from "iconoir-react";
import TodayPanel from "../TodayPanel";
import MoversPanel from "../MoversPanel";
import WatchlistPanel from "../WatchlistPanel";
import { PageHeader } from "../ds/Panel";
import { Button } from "../ds/Button";
import { Chip } from "../ds/Chip";

export function HomeView({ onWorkflows }: { onWorkflows: () => void }) {
  return <div className="mx-auto max-w-6xl px-6 py-10 lg:px-10">
    <PageHeader eyebrow="Your daily read" title="Around the league" description="The slate, the movement, and the players on your radar. Start with the evidence; build your next decision from here." actions={<Chip>2025–26 season</Chip>} />
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-line bg-inset px-5 py-4"><div><p className="text-[13px] font-medium">Turn a question into a decision.</p><p className="mt-1 text-[12px] text-ink-3">Scouting, lineup audits, and roster evaluation — guided from the start.</p></div><Button size="sm" onClick={onWorkflows}>Open workflows <ArrowRight width={13} height={13} /></Button></div>
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(300px,1fr)]">
      <div className="min-w-0 space-y-6"><TodayPanel /><MoversPanel /></div>
      <WatchlistPanel />
    </div>
  </div>;
}

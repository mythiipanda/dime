"use client";

import { useState } from "react";

function Ico({ d, size = 14 }: { d: React.ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden>{d}</svg>
  );
}

const iconBtn =
  "flex size-7 items-center justify-center rounded-[6px] text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-hover hover:text-ink active:scale-[0.94]";

const SOURCE_LABELS: Record<string, string> = {
  silver_boxscores: "Player game logs",
  silver_schedule: "League schedule",
  silver_lineups: "Lineup data",
  silver_team_ratings: "Team ratings",
  silver_players: "Player profiles",
  tracking_feed: "Tracking feed",
};

function sourceLabel(source?: string) {
  if (!source) return null;
  const head = source.split("·")[0].trim();
  return SOURCE_LABELS[head] ?? source.trim();
}

export default function ArtifactShell({
  title,
  source,
  copyText,
  delay = 0,
  children,
}: {
  title: string;
  source?: string;
  copyText?: string;
  delay?: number;
  children: React.ReactNode;
}) {
  const [tall, setTall] = useState(false);
  const [copied, setCopied] = useState(false);
  const label = sourceLabel(source);

  const copy = async () => {
    const text = copyText ?? title;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      } catch {
        return;
      }
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <div
      className="overflow-hidden rounded-card bg-surface shadow-hairline"
      style={{ animation: "fade-up 280ms cubic-bezier(0.23,1,0.32,1) both", animationDelay: `${delay}ms` }}
    >
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-line pl-4 pr-2">
        <span className="truncate text-[13px] font-semibold text-ink">{title}</span>
        <div className="flex shrink-0 items-center gap-0.5">
          {label && (
            <span className="mr-1.5 truncate text-[11px] text-ink-3">{label}</span>
          )}
          <button type="button" aria-label={tall ? "Collapse" : "Expand"} title={tall ? "Collapse" : "Expand"}
            onClick={() => setTall((v) => !v)} className={iconBtn}>
            <Ico d={tall
              ? <><polyline points="4 14 10 14 10 20" /><polyline points="20 10 14 10 14 4" /><line x1="14" y1="10" x2="21" y2="3" /><line x1="3" y1="21" x2="10" y2="14" /></>
              : <><polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" /><line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" /></>} />
          </button>
          <button type="button" aria-label="Copy" title={copied ? "Copied" : "Copy"}
            onClick={copy} className={iconBtn}>
            <Ico d={copied
              ? <path d="M20 6 9 17l-5-5" />
              : <><rect x="9" y="9" width="12" height="12" rx="2.5" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></>} />
          </button>
        </div>
      </div>
      <div
        key={String(tall)}
        className={tall ? "overscroll-contain" : "max-h-[420px] overflow-y-auto overscroll-contain"}
        style={{ animation: "fade-up 160ms cubic-bezier(0.23,1,0.32,1) both" }}
      >{children}</div>
    </div>
  );
}

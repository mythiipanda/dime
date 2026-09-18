"use client";

import { useEffect, useRef, useState } from "react";
import type { ActivityRecord } from "../lib/chat";

const COLORS: Record<string, string> = {
  running: "var(--color-cyan-signal)",
  complete: "var(--color-ink-black)",
  ok: "var(--color-ink-black)",
  pass: "var(--color-ink-black)",
  approved: "var(--color-ink-black)",
  partial: "var(--color-gold, #9b6b00)",
  repair: "var(--color-gold, #9b6b00)",
  fail: "var(--color-ember)",
  failed: "var(--color-ember)",
  error: "var(--color-ember)",
  rejected: "var(--color-ember)",
};

function compactDetails(item: ActivityRecord) {
  const hidden = new Set(["event_id", "sequence", "correlation_id", "transition", "emitted_at", "node", "title", "summary", "text", "status"]);
  return Object.fromEntries(Object.entries(item.data).filter(([key, value]) =>
    !hidden.has(key) && value !== undefined && value !== null && value !== ""));
}

function EventRow({ item, active }: { item: ActivityRecord; active: boolean }) {
  const [open, setOpen] = useState(false);
  const details = compactDetails(item);
  const hasDetails = Object.keys(details).length > 0;
  const status = item.status || item.transition || (active ? "running" : "complete");
  const time = item.emittedAt ? new Date(item.emittedAt).toLocaleTimeString([], {
    hour: "numeric", minute: "2-digit", second: "2-digit",
  }) : "";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "14px minmax(0, 1fr)", gap: 8, position: "relative" }}>
      <div aria-hidden style={{ display: "flex", justifyContent: "center", paddingTop: 9 }}>
        <span className={active ? "pulse-dot" : undefined} style={{
          width: 7, height: 7, borderRadius: 99,
          background: COLORS[status.toLowerCase()] || "var(--color-ash-gray)", zIndex: 1,
        }} />
      </div>
      <button type="button" onClick={() => hasDetails && setOpen((value) => !value)}
        aria-expanded={hasDetails ? open : undefined}
        style={{ background: "none", border: 0, padding: "5px 0 7px", textAlign: "left", cursor: hasDetails ? "pointer" : "default", minWidth: 0 }}>
        <span style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--color-ink-black)" }}>{item.title}</span>
          {(item.transition || item.status) && <span style={{ fontSize: 10.5, color: COLORS[status.toLowerCase()] || "var(--color-ash-gray)", textTransform: "capitalize" }}>{(item.transition || item.status || "").replace(/_/g, " ")}</span>}
          {time && <span style={{ marginLeft: "auto", fontSize: 10.5, color: "var(--color-ash-gray)" }}>{time}</span>}
        </span>
        {item.summary && <span style={{ display: "block", marginTop: 2, whiteSpace: "pre-wrap", fontSize: 12, lineHeight: 1.45, color: "var(--color-warm-gray)" }}>{item.summary}</span>}
        {open && hasDetails && <pre style={{ margin: "6px 0 0", padding: 8, maxHeight: 280, overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere", border: "1px solid var(--color-stone-border)", borderRadius: 6, background: "var(--color-stone-canvas)", color: "var(--color-warm-gray)", fontSize: 10.5, lineHeight: 1.45 }}>{JSON.stringify(details, null, 2)}</pre>}
      </button>
    </div>
  );
}

export default function ActivityTimeline({ items, running }: { items: ActivityRecord[]; running: boolean }) {
  const viewport = useRef<HTMLDivElement>(null);
  const [following, setFollowing] = useState(true);
  const [seen, setSeen] = useState(items.length);
  useEffect(() => {
    if (following && viewport.current) {
      viewport.current.scrollTo({ top: viewport.current.scrollHeight, behavior: "smooth" });
      setSeen(items.length);
    }
  }, [items.length, following]);
  const unseen = Math.max(0, items.length - seen);
  return (
    <div style={{ position: "relative" }}>
      <div ref={viewport} role="log" aria-live="polite" aria-label="Live analysis activity"
        onScroll={(event) => {
          const el = event.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 28;
          setFollowing(atBottom);
          if (atBottom) setSeen(items.length);
        }}
        style={{ maxHeight: running ? 360 : 480, overflowY: "auto", paddingRight: 5 }}>
        {items.map((item, index) => <EventRow key={item.eventId} item={item} active={running && index === items.length - 1} />)}
      </div>
      {!following && unseen > 0 && <button type="button" className="pill-ghost" onClick={() => { setFollowing(true); setSeen(items.length); }} style={{ position: "sticky", bottom: 4, left: "50%", transform: "translateX(-50%)", fontSize: 11, background: "var(--color-paper-white)" }}>{unseen} new update{unseen === 1 ? "" : "s"}</button>}
    </div>
  );
}

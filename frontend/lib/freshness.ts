// One-line "Updated <date>" line for the bottom of the Explore page
// (redesign Phase 1). It speaks in human language — no "freshness",
// "system status", "sync", "pipeline", "endpoint", or "cache". Uses
// per-feed data-coverage dates (data_through), not ingestion time, and
// takes the earliest coverage across feeds so one fresh feed can't mask
// stale ones. Returns null when the endpoint has nothing — the footer
// then doesn't render at all.
import type { FreshRow } from "./api";

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export function freshDateLabel(iso: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso));
  if (!m) return null;
  const month = Number(m[2]);
  if (month < 1 || month > 12) return null;
  return `${MONTHS[month - 1]} ${Number(m[3])}`;
}

export function updatedLine(rows: FreshRow[]): string | null {
  const coverage = rows
    .map((r) => (r.data_through ? String(r.data_through) : ""))
    .filter(Boolean)
    .sort();
  if (coverage.length > 0) {
    // YYYY-MM-DD strings: lexicographic min == earliest coverage date.
    const label = freshDateLabel(coverage[0]);
    return label ? `Updated ${label}` : null;
  }
  // Backend predates coverage dates: fall back to the latest feed time.
  const fetches = rows
    .map((r) => (r.last_fetch ? String(r.last_fetch) : ""))
    .filter(Boolean)
    .sort();
  if (fetches.length === 0) return null;
  const label = freshDateLabel(fetches[fetches.length - 1]);
  return label ? `Updated ${label}` : null;
}

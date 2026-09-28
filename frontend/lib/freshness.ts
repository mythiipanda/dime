// One-line freshness summary for the Explore sticky-nav status (redesign
// Phase C). Derives "Data through Sep 26 · 5 datasets" from the same
// /datasets/freshness rows the System status disclosure shows, replacing the
// old decorative "2025-26" mark with a real, clickable fact.
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

// Latest last_fetch across tables; null when nothing has a fetch time.
// Timestamps arrive as YYYY-MM-DD..., so lexicographic max == latest.
export function summarizeFreshness(rows: FreshRow[]): string | null {
  const fetches = rows
    .map((r) => (r.last_fetch ? String(r.last_fetch) : ""))
    .filter(Boolean)
    .sort();
  if (fetches.length === 0) return null;
  const label = freshDateLabel(fetches[fetches.length - 1]);
  if (!label) return null;
  const datasets = rows.filter((r) => (r.rows ?? 0) > 0).length;
  return datasets > 0
    ? `Data through ${label} · ${datasets} datasets`
    : `Data through ${label}`;
}

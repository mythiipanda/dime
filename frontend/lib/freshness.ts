













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
    

    const label = freshDateLabel(coverage[0]);
    return label ? `Updated ${label}` : null;
  }
  

  const fetches = rows
    .map((r) => (r.last_fetch ? String(r.last_fetch) : ""))
    .filter(Boolean)
    .sort();
  if (fetches.length === 0) return null;
  const label = freshDateLabel(fetches[fetches.length - 1]);
  return label ? `Updated ${label}` : null;
}

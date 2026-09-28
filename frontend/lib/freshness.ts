// One-line freshness summary for the Explore sticky-nav status (redesign
// Phase C). Uses per-feed DATA COVERAGE dates (data_through), not ingestion
// time: last_fetch says when the warehouse pulled a table, which misleads
// when shown as "Data through <date>". The summary takes the MINIMUM
// coverage across covered tables so one fresh table can't mask stale ones;
// the System status disclosure shows the per-feed detail.
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

function coverageParticipants(rows: FreshRow[]): FreshRow[] {
  // Only datasets that actually feed the coverage minimum. Static/snapshot
  // tables with no data_through (combine, standings) are freshness-checked
  // nowhere, so counting them overstates the label.
  return rows.filter((r) => (r.rows ?? 0) > 0 && Boolean(r.data_through));
}

function fetchParticipants(rows: FreshRow[]): FreshRow[] {
  return rows.filter((r) => (r.rows ?? 0) > 0 && Boolean(r.last_fetch));
}

// Latest ingestion times; lexicographic max on YYYY-MM-DD... timestamps.
function latestFetchLabel(rows: FreshRow[]): string | null {
  const fetches = rows
    .map((r) => (r.last_fetch ? String(r.last_fetch) : ""))
    .filter(Boolean)
    .sort();
  if (fetches.length === 0) return null;
  return freshDateLabel(fetches[fetches.length - 1]);
}

export function summarizeFreshness(rows: FreshRow[]): string | null {
  const coverage = rows
    .map((r) => (r.data_through ? String(r.data_through) : ""))
    .filter(Boolean)
    .sort();
  if (coverage.length > 0) {
    // YYYY-MM-DD strings: lexicographic min == earliest coverage date.
    const label = freshDateLabel(coverage[0]);
    if (!label) return null;
    const datasets = coverageParticipants(rows).length;
    return datasets > 0
      ? `Data through ${label} · ${datasets} datasets`
      : `Data through ${label}`;
  }
  // Backend predates coverage dates: name the thing we actually know --
  // the last warehouse fetch -- instead of implying data coverage.
  const label = latestFetchLabel(rows);
  if (!label) return null;
  const datasets = fetchParticipants(rows).length;
  return datasets > 0
    ? `Last fetch ${label} · ${datasets} datasets`
    : `Last fetch ${label}`;
}

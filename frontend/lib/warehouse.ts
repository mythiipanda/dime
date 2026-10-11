import type { WarehouseTableRow } from "./api";

export type CanonicalSeason = { start_year: number; end_year: number };

export type SeasonCoverage = "available" | "unavailable" | "unknown";

export function parseSeasonValue(value: string): CanonicalSeason | null {
  if (typeof value !== "string") return null;
  const v = value.trim();
  if (/^\d{4}$/.test(v)) return null;
  if (/^[24]\d{4}$/.test(v)) return null;
  const span = v.match(/^(\d{4})-(\d{2}|\d{4})$/);
  if (span) {
    const start_year = Number(span[1]);
    const suffix = span[2];
    if (!Number.isInteger(start_year) || start_year < 1800 || start_year > 3000) return null;
    let end_year: number;
    if (suffix.length === 4) {
      end_year = Number(suffix);
    } else {
      const century = Math.floor(start_year / 100) * 100;
      end_year = century + Number(suffix);
      if (end_year <= start_year) end_year += 100;
    }
    if (!Number.isInteger(end_year) || end_year !== start_year + 1) return null;
    return { start_year, end_year };
  }
  return null;
}

export function getCanonicalSeasonRange(range: { min: string; max: string } | null | undefined): {
  min: CanonicalSeason;
  max: CanonicalSeason;
} | null {
  if (!range) return null;
  const min = parseSeasonValue(range.min);
  const max = parseSeasonValue(range.max);
  if (!min || !max) return null;
  return { min, max };
}

export function getSeason2627Coverage(tables: WarehouseTableRow[]): SeasonCoverage {
  return "unknown";
}

export function hasSeason2627(tables: WarehouseTableRow[]): boolean {
  return getSeason2627Coverage(tables) === "available";
}

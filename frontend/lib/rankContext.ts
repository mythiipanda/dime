export interface RankContext {
  rank: number;
  percentile: number;
  chip: string;
}

/**
 * Rank context for one row of an Explore leaders table (redesign Phase 2).
 *
 * The leaders endpoint returns rows ranked descending by the requested
 * stat, so rank is the 1-based position in that returned list. Pass the
 * row's index in the original unsorted list, never the position after
 * the user re-sorts or filters the table.
 *
 * Ties get no tie-averaging: equal values keep position-based ranks, so
 * the first occurrence keeps the better rank, matching the returned order.
 */
export function rankOf(index: number, total: number): RankContext {
  const safeTotal = Math.max(1, Math.floor(total));
  const rank = Math.min(Math.max(1, Math.floor(index) + 1), safeTotal);
  const percentile = safeTotal <= 1
    ? 100
    : Math.min(
      100,
      Math.max(0, Math.round(((safeTotal - rank) / (safeTotal - 1)) * 100)),
    );
  return { rank, percentile, chip: `#${rank}` };
}

interface RankContext {
  rank: number;
  percentile: number;
  chip: string;
}













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

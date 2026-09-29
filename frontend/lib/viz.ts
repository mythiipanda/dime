




export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}



export function ordinal(n: number): string {
  const r = Math.round(n);
  const mod100 = ((r % 100) + 100) % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${r}th`;
  switch (r % 10) {
    case 1:
      return `${r}st`;
    case 2:
      return `${r}nd`;
    case 3:
      return `${r}rd`;
    default:
      return `${r}th`;
  }
}



export function formatPct(v: number, digits = 1): string {
  return `${(v * 100).toFixed(digits)}%`;
}






export function percentileRank(sortedAsc: number[], v: number): number {
  if (!sortedAsc.length) return 0;
  let le = 0;
  for (const x of sortedAsc) {
    if (x <= v) le += 1;
  }
  return le / sortedAsc.length;
}

export interface HistBin {
  lo: number;
  hi: number;
  count: number;
}



export function histogramBins(values: number[], binCount: number): HistBin[] {
  const bins: HistBin[] = [];
  if (!values.length || binCount < 1) return bins;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = (max - min || 1) / binCount;
  const counts = new Array<number>(binCount).fill(0);
  for (const v of values) {
    const i = Math.min(binCount - 1, Math.floor((v - min) / width));
    counts[i] += 1;
  }
  for (let i = 0; i < binCount; i++) {
    bins.push({ lo: min + i * width, hi: min + (i + 1) * width, count: counts[i] });
  }
  return bins;
}







export function categoryAxisWidth(labels: string[]): number {
  if (!labels.length) return 70;
  const longest = Math.max(...labels.map((l) => l.length));
  return clamp(Math.ceil(longest * 7 + 8), 70, 170);
}

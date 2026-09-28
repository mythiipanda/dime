// Mock data for the viz prototypes. Fictional numbers for design review only.
import type { ZoneStat } from "./ZoneShotChart";
import type { PercentileRow } from "./PercentileBars";
import type { TrendPoint } from "./StatTrend";

export const mockZones: ZoneStat[] = [
  { key: "restricted-area", short: "Rim", label: "Restricted area", fgm: 118, fga: 172, fgPct: 0.686, leagueAvg: 0.671 },
  { key: "paint", short: "Paint", label: "Paint, non-restricted", fgm: 41, fga: 96, fgPct: 0.427, leagueAvg: 0.443 },
  { key: "mid-left", short: "Mid L", label: "Mid-range left", fgm: 22, fga: 54, fgPct: 0.407, leagueAvg: 0.421 },
  { key: "mid-center", short: "Mid C", label: "Mid-range center", fgm: 35, fga: 88, fgPct: 0.398, leagueAvg: 0.435 },
  { key: "mid-right", short: "Mid R", label: "Mid-range right", fgm: 19, fga: 47, fgPct: 0.404, leagueAvg: 0.419 },
  { key: "corner-3-left", short: "LC3", label: "Left corner 3", fgm: 28, fga: 71, fgPct: 0.394, leagueAvg: 0.386 },
  { key: "corner-3-right", short: "RC3", label: "Right corner 3", fgm: 24, fga: 66, fgPct: 0.364, leagueAvg: 0.388 },
  { key: "above-break-3", short: "ATB3", label: "Above the break 3", fgm: 96, fga: 248, fgPct: 0.387, leagueAvg: 0.357 },
];

export const mockPercentiles: PercentileRow[] = [
  { label: "True shooting", value: "61.8%", percentile: 88 },
  { label: "3-point rate", value: "46%", percentile: 94 },
  { label: "Free throw rate", value: ".281", percentile: 55 },
  { label: "Assist rate", value: "18.2%", percentile: 61 },
  { label: "Rebound rate", value: "7.4%", percentile: 42 },
  { label: "Turnover rate", value: "11.9%", percentile: 35 },
];

export const mockTrend: TrendPoint[] = [
  { label: "vs BOS", value: 24 },
  { label: "vs NYK", value: 31 },
  { label: "@ MIA", value: 18 },
  { label: "vs PHI", value: 27 },
  { label: "@ CHI", value: 33 },
  { label: "vs DET", value: 22 },
  { label: "@ ATL", value: 29 },
  { label: "vs ORL", value: 26 },
  { label: "@ WAS", value: 35 },
  { label: "vs CHA", value: 28 },
];

// Deterministic pseudo-random league distribution around 54.5% eFG.
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const mockLeagueEfg: number[] = (() => {
  const rnd = mulberry32(42);
  const arr: number[] = [];
  for (let i = 0; i < 140; i++) {
    arr.push(0.545 + (rnd() + rnd() + rnd() - 1.5) * 0.06);
  }
  return arr;
})();

export const mockPlayerEfg = 0.596;

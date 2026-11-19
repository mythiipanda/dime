export type MatchupStat = {
  label: string;
  away: number;
  home: number;
  fmt: (v: number) => string;
  lowerBetter?: boolean;
};

export type Matchup = {
  id: string;
  away: string;
  awayName: string;
  awayRecord: string;
  home: string;
  homeName: string;
  homeRecord: string;
  time: string;
  network: string;
  stats: MatchupStat[];
  awayForm: ("W" | "L")[];
  homeForm: ("W" | "L")[];
  notes: string[];
};

const f1 = (v: number) => v.toFixed(1);
const pct = (v: number) => v.toFixed(1) + "%";
const signed = (v: number) => (v > 0 ? "+" : "") + v.toFixed(1);

export const matchups: Matchup[] = [
  {
    id: "bos-nyk",
    away: "BOS", awayName: "Celtics", awayRecord: "3-1",
    home: "NYK", homeName: "Knicks", homeRecord: "2-2",
    time: "7:30p", network: "TNT",
    stats: [
      { label: "Net rating", away: 8.2, home: 3.1, fmt: signed },
      { label: "Offensive rating", away: 121.4, home: 118.2, fmt: f1 },
      { label: "Defensive rating", away: 113.2, home: 115.1, fmt: f1, lowerBetter: true },
      { label: "Pace", away: 99.8, home: 97.4, fmt: f1 },
      { label: "3P%", away: 38.9, home: 36.2, fmt: pct },
      { label: "Rebound %", away: 51.4, home: 52.8, fmt: pct },
    ],
    awayForm: ["W", "W", "W", "L", "W", "W", "L", "W", "W", "W"],
    homeForm: ["W", "L", "W", "W", "L", "W", "L", "W", "L", "W"],
    notes: [
      "Boston shoots 38.9% from three. New York's closeouts decide this.",
      "Tatum is questionable. Boston's offense drops 6 points per 100 without him.",
      "The Knicks are 8-2 at home against Boston since 2023.",
    ],
  },
  {
    id: "dal-okc",
    away: "DAL", awayName: "Mavericks", awayRecord: "3-2",
    home: "OKC", homeName: "Thunder", homeRecord: "4-0",
    time: "8:00p", network: "ESPN",
    stats: [
      { label: "Net rating", away: 4.6, home: 11.8, fmt: signed },
      { label: "Offensive rating", away: 119.6, home: 122.9, fmt: f1 },
      { label: "Defensive rating", away: 115.0, home: 111.1, fmt: f1, lowerBetter: true },
      { label: "Pace", away: 101.2, home: 100.4, fmt: f1 },
      { label: "3P%", away: 37.1, home: 39.4, fmt: pct },
      { label: "Rebound %", away: 50.2, home: 51.9, fmt: pct },
    ],
    awayForm: ["W", "W", "L", "W", "L", "W", "W", "L", "W", "W"],
    homeForm: ["W", "W", "W", "W", "W", "W", "L", "W", "W", "W"],
    notes: [
      "Oklahoma City's defense forces turnovers on 16% of possessions. Dallas has to protect the ball.",
      "Dončić and Gilgeous-Alexander both top 30 usage. Whichever defense loads up first loses the other matchup.",
      "The Thunder are 4-0 with a +11.8 net. Nobody has stayed within single digits yet.",
    ],
  },
  {
    id: "den-phx",
    away: "DEN", awayName: "Nuggets", awayRecord: "3-1",
    home: "PHX", homeName: "Suns", homeRecord: "2-3",
    time: "9:00p", network: "TNT",
    stats: [
      { label: "Net rating", away: 6.4, home: 1.2, fmt: signed },
      { label: "Offensive rating", away: 120.1, home: 117.8, fmt: f1 },
      { label: "Defensive rating", away: 113.7, home: 116.6, fmt: f1, lowerBetter: true },
      { label: "Pace", away: 98.6, home: 99.9, fmt: f1 },
      { label: "3P%", away: 36.8, home: 37.9, fmt: pct },
      { label: "Rebound %", away: 53.1, home: 49.4, fmt: pct },
    ],
    awayForm: ["W", "W", "L", "W", "W", "W", "L", "W", "W", "L"],
    homeForm: ["L", "W", "L", "W", "L", "L", "W", "L", "W", "W"],
    notes: [
      "Jokić is averaging a 28-point triple-double. Phoenix has no answer for him inside.",
      "Durant is probable. The Suns are 2-0 when he clears 30 minutes.",
      "Denver's bench is last in scoring. If this stays close late, depth matters.",
    ],
  },
  {
    id: "lal-gsw",
    away: "LAL", awayName: "Lakers", awayRecord: "2-2",
    home: "GSW", homeName: "Warriors", homeRecord: "3-2",
    time: "10:30p", network: "TNT",
    stats: [
      { label: "Net rating", away: 2.8, home: 4.9, fmt: signed },
      { label: "Offensive rating", away: 118.4, home: 119.7, fmt: f1 },
      { label: "Defensive rating", away: 115.6, home: 114.8, fmt: f1, lowerBetter: true },
      { label: "Pace", away: 100.8, home: 102.3, fmt: f1 },
      { label: "3P%", away: 35.9, home: 38.4, fmt: pct },
      { label: "Rebound %", away: 50.8, home: 49.9, fmt: pct },
    ],
    awayForm: ["W", "L", "W", "L", "W", "L", "W", "W", "L", "W"],
    homeForm: ["W", "W", "L", "W", "L", "W", "W", "L", "W", "W"],
    notes: [
      "Golden State plays at the league's fastest pace. The Lakers want this in the half court.",
      "Curry is probable. His gravity opens the floor even on quiet scoring nights.",
      "Los Angeles is 1-7 in their last eight trips to Chase Center.",
    ],
  },
];

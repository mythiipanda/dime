export type PlayerRow = {
  name: string; team: string; gp: number; ppg: number; ts: number; usg: number; net: number;
};
export const exploreRows: PlayerRow[] = [
  { name: "Shai Gilgeous-Alexander", team: "OKC", gp: 52, ppg: 31.2, ts: 64.1, usg: 33.6, net: 11.3 },
  { name: "Luka Dončić", team: "DAL", gp: 49, ppg: 30.4, ts: 61.8, usg: 34.1, net: 7.8 },
  { name: "Nikola Jokić", team: "DEN", gp: 51, ppg: 28.1, ts: 65.9, usg: 28.4, net: 12.6 },
  { name: "Jayson Tatum", team: "BOS", gp: 53, ppg: 28.9, ts: 60.4, usg: 30.2, net: 9.1 },
  { name: "Giannis Antetokounmpo", team: "MIL", gp: 48, ppg: 27.5, ts: 63.2, usg: 32.9, net: 8.8 },
  { name: "Anthony Edwards", team: "MIN", gp: 52, ppg: 27.8, ts: 59.7, usg: 31.8, net: 6.4 },
  { name: "Kevin Durant", team: "PHX", gp: 50, ppg: 27.1, ts: 62.4, usg: 29.8, net: 5.9 },
  { name: "Stephen Curry", team: "GSW", gp: 51, ppg: 26.8, ts: 61.2, usg: 30.6, net: 7.2 },
];

export type Game = { away: string; home: string; time: string; line: string; ou: string; note?: string; live?: boolean };
export const tonightGames: Game[] = [
  { away: "BOS", home: "NYK", time: "7:30p", line: "BOS -3.5", ou: "O/U 224.5", note: "Tatum questionable", live: true },
  { away: "DEN", home: "PHX", time: "9:00p", line: "DEN -1.5", ou: "O/U 231.0" },
  { away: "LAL", home: "GSW", time: "10:30p", line: "GSW -2.5", ou: "O/U 228.5", note: "Curry probable" },
  { away: "MIL", home: "PHI", time: "7:00p", line: "MIL -5.5", ou: "O/U 219.0" },
  { away: "DAL", home: "OKC", time: "8:00p", line: "OKC -7.5", ou: "O/U 233.5" },
  { away: "MIN", home: "MEM", time: "8:30p", line: "MIN -2.0", ou: "O/U 221.5" },
];

export type AwardRow = { rk: number; player: string; team: string; rating: number; trend: number };
export const awards: AwardRow[] = [
  { rk: 1, player: "Nikola Jokić", team: "DEN", rating: 94, trend: 2.0 },
  { rk: 2, player: "Shai Gilgeous-Alexander", team: "OKC", rating: 91, trend: 0.0 },
  { rk: 3, player: "Luka Dončić", team: "DAL", rating: 86, trend: -1.0 },
  { rk: 4, player: "Jayson Tatum", team: "BOS", rating: 82, trend: 1.0 },
  { rk: 5, player: "Giannis Antetokounmpo", team: "MIL", rating: 79, trend: -2.0 },
  { rk: 6, player: "Anthony Edwards", team: "MIN", rating: 74, trend: 3.0 },
];

export const thinkRows = [
  { primary: "Parsing the comparison scope", secondary: "SGA vs Dončić — scoring, efficiency, team context" },
  { primary: "Planning warehouse queries", secondary: "boxscores · lineups · tracking, last 30" },
  { primary: "Checking evidence coverage", secondary: "50+ games each, no gaps" },
];

export const compareRows = [
  { label: "Points per game", a: 31.2, b: 30.4, fmt: (v: number) => v.toFixed(1) },
  { label: "True shooting %", a: 64.1, b: 61.8, fmt: (v: number) => v.toFixed(1) + "%" },
  { label: "Usage %", a: 33.6, b: 34.1, fmt: (v: number) => v.toFixed(1) + "%" },
  { label: "Assist %", a: 29.4, b: 38.2, fmt: (v: number) => v.toFixed(1) + "%" },
  { label: "On-court net /100", a: 11.3, b: 7.8, fmt: (v: number) => (v > 0 ? "+" : "") + v.toFixed(1) },
  { label: "Off-court net /100", a: 2.1, b: 1.4, fmt: (v: number) => (v > 0 ? "+" : "") + v.toFixed(1) },
];

export const answerText =
  "On raw scoring it's closer than the narratives suggest. Gilgeous-Alexander is at 31.2 ppg on 64.1% TS over the last 30; Dončić is at 30.4 ppg on 61.8% TS, about one extra efficient possession per game. The separation shows up in team context: OKC is +11.3 per 100 with SGA on versus +2.1 with him off; Dallas is +7.8 / +1.4 with Dončić. Playmaking load favors Dončić: 38.2% assist rate against SGA's 29.4%, on nearly identical usage.";

export const followUps = [
  "Who defends better by matchup data?",
  "Clutch splits, last 5 minutes?",
  "Shot charts side by side?",
];

export const sgaTrend = [28, 34, 29, 38, 31, 27, 35, 33, 30, 36, 29, 32, 41, 26, 34];
export const lukaTrend = [33, 27, 36, 29, 31, 40, 24, 32, 35, 28, 30, 37, 26, 33, 29];

export type ShotZone = { x: number; y: number; att: number; pct: number };
export const sgaZones: ShotZone[] = [
  { x: 50, y: 12, att: 142, pct: 71 }, { x: 32, y: 22, att: 88, pct: 52 }, { x: 68, y: 22, att: 91, pct: 54 },
  { x: 18, y: 38, att: 64, pct: 47 }, { x: 50, y: 34, att: 118, pct: 49 }, { x: 82, y: 38, att: 59, pct: 45 },
  { x: 12, y: 62, att: 47, pct: 39 }, { x: 50, y: 58, att: 52, pct: 37 }, { x: 88, y: 62, att: 44, pct: 41 },
  { x: 28, y: 82, att: 38, pct: 36 }, { x: 72, y: 82, att: 35, pct: 38 },
];

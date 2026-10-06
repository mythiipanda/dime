export type PropMarket = "Points" | "Rebounds" | "Assists" | "Threes";

export type PropRow = {
  player: string;
  team: string;
  market: PropMarket;
  line: number;
  hits: number;
  edge: number | null;
};

export const propRows: PropRow[] = [
  { player: "Shai Gilgeous-Alexander", team: "OKC", market: "Points", line: 31.5, hits: 7, edge: 1.8 },
  { player: "Luka Dončić", team: "DAL", market: "Assists", line: 9.5, hits: 6, edge: 0.9 },
  { player: "Nikola Jokić", team: "DEN", market: "Rebounds", line: 12.5, hits: 8, edge: 2.1 },
  { player: "Jayson Tatum", team: "BOS", market: "Points", line: 27.5, hits: 5, edge: -1.2 },
  { player: "Giannis Antetokounmpo", team: "MIL", market: "Points", line: 28.5, hits: 6, edge: null },
  { player: "Anthony Edwards", team: "MIN", market: "Threes", line: 3.5, hits: 7, edge: 0.6 },
  { player: "Kevin Durant", team: "PHX", market: "Points", line: 26.5, hits: 6, edge: null },
  { player: "Stephen Curry", team: "GSW", market: "Threes", line: 4.5, hits: 5, edge: -0.8 },
  { player: "Joel Embiid", team: "PHI", market: "Rebounds", line: 10.5, hits: 4, edge: -1.5 },
  { player: "Tyrese Haliburton", team: "IND", market: "Assists", line: 11.5, hits: 8, edge: 1.4 },
  { player: "Devin Booker", team: "PHX", market: "Points", line: 25.5, hits: 7, edge: 0.4 },
  { player: "Anthony Davis", team: "LAL", market: "Rebounds", line: 13.5, hits: 6, edge: null },
  { player: "Jalen Brunson", team: "NYK", market: "Points", line: 24.5, hits: 8, edge: 1.1 },
  { player: "Trae Young", team: "ATL", market: "Assists", line: 10.5, hits: 5, edge: -0.5 },
  { player: "Karl-Anthony Towns", team: "NYK", market: "Threes", line: 2.5, hits: 6, edge: null },
  { player: "LeBron James", team: "LAL", market: "Points", line: 23.5, hits: 6, edge: 0.2 },
  { player: "Damian Lillard", team: "MIL", market: "Threes", line: 3.5, hits: 4, edge: -1.0 },
  { player: "Domantas Sabonis", team: "SAC", market: "Rebounds", line: 14.5, hits: 9, edge: 2.6 },
  { player: "Cade Cunningham", team: "DET", market: "Assists", line: 8.5, hits: 7, edge: 0.7 },
  { player: "Victor Wembanyama", team: "SAS", market: "Rebounds", line: 11.5, hits: 5, edge: null },
];

export const propMarkets: ("All" | PropMarket)[] = ["All", "Points", "Rebounds", "Assists", "Threes"];

export type ExplorePlayer = {
  name: string;
  team: string;
  pos: string;
  gp: number;
  mpg: number;
  ppg: number;
  rpg: number;
  apg: number;
  ts: number;
  usg: number;
  net: number;
};

export const explorePlayers: ExplorePlayer[] = [
  { name: "Shai Gilgeous-Alexander", team: "OKC", pos: "G", gp: 52, mpg: 34.2, ppg: 31.2, rpg: 5.8, apg: 6.4, ts: 64.1, usg: 33.6, net: 11.3 },
  { name: "Luka Dončić", team: "DAL", pos: "G", gp: 49, mpg: 35.1, ppg: 30.4, rpg: 8.9, apg: 9.1, ts: 61.8, usg: 34.1, net: 7.8 },
  { name: "Jayson Tatum", team: "BOS", pos: "F", gp: 53, mpg: 35.6, ppg: 28.9, rpg: 8.7, apg: 5.2, ts: 60.4, usg: 30.2, net: 9.1 },
  { name: "Nikola Jokić", team: "DEN", pos: "C", gp: 51, mpg: 34.8, ppg: 28.1, rpg: 12.4, apg: 9.8, ts: 65.9, usg: 28.4, net: 12.6 },
  { name: "Anthony Edwards", team: "MIN", pos: "G", gp: 52, mpg: 35.9, ppg: 27.8, rpg: 5.9, apg: 5.1, ts: 59.7, usg: 31.8, net: 6.4 },
  { name: "Giannis Antetokounmpo", team: "MIL", pos: "F", gp: 48, mpg: 34.1, ppg: 27.5, rpg: 11.2, apg: 6.1, ts: 63.2, usg: 32.9, net: 8.8 },
  { name: "Kevin Durant", team: "PHX", pos: "F", gp: 50, mpg: 35.2, ppg: 27.1, rpg: 6.8, apg: 4.9, ts: 62.4, usg: 29.8, net: 5.9 },
  { name: "Stephen Curry", team: "GSW", pos: "G", gp: 51, mpg: 33.4, ppg: 26.8, rpg: 4.9, apg: 5.8, ts: 61.2, usg: 30.6, net: 7.2 },
  { name: "Donovan Mitchell", team: "CLE", pos: "G", gp: 52, mpg: 34.6, ppg: 26.4, rpg: 5.1, apg: 6.0, ts: 60.8, usg: 30.1, net: 8.4 },
  { name: "Devin Booker", team: "PHX", pos: "G", gp: 53, mpg: 36.1, ppg: 25.9, rpg: 4.8, apg: 7.2, ts: 59.4, usg: 29.4, net: 4.1 },
  { name: "Tyrese Maxey", team: "PHI", pos: "G", gp: 50, mpg: 37.2, ppg: 25.8, rpg: 4.2, apg: 6.9, ts: 58.1, usg: 29.9, net: 3.2 },
  { name: "Jaylen Brown", team: "BOS", pos: "F", gp: 51, mpg: 34.8, ppg: 25.2, rpg: 6.9, apg: 4.8, ts: 58.9, usg: 28.7, net: 7.6 },
  { name: "Damian Lillard", team: "MIL", pos: "G", gp: 52, mpg: 35.4, ppg: 24.9, rpg: 4.4, apg: 7.0, ts: 60.9, usg: 28.2, net: 5.1 },
  { name: "Anthony Davis", team: "DAL", pos: "C", gp: 46, mpg: 34.4, ppg: 24.8, rpg: 12.1, apg: 3.4, ts: 62.8, usg: 27.5, net: 6.9 },
  { name: "LeBron James", team: "LAL", pos: "F", gp: 49, mpg: 34.9, ppg: 24.6, rpg: 7.8, apg: 8.2, ts: 60.2, usg: 28.1, net: 5.4 },
  { name: "Joel Embiid", team: "PHI", pos: "C", gp: 39, mpg: 32.1, ppg: 24.2, rpg: 9.6, apg: 4.8, ts: 62.2, usg: 30.8, net: 4.4 },
  { name: "Kawhi Leonard", team: "LAC", pos: "F", gp: 44, mpg: 33.8, ppg: 24.1, rpg: 6.4, apg: 4.1, ts: 61.5, usg: 28.8, net: 6.2 },
  { name: "Cade Cunningham", team: "DET", pos: "G", gp: 53, mpg: 35.2, ppg: 23.9, rpg: 6.8, apg: 8.9, ts: 57.9, usg: 29.8, net: 4.2 },
  { name: "Ja Morant", team: "MEM", pos: "G", gp: 47, mpg: 32.6, ppg: 23.8, rpg: 5.2, apg: 8.4, ts: 57.6, usg: 30.4, net: 4.8 },
  { name: "Trae Young", team: "ATL", pos: "G", gp: 53, mpg: 35.8, ppg: 23.4, rpg: 3.9, apg: 10.8, ts: 58.8, usg: 29.1, net: 2.9 },
  { name: "Paolo Banchero", team: "ORL", pos: "F", gp: 50, mpg: 34.2, ppg: 23.1, rpg: 7.4, apg: 5.3, ts: 57.2, usg: 29.6, net: 3.8 },
  { name: "Victor Wembanyama", team: "SAS", pos: "C", gp: 52, mpg: 32.4, ppg: 22.9, rpg: 10.8, apg: 4.2, ts: 60.1, usg: 27.8, net: 7.4 },
  { name: "Kyrie Irving", team: "DAL", pos: "G", gp: 50, mpg: 34.0, ppg: 22.4, rpg: 4.8, apg: 5.9, ts: 60.5, usg: 27.1, net: 6.1 },
  { name: "Jimmy Butler", team: "MIA", pos: "F", gp: 48, mpg: 33.6, ppg: 21.8, rpg: 6.2, apg: 5.4, ts: 59.8, usg: 26.4, net: 5.8 },
];

export const exploreTeams: string[] = Array.from(
  new Set(explorePlayers.map((p) => p.team))
).sort();

export type LineupShots = { rim: number; mid: number; three: number };

export type Lineup = {
  id: string;
  team: string;
  players: string[];
  min: number;
  ortg: number;
  drtg: number;
  shots: LineupShots;
  note: string;
};

export const lineupTeams = ["OKC", "BOS", "DEN", "DAL", "MIN", "NYK"];

export const lineups: Lineup[] = [
  {
    id: "okc-1", team: "OKC",
    players: ["Gilgeous-Alexander", "Dort", "Williams", "Holmgren", "Hartenstein"],
    min: 412, ortg: 121.4, drtg: 106.2,
    shots: { rim: 38, mid: 22, three: 40 },
    note: "Best defensive unit in the sample. Holmgren covers the rim and Dort takes the top assignment.",
  },
  {
    id: "okc-2", team: "OKC",
    players: ["Gilgeous-Alexander", "Caruso", "Dort", "Williams", "Holmgren"],
    min: 238, ortg: 119.8, drtg: 104.9,
    shots: { rim: 36, mid: 24, three: 40 },
    note: "Small-ball closing group. Switches everything across the floor.",
  },
  {
    id: "okc-3", team: "OKC",
    players: ["Gilgeous-Alexander", "Joe", "Wiggins", "Williams", "Hartenstein"],
    min: 156, ortg: 122.1, drtg: 110.4,
    shots: { rim: 33, mid: 20, three: 47 },
    note: "Shooting-heavy second unit. Nearly half its shots come from the arc.",
  },
  {
    id: "bos-1", team: "BOS",
    players: ["White", "Brown", "Tatum", "Horford", "Porzingis"],
    min: 388, ortg: 120.2, drtg: 109.8,
    shots: { rim: 34, mid: 18, three: 48 },
    note: "Five-out spacing. Porzingis punishes switches in the post.",
  },
  {
    id: "bos-2", team: "BOS",
    players: ["Pritchard", "White", "Brown", "Tatum", "Kornet"],
    min: 204, ortg: 121.5, drtg: 112.3,
    shots: { rim: 35, mid: 16, three: 49 },
    note: "Pritchard runs the bench minutes. Pace jumps when he is on the ball.",
  },
  {
    id: "bos-3", team: "BOS",
    players: ["White", "Brown", "Tatum", "Hauser", "Horford"],
    min: 142, ortg: 118.9, drtg: 108.7,
    shots: { rim: 32, mid: 19, three: 49 },
    note: "Defense-first close. Hauser chases shooters off the line.",
  },
  {
    id: "den-1", team: "DEN",
    players: ["Murray", "Braun", "Porter", "Gordon", "Jokic"],
    min: 445, ortg: 122.8, drtg: 112.1,
    shots: { rim: 40, mid: 24, three: 36 },
    note: "The starters. The Jokic-Gordon two-man game carries the half court.",
  },
  {
    id: "den-2", team: "DEN",
    players: ["Murray", "Strawther", "Gordon", "Watson", "Jokic"],
    min: 178, ortg: 119.4, drtg: 113.8,
    shots: { rim: 37, mid: 22, three: 41 },
    note: "Bench bridge. Holds the lead without Murray creating every trip.",
  },
  {
    id: "dal-1", team: "DAL",
    players: ["Irving", "Doncic", "Thompson", "Washington", "Gafford"],
    min: 366, ortg: 120.6, drtg: 113.2,
    shots: { rim: 39, mid: 21, three: 40 },
    note: "Two creators plus shooting. Gafford gives vertical spacing on rolls.",
  },
  {
    id: "dal-2", team: "DAL",
    players: ["Irving", "Doncic", "Marshall", "Washington", "Lively"],
    min: 189, ortg: 119.1, drtg: 111.9,
    shots: { rim: 41, mid: 20, three: 39 },
    note: "Bigger wing minutes. Lively drops in coverage behind the guards.",
  },
  {
    id: "dal-3", team: "DAL",
    players: ["Dinwiddie", "Grimes", "Prosper", "Kleber", "Powell"],
    min: 87, ortg: 108.4, drtg: 116.2,
    shots: { rim: 36, mid: 24, three: 40 },
    note: "End-of-bench minutes. The offense stalls without a creator on the floor.",
  },
  {
    id: "min-1", team: "MIN",
    players: ["Conley", "Edwards", "McDaniels", "Randle", "Gobert"],
    min: 402, ortg: 118.3, drtg: 109.5,
    shots: { rim: 42, mid: 20, three: 38 },
    note: "The starters. Edwards-Randle pick and roll with Gobert cleaning up.",
  },
  {
    id: "min-2", team: "MIN",
    players: ["DiVincenzo", "Edwards", "McDaniels", "Reid", "Gobert"],
    min: 211, ortg: 120.9, drtg: 112.6,
    shots: { rim: 38, mid: 18, three: 44 },
    note: "Reid at the five opens the floor. The best offensive bench look.",
  },
  {
    id: "nyk-1", team: "NYK",
    players: ["Brunson", "Bridges", "Anunoby", "Hart", "Towns"],
    min: 389, ortg: 121.1, drtg: 112.9,
    shots: { rim: 37, mid: 19, three: 44 },
    note: "Heavy-minutes starters. Brunson-Towns pick and pop is the base action.",
  },
  {
    id: "nyk-2", team: "NYK",
    players: ["Brunson", "McBride", "Bridges", "Anunoby", "Towns"],
    min: 167, ortg: 122.4, drtg: 114.1,
    shots: { rim: 35, mid: 17, three: 48 },
    note: "Three-guard look. Trades some defense for shooting.",
  },
];

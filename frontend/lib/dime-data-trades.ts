export type TradePlayer = { name: string; salary: number };

export type TradeTeam = { abbr: string; name: string; players: TradePlayer[] };

export const tradeTeams: TradeTeam[] = [
  {
    abbr: "OKC", name: "Thunder",
    players: [
      { name: "Shai Gilgeous-Alexander", salary: 38.3 },
      { name: "Jalen Williams", salary: 6.6 },
      { name: "Chet Holmgren", salary: 13.7 },
      { name: "Luguentz Dort", salary: 17.7 },
      { name: "Isaiah Hartenstein", salary: 30.0 },
      { name: "Alex Caruso", salary: 9.9 },
    ],
  },
  {
    abbr: "BOS", name: "Celtics",
    players: [
      { name: "Jayson Tatum", salary: 54.1 },
      { name: "Jaylen Brown", salary: 53.3 },
      { name: "Derrick White", salary: 28.1 },
      { name: "Jrue Holiday", salary: 32.4 },
      { name: "Kristaps Porzingis", salary: 30.7 },
      { name: "Payton Pritchard", salary: 6.7 },
    ],
  },
  {
    abbr: "DEN", name: "Nuggets",
    players: [
      { name: "Nikola Jokic", salary: 55.2 },
      { name: "Jamal Murray", salary: 50.0 },
      { name: "Aaron Gordon", salary: 22.8 },
      { name: "Michael Porter Jr.", salary: 38.3 },
      { name: "Christian Braun", salary: 4.7 },
      { name: "Peyton Watson", salary: 2.4 },
    ],
  },
  {
    abbr: "DAL", name: "Mavericks",
    players: [
      { name: "Luka Doncic", salary: 46.0 },
      { name: "Kyrie Irving", salary: 41.0 },
      { name: "Klay Thompson", salary: 15.7 },
      { name: "P.J. Washington", salary: 14.1 },
      { name: "Daniel Gafford", salary: 13.4 },
      { name: "Dereck Lively II", salary: 5.0 },
    ],
  },
  {
    abbr: "MIN", name: "Timberwolves",
    players: [
      { name: "Anthony Edwards", salary: 42.2 },
      { name: "Julius Randle", salary: 33.1 },
      { name: "Rudy Gobert", salary: 43.8 },
      { name: "Jaden McDaniels", salary: 22.6 },
      { name: "Mike Conley", salary: 9.9 },
      { name: "Naz Reid", salary: 14.0 },
    ],
  },
  {
    abbr: "NYK", name: "Knicks",
    players: [
      { name: "Jalen Brunson", salary: 24.9 },
      { name: "Karl-Anthony Towns", salary: 57.1 },
      { name: "OG Anunoby", salary: 36.6 },
      { name: "Mikal Bridges", salary: 23.3 },
      { name: "Josh Hart", salary: 18.1 },
      { name: "Mitchell Robinson", salary: 14.3 },
    ],
  },
];

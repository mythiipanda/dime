export type AwardCandidate = {
  player: string;
  team: string;
  line: string;
  odds: string;
  move: number;
};

export type AwardTab = { key: string; label: string; candidates: AwardCandidate[] };

export const awardTabs: AwardTab[] = [
  {
    key: "mvp", label: "MVP",
    candidates: [
      { player: "Nikola Jokic", team: "DEN", line: "29.1p · 12.8r · 10.2a", odds: "+180", move: -40 },
      { player: "Shai Gilgeous-Alexander", team: "OKC", line: "31.4p · 6.1a · 2.0s", odds: "+220", move: -25 },
      { player: "Luka Doncic", team: "DAL", line: "30.8p · 9.4r · 9.1a", odds: "+450", move: 60 },
      { player: "Jayson Tatum", team: "BOS", line: "28.6p · 8.9r · 5.4a", odds: "+800", move: 120 },
      { player: "Giannis Antetokounmpo", team: "MIL", line: "29.9p · 11.2r · 6.0a", odds: "+1000", move: -50 },
      { player: "Anthony Edwards", team: "MIN", line: "27.9p · 5.8r · 5.1a", odds: "+1400", move: 200 },
    ],
  },
  {
    key: "dpoy", label: "DPOY",
    candidates: [
      { player: "Victor Wembanyama", team: "SA", line: "3.8b · 11.4r", odds: "+150", move: -60 },
      { player: "Rudy Gobert", team: "MIN", line: "2.4b · 12.1r", odds: "+500", move: 40 },
      { player: "Chet Holmgren", team: "OKC", line: "2.9b · 9.8r", odds: "+600", move: -80 },
      { player: "Bam Adebayo", team: "MIA", line: "1.8b · 10.2r", odds: "+900", move: 150 },
      { player: "OG Anunoby", team: "NYK", line: "1.9s · 5.6r", odds: "+1200", move: -100 },
      { player: "Luguentz Dort", team: "OKC", line: "1.6s · 4.4r", odds: "+1600", move: 0 },
    ],
  },
  {
    key: "mip", label: "MIP",
    candidates: [
      { player: "Jalen Williams", team: "OKC", line: "22.4p · up 5.1", odds: "+400", move: -120 },
      { player: "Tyrese Maxey", team: "PHI", line: "26.8p · up 4.8", odds: "+550", move: 30 },
      { player: "Christian Braun", team: "DEN", line: "14.2p · up 6.9", odds: "+700", move: -200 },
      { player: "Amen Thompson", team: "HOU", line: "16.9p · up 5.5", odds: "+900", move: 90 },
      { player: "Brandin Podziemski", team: "GSW", line: "13.8p · up 6.2", odds: "+1100", move: -40 },
    ],
  },
  {
    key: "roy", label: "ROY",
    candidates: [
      { player: "Cooper Flagg", team: "DAL", line: "19.2p · 7.8r", odds: "+250", move: -80 },
      { player: "Dylan Harper", team: "SA", line: "17.5p · 5.2a", odds: "+350", move: 40 },
      { player: "Ace Bailey", team: "UTA", line: "16.8p · 6.1r", odds: "+600", move: -30 },
      { player: "VJ Edgecombe", team: "PHI", line: "15.4p · 4.9r", odds: "+800", move: 110 },
      { player: "Kon Knueppel", team: "CHA", line: "14.1p · 5.5r · 3.8a", odds: "+1200", move: -150 },
      { player: "Tre Johnson", team: "WAS", line: "15.9p · 3.2r", odds: "+1600", move: 200 },
    ],
  },
  {
    key: "6moy", label: "6MOY",
    candidates: [
      { player: "Payton Pritchard", team: "BOS", line: "16.2p · 47% 3pt", odds: "+300", move: -90 },
      { player: "Naz Reid", team: "MIN", line: "14.8p · 6.9r", odds: "+450", move: 20 },
      { player: "Malik Beasley", team: "DET", line: "15.9p · 42% 3pt", odds: "+600", move: -60 },
      { player: "Ty Jerome", team: "CLE", line: "13.4p · 5.1a", odds: "+750", move: 140 },
      { player: "Alex Caruso", team: "OKC", line: "9.8p · 2.1s", odds: "+1000", move: -40 },
      { player: "Bennedict Mathurin", team: "IND", line: "15.2p · 4.8r", odds: "+1200", move: 80 },
    ],
  },
];

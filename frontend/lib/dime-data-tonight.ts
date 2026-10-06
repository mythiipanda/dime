export type Form = ("W" | "L")[];

export type TonightGame = {
  id: string;
  away: string;
  awayName: string;
  awayRecord: string;
  home: string;
  homeName: string;
  homeRecord: string;
  time: string;
  network: string;
  spread: string;
  total: string;
  injuries: string[];
  homeWinProb: number;
  awayForm: Form;
  homeForm: Form;
};

export const tonightLabel = "Tue, Oct 6";

export const tonightGames: TonightGame[] = [
  {
    id: "mil-phi",
    away: "MIL", awayName: "Bucks", awayRecord: "2-2",
    home: "PHI", homeName: "76ers", homeRecord: "1-3",
    time: "7:00p", network: "ESPN",
    spread: "MIL -5.5", total: "O/U 219.0",
    injuries: ["Embiid out (knee)"],
    homeWinProb: 30,
    awayForm: ["W", "L", "W", "L", "W", "W", "L", "W", "L", "W"],
    homeForm: ["L", "L", "W", "L", "L", "W", "L", "W", "L", "L"],
  },
  {
    id: "cle-orl",
    away: "CLE", awayName: "Cavaliers", awayRecord: "4-0",
    home: "ORL", homeName: "Magic", homeRecord: "2-2",
    time: "7:00p", network: "",
    spread: "CLE -4.5", total: "O/U 218.5",
    injuries: [],
    homeWinProb: 34,
    awayForm: ["W", "W", "W", "W", "W", "L", "W", "W", "W", "L"],
    homeForm: ["W", "L", "W", "L", "W", "L", "W", "W", "L", "W"],
  },
  {
    id: "bos-nyk",
    away: "BOS", awayName: "Celtics", awayRecord: "3-1",
    home: "NYK", homeName: "Knicks", homeRecord: "2-2",
    time: "7:30p", network: "TNT",
    spread: "BOS -3.5", total: "O/U 224.5",
    injuries: ["Tatum questionable (ankle)", "Brunson probable (wrist)"],
    homeWinProb: 41,
    awayForm: ["W", "W", "W", "L", "W", "W", "L", "W", "W", "W"],
    homeForm: ["W", "L", "W", "W", "L", "W", "L", "W", "L", "W"],
  },
  {
    id: "dal-okc",
    away: "DAL", awayName: "Mavericks", awayRecord: "3-2",
    home: "OKC", homeName: "Thunder", homeRecord: "4-0",
    time: "8:00p", network: "ESPN",
    spread: "OKC -7.5", total: "O/U 233.5",
    injuries: [],
    homeWinProb: 74,
    awayForm: ["W", "W", "L", "W", "L", "W", "W", "L", "W", "W"],
    homeForm: ["W", "W", "W", "W", "W", "W", "L", "W", "W", "W"],
  },
  {
    id: "min-mem",
    away: "MIN", awayName: "Timberwolves", awayRecord: "2-2",
    home: "MEM", homeName: "Grizzlies", homeRecord: "3-1",
    time: "8:30p", network: "",
    spread: "MIN -2.0", total: "O/U 221.5",
    injuries: ["Morant questionable (shoulder)"],
    homeWinProb: 44,
    awayForm: ["L", "W", "L", "W", "W", "L", "W", "L", "W", "W"],
    homeForm: ["W", "W", "W", "L", "W", "L", "W", "W", "L", "W"],
  },
  {
    id: "den-phx",
    away: "DEN", awayName: "Nuggets", awayRecord: "3-1",
    home: "PHX", homeName: "Suns", homeRecord: "2-3",
    time: "9:00p", network: "TNT",
    spread: "DEN -1.5", total: "O/U 231.0",
    injuries: ["Durant probable (calf)"],
    homeWinProb: 46,
    awayForm: ["W", "W", "L", "W", "W", "W", "L", "W", "W", "L"],
    homeForm: ["L", "W", "L", "W", "L", "L", "W", "L", "W", "W"],
  },
  {
    id: "lal-gsw",
    away: "LAL", awayName: "Lakers", awayRecord: "2-2",
    home: "GSW", homeName: "Warriors", homeRecord: "3-2",
    time: "10:30p", network: "TNT",
    spread: "GSW -2.5", total: "O/U 228.5",
    injuries: ["Curry probable (thumb)"],
    homeWinProb: 57,
    awayForm: ["W", "L", "W", "L", "W", "L", "W", "W", "L", "W"],
    homeForm: ["W", "W", "L", "W", "L", "W", "W", "L", "W", "W"],
  },
];

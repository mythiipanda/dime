






export const TEAM_IDS: Record<string, number> = {
  ATL: 1610612737,
  BOS: 1610612738,
  CLE: 1610612739,
  NOP: 1610612740,
  CHI: 1610612741,
  DAL: 1610612742,
  DEN: 1610612743,
  GSW: 1610612744,
  HOU: 1610612745,
  LAC: 1610612746,
  LAL: 1610612747,
  MIA: 1610612748,
  MIL: 1610612749,
  MIN: 1610612750,
  BKN: 1610612751,
  NYK: 1610612752,
  ORL: 1610612753,
  IND: 1610612754,
  PHI: 1610612755,
  PHX: 1610612756,
  POR: 1610612757,
  SAC: 1610612758,
  SAS: 1610612759,
  OKC: 1610612760,
  TOR: 1610612761,
  UTA: 1610612762,
  MEM: 1610612763,
  WAS: 1610612764,
  DET: 1610612765,
  CHA: 1610612766,
};



export function abbrForTeamId(id: number | string): string | null {
  const n = typeof id === "string" ? Number(id) : id;
  if (!Number.isFinite(n)) return null;
  for (const [abbr, teamId] of Object.entries(TEAM_IDS)) {
    if (teamId === n) return abbr;
  }
  return null;
}



export function isTeamAbbr(v: string): boolean {
  return Object.hasOwn(TEAM_IDS, String(v).trim().toUpperCase());
}

export const TEAM_ABBR_BY_FULL_NAME: Record<string, string> = {
  "Atlanta Hawks": "ATL",
  "Boston Celtics": "BOS",
  "Brooklyn Nets": "BKN",
  "Charlotte Hornets": "CHA",
  "Chicago Bulls": "CHI",
  "Cleveland Cavaliers": "CLE",
  "Dallas Mavericks": "DAL",
  "Denver Nuggets": "DEN",
  "Detroit Pistons": "DET",
  "Golden State Warriors": "GSW",
  "Houston Rockets": "HOU",
  "Indiana Pacers": "IND",
  "Los Angeles Clippers": "LAC",
  "Los Angeles Lakers": "LAL",
  "Memphis Grizzlies": "MEM",
  "Miami Heat": "MIA",
  "Milwaukee Bucks": "MIL",
  "Minnesota Timberwolves": "MIN",
  "New Orleans Pelicans": "NOP",
  "New York Knicks": "NYK",
  "Oklahoma City Thunder": "OKC",
  "Orlando Magic": "ORL",
  "Philadelphia 76ers": "PHI",
  "Phoenix Suns": "PHX",
  "Portland Trail Blazers": "POR",
  "Sacramento Kings": "SAC",
  "San Antonio Spurs": "SAS",
  "Toronto Raptors": "TOR",
  "Utah Jazz": "UTA",
  "Washington Wizards": "WAS",
};

const FULL_NAME_LOOKUP = new Map<string, string>(
  Object.entries(TEAM_ABBR_BY_FULL_NAME).map(([name, abbr]) => [
    name.trim().replace(/\s+/g, " ").toLowerCase(),
    abbr,
  ]),
);

export function abbrForTeamFullName(name: string): string | null {
  if (typeof name !== "string") return null;
  return FULL_NAME_LOOKUP.get(name.trim().replace(/\s+/g, " ").toLowerCase()) ?? null;
}

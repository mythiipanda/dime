export type WarehouseColumn = { name: string; type: string };

export type WarehouseTable = {
  name: string;
  rows: number;
  freshness: string;
  description: string;
  columns: WarehouseColumn[];
  sample: string[][];
};

export const warehouseTables: WarehouseTable[] = [
  {
    name: "silver_boxscores",
    rows: 330485,
    freshness: "2h ago",
    description: "Player box scores for every game since 2015.",
    columns: [
      { name: "game_id", type: "string" },
      { name: "season", type: "string" },
      { name: "player_id", type: "string" },
      { name: "team", type: "string" },
      { name: "minutes", type: "double" },
      { name: "pts", type: "int" },
      { name: "reb", type: "int" },
      { name: "ast", type: "int" },
      { name: "stl", type: "int" },
      { name: "blk", type: "int" },
      { name: "tov", type: "int" },
      { name: "fgm", type: "int" },
      { name: "fga", type: "int" },
    ],
    sample: [
      ["0022400123", "2024-25", "1628983", "OKC", "34.2", "31", "5", "6", "2", "1", "3", "11", "21"],
      ["0022400123", "2024-25", "1627749", "DAL", "36.8", "34", "9", "11", "1", "0", "4", "12", "24"],
      ["0022400124", "2024-25", "203999", "DEN", "35.1", "28", "12", "10", "2", "1", "2", "10", "18"],
      ["0022400124", "2024-25", "1628369", "DEN", "33.4", "26", "7", "5", "1", "2", "3", "9", "17"],
      ["0022400125", "2024-25", "1630162", "MIN", "37.9", "33", "4", "5", "3", "0", "2", "12", "23"],
    ],
  },
  {
    name: "silver_schedule",
    rows: 12960,
    freshness: "2h ago",
    description: "Game dates, matchups, and final scores.",
    columns: [
      { name: "game_id", type: "string" },
      { name: "season", type: "string" },
      { name: "game_date", type: "date" },
      { name: "away_team", type: "string" },
      { name: "home_team", type: "string" },
      { name: "away_pts", type: "int" },
      { name: "home_pts", type: "int" },
    ],
    sample: [
      ["0022400123", "2024-25", "2025-04-13", "DAL", "OKC", "111", "118"],
      ["0022400124", "2024-25", "2025-04-13", "MIN", "DEN", "104", "109"],
      ["0022400125", "2024-25", "2025-04-13", "LAL", "GSW", "122", "119"],
      ["0022400126", "2024-25", "2025-04-12", "BOS", "NYK", "108", "105"],
      ["0022400127", "2024-25", "2025-04-12", "MIL", "PHI", "121", "114"],
    ],
  },
  {
    name: "silver_lineups",
    rows: 48211,
    freshness: "6h ago",
    description: "Lineup stints with on/off splits per game.",
    columns: [
      { name: "game_id", type: "string" },
      { name: "team", type: "string" },
      { name: "lineup_id", type: "string" },
      { name: "minutes", type: "double" },
      { name: "off_rtg", type: "double" },
      { name: "def_rtg", type: "double" },
      { name: "net_rtg", type: "double" },
    ],
    sample: [
      ["0022400123", "OKC", "okc_0142", "14.2", "121.4", "104.8", "16.6"],
      ["0022400123", "OKC", "okc_0891", "9.6", "114.2", "109.3", "4.9"],
      ["0022400123", "DAL", "dal_0330", "16.1", "118.9", "112.4", "6.5"],
      ["0022400124", "DEN", "den_0117", "18.3", "124.1", "108.2", "15.9"],
      ["0022400124", "MIN", "min_0455", "12.8", "110.6", "114.9", "-4.3"],
    ],
  },
  {
    name: "silver_players",
    rows: 5842,
    freshness: "1d ago",
    description: "Player bios, positions, and contract years.",
    columns: [
      { name: "player_id", type: "string" },
      { name: "name", type: "string" },
      { name: "team", type: "string" },
      { name: "position", type: "string" },
      { name: "height_in", type: "int" },
      { name: "draft_year", type: "int" },
    ],
    sample: [
      ["1628983", "Shai Gilgeous-Alexander", "OKC", "G", "78", "2018"],
      ["1627749", "Luka Dončić", "DAL", "G", "79", "2018"],
      ["203999", "Nikola Jokić", "DEN", "C", "83", "2014"],
      ["1630162", "Anthony Edwards", "MIN", "G", "76", "2020"],
      ["1546716", "Stephen Curry", "GSW", "G", "74", "2009"],
    ],
  },
  {
    name: "silver_odds",
    rows: 96340,
    freshness: "3h ago",
    description: "Historical spreads, totals, and moneylines.",
    columns: [
      { name: "game_id", type: "string" },
      { name: "book", type: "string" },
      { name: "spread", type: "double" },
      { name: "total", type: "double" },
      { name: "captured_at", type: "timestamp" },
    ],
    sample: [
      ["0022400123", "pinnacle", "-7.5", "233.5", "2025-04-13 18:02:11"],
      ["0022400123", "draftkings", "-7.0", "233.0", "2025-04-13 18:04:52"],
      ["0022400124", "pinnacle", "-3.0", "221.5", "2025-04-13 17:58:03"],
      ["0022400125", "pinnacle", "2.5", "228.5", "2025-04-13 18:11:44"],
      ["0022400126", "draftkings", "-3.5", "224.5", "2025-04-12 18:20:19"],
    ],
  },
  {
    name: "silver_tracking",
    rows: 1204553,
    freshness: "1d ago",
    description: "Shot locations and movement events.",
    columns: [
      { name: "game_id", type: "string" },
      { name: "player_id", type: "string" },
      { name: "x", type: "double" },
      { name: "y", type: "double" },
      { name: "made", type: "boolean" },
      { name: "shot_type", type: "string" },
    ],
    sample: [
      ["0022400123", "1628983", "2.1", "8.4", "true", "pullup"],
      ["0022400123", "1628983", "-14.2", "22.8", "false", "catch_shoot"],
      ["0022400123", "1627749", "0.8", "3.2", "true", "drive"],
      ["0022400124", "203999", "-4.5", "12.1", "true", "post"],
      ["0022400124", "1630162", "18.9", "20.4", "false", "pullup"],
    ],
  },
  {
    name: "dim_teams",
    rows: 30,
    freshness: "7d ago",
    description: "Team names, abbreviations, and conferences.",
    columns: [
      { name: "team", type: "string" },
      { name: "name", type: "string" },
      { name: "conference", type: "string" },
    ],
    sample: [
      ["OKC", "Oklahoma City Thunder", "West"],
      ["DAL", "Dallas Mavericks", "West"],
      ["DEN", "Denver Nuggets", "West"],
      ["BOS", "Boston Celtics", "East"],
      ["NYK", "New York Knicks", "East"],
    ],
  },
];

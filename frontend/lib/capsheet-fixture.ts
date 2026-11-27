export type CapYear = {
  season: string;
  salary: number | null;
  option: "player" | "team" | null;
  guaranteed: boolean;
};

export type CapPlayer = {
  player: string;
  player_id: number;
  contract_type: string;
  years: CapYear[];
};

export type CapLines = {
  cap: number;
  tax: number;
  apron1: number;
  apron2: number;
  projected: boolean;
};

export type CapSheetResponse = {
  ok: boolean;
  team: string;
  season: string;
  lines: Record<string, CapLines>;
  players: CapPlayer[];
  totals: Record<string, {
    committed: number;
    pending_option: number;
    dead_money: number;
    cap_holds: number;
    incomplete_roster_charges: number;
    payroll: number;
  }>;
  state: {
    over_tax: boolean;
    over_apron1: boolean;
    over_apron2: boolean;
    room_under_apron2: number;
  };
  meta: { source: string; salary_date: string; season: string };
  error?: string;
};

export type ScenarioMove = {
  kind: "signing" | "trade_in" | "trade_out" | "waive" | "option_decision";
  label?: string;
  amount?: number;
  player?: string;
  season?: string;
  exercise?: boolean;
  stretch?: boolean;
  from?: string;
};

export type ScenarioResponse = {
  ok: boolean;
  steps: { step: number; kind: string; detail: string; delta: number; payroll: number }[];
  pay_after: number;
  state: { over_tax: boolean; over_apron1: boolean; over_apron2: boolean; room_under_apron2?: number };
  restrictions: { threshold: string; status: string; rule: string }[];
  roster_issues: string[];
  errors: string[];
};

const SEASONS = ["2026-27", "2027-28", "2028-29", "2029-30", "2030-31", "2031-32"];

function linesFor(index: number): CapLines {
  const base = { cap: 164961000, tax: 200428000, apron1: 209015000, apron2: 221686000 };
  const grown = Object.fromEntries(
    Object.entries(base).map(([k, v]) => [k, Math.round(v * Math.pow(1.07, index))]),
  ) as unknown as CapLines;
  return { ...grown, projected: index > 1 };
}

function player(
  player: string,
  player_id: number,
  contract_type: string,
  base: number,
  options: ("player" | "team" | null)[],
): CapPlayer {
  return {
    player,
    player_id,
    contract_type,
    years: SEASONS.map((season, i) => ({
      season,
      salary: i < 5 ? Math.round(base * Math.pow(1.08, i)) : null,
      option: options[i] ?? null,
      guaranteed: i < 3,
    })),
  };
}

export const capSheetFixture: CapSheetResponse = {
  ok: true,
  team: "BOS",
  season: "2026-27",
  lines: Object.fromEntries(SEASONS.map((s, i) => [s, linesFor(i)])),
  players: [
    player("Jayson Tatum", 1628369, "Supermax Extension", 54126450, [null, null, "player", null, null, null]),
    player("Jaylen Brown", 1627759, "Supermax Extension", 53142264, [null, null, null, "player", null, null]),
    player("Derrick White", 1628401, "Veteran Extension", 28100000, [null, null, null, null, null, null]),
    player("Sam Hauser", 1630573, "Veteran Extension", 10044772, [null, null, null, "team", null, null]),
    player("Payton Pritchard", 1630202, "Rookie Extension", 7232014, [null, null, null, null, null, null]),
    player("Neemias Queta", 1629674, "Minimum", 2524525, [null, "team", null, null, null, null]),
  ],
  totals: Object.fromEntries(
    SEASONS.map((season, i) => [
      season,
      {
        committed: 198000000 + i * 8400000,
        pending_option: i >= 2 ? 62786682 : 0,
        dead_money: i === 0 ? 0 : 0,
        cap_holds: i === 1 ? 4100000 : 0,
        incomplete_roster_charges: 0,
        payroll: 198000000 + i * 8400000,
      },
    ]),
  ),
  state: { over_tax: true, over_apron1: false, over_apron2: false, room_under_apron2: 23686000 },
  meta: { source: "basketball-reference contracts", salary_date: "2026-11-20", season: "2026-27" },
};

export const capScenarioFixture: ScenarioResponse = {
  ok: true,
  steps: [
    { step: 0, kind: "payroll", detail: "BOS committed", delta: 0, payroll: 198000000 },
    { step: 1, kind: "signing", detail: "Free Agent X", delta: 12000000, payroll: 210000000 },
  ],
  pay_after: 210000000,
  state: { over_tax: true, over_apron1: true, over_apron2: false, room_under_apron2: 11686000 },
  restrictions: [
    { threshold: "first apron", status: "trigger", rule: "Signing a free agent to more than the taxpayer midlevel hard-caps the team at the first apron for the rest of the season." },
    { threshold: "first apron", status: "active", rule: "Cannot take back more salary in a trade than is sent out (no expanded matching)." },
    { threshold: "second apron", status: "inactive", rule: "First-round pick seven years out becomes tradeable again once below the second apron." },
  ],
  roster_issues: [],
  errors: [],
};

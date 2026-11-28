export type CapYear = {
  season: string;
  salary: number | null;
  option: "player" | "team" | null;
  guaranteed: boolean | null;
  counts_as_standard?: boolean;
};

export type CapPlayer = {
  player: string;
  player_id: number | null;
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

export type CapMoneyDetail = {
  player: string;
  team: string;
  salary: number | null;
  amount_unknown?: boolean;
  basis?: string;
};

const DEAD_MONEY_BASIS_WORDS: Record<string, string> = {
  waived_standard_contract_before_two_way:
    "waived standard contract before a two-way signing — the dead amount is the protected guarantee",
  waived_standard_contract_before_two_way_protection_unknown:
    "waived standard contract before a two-way signing — the protected amount is unknown",
  waived_standard_contract_before_same_team_resign_protection_unknown:
    "waived, then re-signed by the same team — the guaranteed amount protected is unknown",
  row_kind_unknown_protection_unknown:
    "contract status unresolved — the protected amount is unknown",
};

export function deadMoneyBasisWords(basis: string | undefined): string {
  if (!basis) return "the protected amount is unknown";
  return DEAD_MONEY_BASIS_WORDS[basis] ?? "the protected amount is unknown";
}

export type CapSheetResponse = {
  ok: boolean;
  team: string;
  season: string;
  lines: Record<string, CapLines>;
  players: CapPlayer[];
  totals: Record<string, {
    committed: number;
    roster_payroll: number;
    pending_option: number;
    dead_money: number;
    dead_money_detail: CapMoneyDetail[];
    cap_holds: number;
    incomplete_roster_charges: number;
    payroll: number;
    component_availability?: {
      committed?: boolean;
      roster_payroll?: boolean;
      pending_option?: boolean;
      dead_money?: boolean;
      cap_holds?: boolean;
      incomplete_roster_charges?: boolean;
    };
  }>;
  dead_money_detail?: CapMoneyDetail[];
  dead_money_unit?: string;
  state: {
    over_tax: boolean;
    over_apron1: boolean;
    over_apron2: boolean;
    room_under_apron2: number;
  };
  meta: { source: string; salary_date: string; season: string };
  error?: string;
};

export type SigningExceptionState = {
  ntmle_used?: number;
  tmle_used?: number;
  bae_used?: number;
  room_used?: number;
  bae_used_prior_cap_year?: boolean;
  operating_mode?: string;
};

export type ScenarioMove = {
  kind: "signing" | "trade_in" | "trade_out" | "waive" | "option_decision" | "extend" | "renounce";
  label?: string;
  amount?: number;
  player?: string;
  season?: string;
  exercise?: boolean;
  stretch?: boolean;
  years?: number;
  mechanism?: string;
  unlikely_bonus?: number;
  years_of_service?: number;
  prior_salary?: number;
  signing_date?: string;
  prior_team?: string;
  free_agent_status?: string;
  replaces_cap_hold?: boolean;
  salary_schedule?: number[];
  exception_state?: SigningExceptionState;
  from?: string;
  exception?: "cap_room" | "mle" | "bae" | "minimum" | "bird";
  first_year_amount?: number;
  group?: string;
};

export type ScenarioResponse = {
  ok: boolean;
  season: string;
  steps: {
    step: number;
    kind: string;
    detail: string;
    delta: number;
    payroll: number;
    player?: string;
    dead_cap?: number;
    guaranteed?: number;
    stretch_years?: number;
    stretched_amount?: number;
    stretched_dead_cap?: number;
    waiver_window?: "pre_sep1" | "post_sep1";
    waiver_date?: string | null;
    waiver_date_defaulted?: boolean;
    estimate_basis?: string;
  }[];
  pay_after: number;
  state: { over_tax: boolean; over_apron1: boolean; over_apron2: boolean; room_under_apron2?: number };
  restrictions: { threshold: string; status: string; rule: string }[];
  roster_issues: string[];
  lines_projected?: boolean;
  hard_cap?: string;
  active_hard_caps?: string[];
  hard_cap_triggers?: { transaction: string; move_index: number; apron: string; status: "active" | "prohibited" }[];
  would_be_hard_cap_triggers?: { transaction: string; move_index: number; apron: string; status: "active" | "prohibited" }[];
  signing_exception_state?: SigningExceptionState;
  includes_illegal_moves?: boolean;
  illegal_move_indices?: number[];
  includes_unvalidated_moves?: boolean;
  unvalidated_move_indices?: number[];
  errors: (string | { move: string; error: string })[];
  meta?: {
    waiver_basis?: string;
    waiver_timing?: { window: "pre_sep1" | "post_sep1"; date: string | null; defaulted: boolean };
    illegal_move_state_disclosure?: string;
    sign_and_trade_scope?: string;
  };
};

export function shortSeason(season: string): string {
  return `\u2019${season.slice(5)}`;
}

export function moneyMillions(value: number | null | undefined): string {
  if (value == null) return "\u2013";
  const sign = value < 0 ? "\u2212" : "";
  return `${sign}$${(Math.abs(value) / 1e6).toFixed(1)}M`;
}

export function describeScenarioMove(move: ScenarioMove): string {
  switch (move.kind) {
    case "signing":
      return `sign ${move.label} (${moneyMillions(move.amount)})`;
    case "option_decision":
      return `${move.exercise ? "exercise" : "decline"} ${move.player} ${shortSeason(move.season ?? "")} option`;
    case "waive":
      return `waive ${move.player}${move.stretch ? " (stretch)" : ""}`;
    case "trade_out":
      return `trade out ${move.player}`;
    case "trade_in":
      return `trade in ${move.player}`;
    default:
      return `${move.kind} ${move.player ?? move.label ?? ""}`.trim();
  }
}

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
  player_id: number | null,
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
    player("Camp Signing One", null, "Exhibit 10", 1275000, [null, null, null, null, null, null]),
    player("Camp Signing Two", null, "Exhibit 10", 1275000, [null, null, null, null, null, null]),
    player("Neemias Queta", 1629674, "Minimum", 2524525, [null, "team", null, null, null, null]),
    {
      player: "Two-way Example",
      player_id: null,
      contract_type: "Two-way",
      years: SEASONS.map((season, i) => ({
        season,
        salary: i < 2 ? 578577 : null,
        option: null,
        guaranteed: i < 2,
        counts_as_standard: i !== 0,
      })),
    },
  ],
  totals: Object.fromEntries(
    SEASONS.map((season, i) => {
      const rosterPayroll = 189337323 + i * 8400000;
      const deadMoney = [8662677, 7660317, 1002360, 0, 0, 0][i];
      const deadDetail = deadMoney > 0
        ? [{ player: "Dead-money example", team: "BOS", salary: deadMoney },
           ...(i === 0 ? [{ player: "Resigned Example", team: "BOS", salary: null, amount_unknown: true, basis: "waived_standard_contract_before_same_team_resign_protection_unknown" } as const] : [])]
        : [];
      const committed = rosterPayroll + deadMoney;
      const capHolds = i === 1 ? 4100000 : 0;
      const rosterCharges = i === 1 ? 1234567 : 0;
      const capRoomCovered = i === 1;
      return [
        season,
        {
          committed,
          roster_payroll: rosterPayroll,
          pending_option: i === 1 ? 2726487 : i >= 2 ? 62786682 : 0,
          dead_money: deadMoney,
          dead_money_detail: deadDetail,
          cap_holds: capHolds,
          incomplete_roster_charges: rosterCharges,
          payroll: committed + capHolds + rosterCharges,
          component_availability: {
            committed: true,
            roster_payroll: true,
            pending_option: true,
            dead_money: true,
            cap_holds: capRoomCovered,
            incomplete_roster_charges: capRoomCovered,
          },
        },
      ];
    }),
  ),
  dead_money_detail: [{ player: "Dead-money example", team: "BOS", salary: 8662677 }],
  dead_money_unit: "usd_dollars",
  state: { over_tax: true, over_apron1: false, over_apron2: false, room_under_apron2: 23686000 },
  meta: { source: "basketball-reference contracts", salary_date: "2026-11-20", season: "2026-27" },
};

export const capScenarioFixture: ScenarioResponse = {
  ok: true,
  season: "2026-27",
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

import { Type } from "typebox";

export const OBJECT_KINDS = ["cap_scenario", "trade_scenario", "thread_grant", "board", "artifact_ref"] as const;
export type ObjectKind = (typeof OBJECT_KINDS)[number];

export const signingExceptionStateSchema = Type.Object({
    ntmle_used: Type.Optional(Type.Number()),
    tmle_used: Type.Optional(Type.Number()),
    bae_used: Type.Optional(Type.Number()),
    room_used: Type.Optional(Type.Number()),
    bae_used_prior_cap_year: Type.Optional(Type.Boolean()),
    operating_mode: Type.Optional(Type.String())
}, { additionalProperties: false });

export const capScenarioMoveSchema = Type.Object({
    kind: Type.String(),
    label: Type.Optional(Type.String()),
    amount: Type.Optional(Type.Number()),
    player: Type.Optional(Type.String()),
    exercise: Type.Optional(Type.Boolean()),
    stretch: Type.Optional(Type.Boolean()),
    season: Type.Optional(Type.String()),
    exception: Type.Optional(Type.String({ maxLength: 24 })),
    years: Type.Optional(Type.Number()),
    first_year_amount: Type.Optional(Type.Number()),
    mechanism: Type.Optional(Type.String()),
    unlikely_bonus: Type.Optional(Type.Number()),
    years_of_service: Type.Optional(Type.Number()),
    prior_salary: Type.Optional(Type.Number()),
    signing_date: Type.Optional(Type.String()),
    prior_team: Type.Optional(Type.String()),
    free_agent_status: Type.Optional(Type.String()),
    replaces_cap_hold: Type.Optional(Type.Boolean()),
    salary_schedule: Type.Optional(Type.Array(Type.Number(), { maxItems: 8 })),
    exception_state: Type.Optional(signingExceptionStateSchema),
    group: Type.Optional(Type.String({ maxLength: 48 }))
}, { additionalProperties: false });

export const capScenarioPayloadSchema = Type.Object({
    team: Type.String({ minLength: 1, maxLength: 12 }),
    season: Type.String({ minLength: 1, maxLength: 12 }),
    waiver_date: Type.Optional(Type.String({ maxLength: 16 })),
    exception_state: Type.Optional(signingExceptionStateSchema),
    moves: Type.Array(capScenarioMoveSchema, { minItems: 1, maxItems: 40 }),
    groups: Type.Optional(Type.Record(Type.String(), Type.Object({
        partner: Type.Optional(Type.String({ maxLength: 120 })),
        verdict: Type.Optional(Type.Union([Type.Boolean(), Type.Null()])),
        evaluated_at: Type.Optional(Type.String({ maxLength: 40 }))
    }, { additionalProperties: false }), { maxProperties: 20 })),
    tpes: Type.Optional(Type.Array(Type.Object({
        team: Type.String({ minLength: 2, maxLength: 4 }),
        amount: Type.Integer({ minimum: 1 }),
        kind: Type.Optional(Type.String({ maxLength: 24 })),
        origin_year: Type.Optional(Type.Integer({ minimum: 2000, maximum: 2100 })),
        exactness: Type.Optional(Type.String({ maxLength: 32 }))
    }, { additionalProperties: false }), { maxItems: 30 }))
}, { additionalProperties: false });

export const tradeScenarioPayloadSchema = Type.Object({
    legs: Type.Array(Type.Object({
        from: Type.String({ minLength: 2, maxLength: 4 }),
        to: Type.String({ minLength: 2, maxLength: 4 }),
        players: Type.Optional(Type.Union([Type.String({ maxLength: 600 }), Type.Array(Type.String({ minLength: 1, maxLength: 120 }), { maxItems: 12 })])),
        picks: Type.Optional(Type.Array(Type.Record(Type.String(), Type.Unknown()), { maxItems: 12 }))
    }, { additionalProperties: false }), { minItems: 1, maxItems: 8 }),
    season: Type.String({ minLength: 1, maxLength: 12 }),
    tpes: Type.Optional(Type.Array(Type.Object({
        team: Type.String({ minLength: 2, maxLength: 4 }),
        amount: Type.Integer({ minimum: 1 }),
        kind: Type.Optional(Type.String({ maxLength: 24 })),
        origin_year: Type.Optional(Type.Integer({ minimum: 2000, maximum: 2100 })),
        exactness: Type.Optional(Type.String({ maxLength: 32 }))
    }, { additionalProperties: false }), { maxItems: 30 }))
}, { additionalProperties: false });

export const artifactRefPayloadSchema = Type.Object({
    run_id: Type.String({ minLength: 1, maxLength: 60 }),
    artifact_index: Type.Integer({ minimum: 0 }),
    thread: Type.String({ minLength: 1, maxLength: 120 }),
    owner: Type.String({ minLength: 1, maxLength: 80 })
}, { additionalProperties: false });

export const threadGrantPayloadSchema = Type.Object({
    thread: Type.String({ minLength: 1, maxLength: 120 }),
    owner: Type.String({ minLength: 1, maxLength: 80 }),
    granted_before: Type.String({ minLength: 10, maxLength: 40 })
}, { additionalProperties: false });

export const boardPinSchema = Type.Object({
    kind: Type.Union([Type.Literal("cap_scenario"), Type.Literal("trade_scenario"), Type.Literal("artifact_ref")]),
    object_id: Type.String({ minLength: 1, maxLength: 120 }),
    note: Type.Optional(Type.String({ maxLength: 120 }))
}, { additionalProperties: false });

export const boardPayloadSchema = Type.Object({
    season: Type.String({ minLength: 1, maxLength: 12 }),
    pins: Type.Optional(Type.Array(boardPinSchema, { maxItems: 20 })),
    rows: Type.Array(Type.Object({
        player_id: Type.Integer({ minimum: 1 })
    }, { additionalProperties: false }), { minItems: 1, maxItems: 50 }),
    columns: Type.Array(Type.Object({
        metric_id: Type.String({ minLength: 1, maxLength: 64 })
    }, { additionalProperties: false }), { minItems: 1, maxItems: 30 }),
    template_id: Type.Optional(Type.String({ maxLength: 64 }))
}, { additionalProperties: false });

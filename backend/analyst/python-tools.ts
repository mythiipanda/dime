import { McpClient, StdioTransport, type CallToolResult, type StdioTransportOptions } from "@earendil-works/pi-mcp";
import { randomUUID } from "node:crypto";
import { isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import type { JsonValue } from "@earendil-works/pi-ai";
import { defineTool, type ToolNamespace } from "@earendil-works/pi-coding-agent";

export const ANALYST_TOOL_NAMES = [
    "sql_exec",
    "warehouse_schema",
    "get_rapm",
    "get_impact_rank",
    "get_game_prediction",
    "get_wpa_leaders",
    "get_comps",
    "get_lineup_stats",
    "get_win_prob",
    "get_on_off",
    "get_shot_zones",
    "get_phase_shot_splits",
    "get_four_factors",
    "get_clutch_stats",
    "get_competitive_ratings",
    "get_hustle",
    "get_injuries",
    "get_news_feed",
    "get_team_daily_brief",
    "get_award_results",
    "get_briefing",
    "get_standings",
    "get_rest",
    "get_team_trajectory",
    "get_ratings",
    "get_rookie_leaders",
    "get_cap_ledger",
    "get_leaders",
    "get_lineup_leaders",
    "get_playoffs",
    "get_team_leaders",
    "get_team_compare",
    "get_elo_standings",
    "get_draft_board",
    "get_combine",
    "get_young_player_usage",
    "get_contract_value",
    "get_trade_check",
    "get_trade_value",
    "get_draft_capital",
    "get_trade_partners",
    "get_situational_splits",
    "get_playoff_sim",
    "get_playoff_team_ratings",
    "get_player_risers",
    "get_standings_deep",
    "get_warehouse_freshness",
    "get_finder",
    "get_draft_model",
    "get_leaderboard_deltas",
    "get_player_ratings",
    "get_risers",
    "get_team_four_factors",
    "get_streaks",
    "get_playtype_profile",
    "get_defensive_matchups",
    "get_head_to_head",
    "get_lineup_matchup_matrix",
    "get_transactions",
    "get_wowy",
    "get_shot_compare",
    "get_raptor_history",
    "get_season_series",
    "get_team_game_log",
    "get_zone_deltas",
    "search_shots",
    "get_shot_chart",
    "get_stint_timeline",
    "get_possession_log",
    "get_elo",
    "get_team_shot_zones",
    "get_historical_leaders",
    "get_today",
    "get_morning_briefing",
    "get_tracking_profile",
    "get_rest_advantage",
    "get_rapm_prior",
    "search_game_logs",
    "get_dataset",
    "get_dataset_freshness",
    "get_career_arc",
    "run_python",
    "get_matchup_preview",
    "get_matchup_splits",
    "get_regression_check",
    "get_scout_pack",
    "get_opponent_scout",
    "get_rotation_check",
    "get_injury_impact",
    "get_matchup_brief",
    "get_watchlist",
    "get_games_on_date",
    "get_boxscore",
    "get_award_race",
    "get_last_x",
    "get_player_report",
    "get_team_hub",
    "get_lineups",
    "get_splits",
    "get_recap",
    "get_scouting_report",
    "web_search",
    "web_fetch",
=======
    "get_free_agents",
    "get_prospect",
    "get_roster_fit",
    "get_expectations",
>>>>>>> origin/dev
] as const;

export type PythonToolName = (typeof ANALYST_TOOL_NAMES)[number];

const NAMESPACES: Record<string, ToolNamespace> = {
    player: { name: "player", description: "Player impact, RAPM, on/off, splits, comps, scouting, and availability tools." },
    team: { name: "team", description: "Team ratings, four factors, 5-man lineups, standings, and Elo tools." },
    league: { name: "league", description: "League leaders, awards, draft, playoffs, briefings, and dataset tools." },
    cba: { name: "cba", description: "2023 CBA salary cap ledgers, trade legality checks, contract values, and transactions." },
    spatial: { name: "spatial", description: "Shot zones, shot diets, optical tracking, and Synergy playtype tools." },
    matchup: { name: "matchup", description: "Game predictions, head-to-head matchups, boxscores, rest, and stint logs." },
    web: { name: "web", description: "Public web search and page fetch tools for current external sources." },
};

const TOOL_NAMESPACE_GROUPS: Record<string, readonly PythonToolName[]> = {
    cba: ["get_cap_ledger", "get_contract_value", "get_trade_check", "get_trade_value", "get_draft_capital", "get_trade_partners", "get_transactions"],
    spatial: ["get_shot_zones", "get_shot_compare", "get_team_shot_zones", "get_zone_deltas", "search_shots", "get_tracking_profile", "get_playtype_profile"],
    matchup: ["get_game_prediction", "get_win_prob", "get_defensive_matchups", "get_head_to_head", "get_lineup_matchup_matrix", "get_season_series", "get_rest", "get_rest_advantage", "get_matchup_preview", "get_matchup_splits", "get_matchup_brief", "get_games_on_date", "get_boxscore", "get_possession_log", "get_stint_timeline"],
=======
    cba: ["get_cap_ledger", "get_contract_value", "get_trade_check", "get_trade_partners", "get_trade_value", "get_transactions"],
    spatial: ["get_shot_zones", "get_shot_compare", "get_team_shot_zones", "get_phase_shot_splits", "get_zone_deltas", "search_shots", "get_shot_chart", "get_tracking_profile", "get_playtype_profile"],
    matchup: ["get_game_prediction", "get_win_prob", "get_defensive_matchups", "get_head_to_head", "get_lineup_matchup_matrix", "get_season_series", "get_rest", "get_rest_advantage", "get_matchup_preview", "get_matchup_splits", "get_matchup_brief", "get_opponent_scout", "get_games_on_date", "get_boxscore", "get_possession_log", "get_stint_timeline"],
>>>>>>> origin/dev
    player: ["get_rapm", "get_rapm_prior", "get_impact_rank", "get_raptor_history", "get_comps", "get_on_off", "get_wowy", "get_clutch_stats", "get_hustle", "get_injuries", "get_rookie_leaders", "get_young_player_usage", "get_player_risers", "get_player_ratings", "get_situational_splits", "get_career_arc", "get_last_x", "get_player_report", "get_splits", "get_scouting_report", "get_scout_pack", "get_regression_check", "get_rotation_check", "get_injury_impact", "search_game_logs"],
    team: ["get_lineup_stats", "get_lineup_leaders", "get_lineups", "get_four_factors", "get_team_four_factors", "get_team_trajectory", "get_ratings", "get_team_leaders", "get_team_compare", "get_team_game_log", "get_team_hub", "get_risers", "get_playoff_team_ratings", "get_competitive_ratings", "get_elo", "get_elo_standings", "get_standings", "get_standings_deep"],
    league: ["get_wpa_leaders", "get_award_results", "get_award_race", "get_briefing", "get_morning_briefing", "get_today", "get_leaders", "get_leaderboard_deltas", "get_historical_leaders", "get_playoffs", "get_playoff_sim", "get_draft_board", "get_combine", "get_draft_model", "get_warehouse_freshness", "get_dataset", "get_dataset_freshness", "get_finder", "get_streaks", "get_watchlist", "get_recap"],
    web: ["web_search", "web_fetch"],
=======
    league: ["get_wpa_leaders", "get_award_results", "get_award_race", "get_briefing", "get_morning_briefing", "get_today", "get_leaders", "get_leaderboard_deltas", "get_historical_leaders", "get_playoffs", "get_playoff_sim", "get_draft_board", "get_combine", "get_draft_model", "get_warehouse_freshness", "get_dataset", "get_dataset_freshness", "get_finder", "get_streaks", "get_watchlist", "get_recap", "get_news_feed", "get_team_daily_brief", "get_prospect", "get_free_agents"],
>>>>>>> origin/dev
};

const TOOL_NAMESPACE_MAP = new Map<string, ToolNamespace>(
    Object.entries(TOOL_NAMESPACE_GROUPS).flatMap(([group, names]) =>
        names.map((name) => [name, NAMESPACES[group]] as const)
    )
);

type ToolLiteralTuple<T extends readonly string[]> = { -readonly [K in keyof T]: Type.TLiteral<T[K]> };
function makeToolLiterals<const T extends readonly string[]>(names: T): ToolLiteralTuple<T> {
    return names.map(name => Type.Literal(name)) as unknown as ToolLiteralTuple<T>;
}

export const sourceRecordSchema = Type.Object({
    ref: Type.String(), callId: Type.String(),
    tool: Type.Union(makeToolLiterals(ANALYST_TOOL_NAMES)),
    args: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
    response: Type.Object({
        content: Type.Array(Type.Unknown()),
        structuredContent: Type.Optional(Type.Unknown()), isError: Type.Optional(Type.Boolean())
    }, { additionalProperties: true }),
}, { additionalProperties: false });
export type SourceRecord = Static<typeof sourceRecordSchema>;
export const sourceOutputSchema = Type.Object({ ref: Type.String(), tool: Type.String(), result: Type.Unknown(), evidence: Type.Optional(Type.Record(Type.String(), Type.Unknown())), isError: Type.Boolean() }, { additionalProperties: false });
const objectSchema = Type.Record(Type.String(), Type.Unknown());
export function objectValue(value: unknown) {
    return Value.Check(objectSchema, value) ? value : undefined;
}
function clipText(value: string, limit = 240) {
    return value.length <= limit ? value : value.slice(0, limit - 1) + "…";
}
function finiteNumber(value: unknown) {
    return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
function stringList(value: unknown, limit: number): string[] | undefined {
    if (!Array.isArray(value) || !value.every(item => typeof item === "string"))
        return undefined;
    return value.slice(0, limit) as string[];
}
function compactJsonValue(value: unknown, depth = 0, state?: { truncated: boolean }): JsonValue | undefined {
    if (value === null || typeof value === "boolean")
        return value;
    if (typeof value === "number")
        return Number.isFinite(value) ? value : undefined;
    if (typeof value === "string") {
        if (value.length <= 160)
            return value;
        if (state)
            state.truncated = true;
        return clipText(value, 160);
    }
    if (depth >= 2) {
        if (state)
            state.truncated = true;
        return undefined;
    }
    if (Array.isArray(value)) {
        if (value.length > 12 && state)
            state.truncated = true;
        return value.slice(0, 12).map(item => compactJsonValue(item, depth + 1, state)).filter((item): item is JsonValue => item !== undefined);
    }
    const object = objectValue(value);
    if (!object)
        return undefined;
    const entries = Object.entries(object);
    if (entries.length > 12 && state)
        state.truncated = true;
    const out: Record<string, JsonValue> = {};
    for (const [key, item] of entries.slice(0, 12)) {
        const compact = compactJsonValue(item, depth + 1, state);
        if (compact !== undefined)
            out[key] = compact;
    }
    return out;
}
function columnNames(value: unknown): string[] | undefined {
    const strings = stringList(value, Number.MAX_SAFE_INTEGER);
    if (strings)
        return strings;
    const object = objectValue(value);
    return object ? Object.keys(object) : undefined;
}
function evidenceColumns(data: Record<string, unknown> | undefined, state: { truncated: boolean }): Record<string, JsonValue> {
    if (!data)
        return {};
    const declared = Array.isArray(data.columns) ? data.columns : undefined;
    let columns: string[] | undefined;
    let total: number | undefined;
    if (declared && declared.every(item => typeof item === "string")) {
        total = declared.length;
        columns = declared.slice(0, 40) as string[];
    }
    else {
        const rows = Array.isArray(data.rows) ? data.rows : [];
        const first = rows.map(objectValue).find(item => item !== undefined);
        if (!first)
            return {};
        const keys = Object.keys(first);
        total = keys.length;
        columns = keys.slice(0, 40);
    }
    const out: Record<string, JsonValue> = { columns };
    if (total !== undefined && total > columns.length) {
        out.columns_total = total;
        out.columns_omitted = total - columns.length;
    }
    if (total !== undefined && total > 40)
        state.truncated = true;
    return out;
}
function scalarFields(data: Record<string, unknown> | undefined, state: { truncated: boolean }) {
    if (!data)
        return undefined;
    const skip = new Set(["ok", "tool", "rows", "columns", "row_count", "meta", "declared_column_semantics", "season_semantics", "tables", "catalog_scope", "lineup_variant_policy", "error", "summary", "recovery_hint", "next_actions", "sql"]);
    const out: Record<string, JsonValue> = {};
    for (const [key, value] of Object.entries(data)) {
        if (skip.has(key) || Object.keys(out).length >= 12)
            continue;
        if (typeof value === "string") {
            out[key] = clipText(value, 120);
            if (value.length > 120)
                state.truncated = true;
        }
        else if (typeof value === "number" && Number.isFinite(value))
            out[key] = value;
        else if (typeof value === "boolean")
            out[key] = value;
    }
    return Object.keys(out).length ? out : undefined;
}
function filterFields(args: Record<string, unknown>, state: { truncated: boolean }) {
    const out: Record<string, JsonValue> = {};
    for (const [key, value] of Object.entries(args)) {
        if (key === "sql" || key === "code" || Object.keys(out).length >= 16)
            continue;
        const compact = compactJsonValue(value, 0, state);
        if (compact !== undefined)
            out[key] = compact;
    }
    return Object.keys(out).length ? out : undefined;
}
function queryEvidence(record: SourceRecord, data: Record<string, unknown> | undefined, meta: Record<string, unknown> | undefined, state: { truncated: boolean }): Record<string, JsonValue> | undefined {
    const out: Record<string, JsonValue> = {};
    const sql = typeof record.args?.sql === "string" ? record.args.sql : typeof data?.sql === "string" ? data.sql : typeof meta?.sql === "string" ? meta.sql : undefined;
    if (sql) {
        out.sql = clipText(sql, 500);
        if (sql.length > 500) {
            out.sql_chars = sql.length;
            out.sql_truncated = true;
            state.truncated = true;
        }
    }
    const tables = stringList(meta?.tables, 12);
    if (tables)
        out.tables = tables;
    const filters = record.args ? filterFields(record.args, state) : undefined;
    if (filters) {
        out.filters = filters;
        if (state.truncated)
            out.filters_truncated = true;
    }
    if (typeof record.args?.code === "string")
        out.code_chars = record.args.code.length;
    return Object.keys(out).length ? out : undefined;
}
function pickSeasonValue(...values: unknown[]) {
    for (const value of values) {
        if (typeof value === "string" && value.trim())
            return clipText(value.trim(), 120);
        if (typeof value === "number" && Number.isFinite(value))
            return value;
    }
    return undefined;
}
function compactSeasonSemantics(semantics: Record<string, unknown>, state: { truncated: boolean }): Record<string, JsonValue> | undefined {
    const out: Record<string, JsonValue> = {};
    const tables = stringList(semantics.tables, 12);
    if (tables)
        out.tables = tables;
    const attribution = objectValue(semantics.query_attribution);
    if (attribution) {
        const mode = pickSeasonValue(attribution.mode);
        const reason = typeof attribution.reason === "string" ? clipText(attribution.reason, 160) : undefined;
        const lineage = typeof attribution.lineage_proven === "boolean" ? attribution.lineage_proven : undefined;
        if (mode !== undefined || reason !== undefined || lineage !== undefined)
            out.query_attribution = { ...(mode !== undefined ? { mode } : {}), ...(reason ? { reason } : {}), ...(lineage !== undefined ? { lineage_proven: lineage } : {}) };
    }
    const seasonColumns = Array.isArray(semantics.season_columns) ? semantics.season_columns : [];
    const columns = seasonColumns.slice(0, 8).map(objectValue).filter((item): item is Record<string, unknown> => item !== undefined).map(item => {
        const compact: Record<string, JsonValue> = {};
        for (const key of ["table", "column", "encoding", "row_grain", "attribution_supported"] as const) {
            const value = item[key];
            if (typeof value === "string")
                compact[key] = clipText(value, 120);
            else if (typeof value === "boolean")
                compact[key] = value;
        }
        return compact;
    }).filter(item => Object.keys(item).length);
    if (columns.length) {
        out.season_columns = columns;
        if (seasonColumns.length > columns.length) {
            out.season_columns_total = seasonColumns.length;
            out.season_columns_omitted = seasonColumns.length - columns.length;
            state.truncated = true;
        }
    }
    for (const key of ["resolved_labels", "ambiguities", "contradictions"] as const) {
        const items = Array.isArray(semantics[key]) ? semantics[key] : [];
        if (!items.length)
            continue;
        const limit = key === "resolved_labels" ? 5 : 3;
        const compact = items.slice(0, limit).map(item => compactJsonValue(item, 0, state)).filter((item): item is JsonValue => item !== undefined);
        out[key] = compact;
        out[`${key}_count`] = items.length;
        if (items.length > limit) {
            out[`${key}_omitted`] = items.length - limit;
            state.truncated = true;
        }
    }
    return Object.keys(out).length ? out : undefined;
}
function seasonEvidence(data: Record<string, unknown> | undefined, meta: Record<string, unknown> | undefined, state: { truncated: boolean }): Record<string, JsonValue> | undefined {
    if (!data)
        return undefined;
    const out: Record<string, JsonValue> = {};
    const season = pickSeasonValue(data.season, meta?.season);
    const seasonLabel = pickSeasonValue(data.season_label, meta?.season_label);
    const requestedSeason = pickSeasonValue(data.requested_season, meta?.requested_season);
    const seasonType = pickSeasonValue(data.season_type, meta?.season_type);
    if (season !== undefined)
        out.season = season;
    if (seasonLabel !== undefined)
        out.season_label = seasonLabel;
    if (requestedSeason !== undefined)
        out.requested_season = requestedSeason;
    if (seasonType !== undefined)
        out.season_type = seasonType;
    const semantics = objectValue(data.season_semantics);
    const compactSemantics = semantics ? compactSeasonSemantics(semantics, state) : undefined;
    if (compactSemantics)
        out.semantics = compactSemantics;
    return Object.keys(out).length ? out : undefined;
}
function unitEvidence(data: Record<string, unknown> | undefined, state: { truncated: boolean }): { units: Record<string, string>; units_total?: number; units_omitted?: number } | undefined {
    const semantics = objectValue(data?.declared_column_semantics);
    if (!semantics)
        return undefined;
    const entries = Object.entries(semantics);
    const units: Record<string, string> = {};
    for (const [column, value] of entries.slice(0, 24)) {
        const item = objectValue(value);
        const unit = typeof item?.unit === "string" && item.unit.trim() ? clipText(item.unit.trim(), 80) : undefined;
        if (unit)
            units[column] = unit;
    }
    if (!Object.keys(units).length)
        return undefined;
    if (entries.length > 24)
        state.truncated = true;
    return { units, ...(entries.length > 24 ? { units_total: entries.length, units_omitted: entries.length - 24 } : {}) };
}
function schemaEvidence(data: Record<string, unknown> | undefined, state: { truncated: boolean }): Record<string, JsonValue> | undefined {
    const tables = objectValue(data?.tables);
    if (!tables)
        return undefined;
    const entries = Object.entries(tables);
    const compactTables = entries.slice(0, 12).map(([name, columns]) => {
        const names = columnNames(columns);
        const out: Record<string, JsonValue> = { name };
        if (names) {
            out.columns = names.slice(0, 8);
            out.column_count = names.length;
            if (names.length > 8) {
                out.columns_omitted = names.length - 8;
                state.truncated = true;
            }
        }
        return out;
    });
    return { table_count: entries.length, tables: compactTables, ...(entries.length > 12 ? { tables_total: entries.length, tables_omitted: entries.length - 12 } : {}) };
}
const PROVENANCE_KEYS = ["source", "dataset", "season", "season_label", "requested_season", "season_type", "freshness", "last_fetch", "data_through", "cached", "estimated", "limit", "row_cap", "timeout_s", "ms", "empty_observation", "warning", "warnings", "note", "model", "version", "as_of", "generated_at", "catalog_scope", "negative_claim_scope"];
function provenanceEvidence(data: Record<string, unknown> | undefined, meta: Record<string, unknown> | undefined, state: { truncated: boolean }) {
    if (!data)
        return undefined;
    const out: Record<string, JsonValue> = {};
    for (const key of PROVENANCE_KEYS) {
        const value = compactJsonValue(data[key] ?? meta?.[key], 0, state);
        if (value !== undefined)
            out[key] = value;
    }
    return Object.keys(out).length ? out : undefined;
}
function errorEvidence(result: unknown, data: Record<string, unknown> | undefined, meta: Record<string, unknown> | undefined, isError: boolean, state: { truncated: boolean }) {
    if (!isError)
        return undefined;
    const error = typeof result === "string" ? result : typeof data?.error === "string" ? data.error : typeof meta?.error === "string" ? meta.error : undefined;
    if (!error)
        return undefined;
    if (error.length > 240)
        state.truncated = true;
    return clipText(error, 240);
}
function caveatEvidence(data: Record<string, unknown> | undefined, meta: Record<string, unknown> | undefined, isError: boolean, truncated: boolean) {
    const caveats: string[] = [];
    if (truncated)
        caveats.push("Evidence card clipped long strings, arrays, or objects; use read_source for the full result.");
    if (meta?.empty_observation === true)
        caveats.push("Empty result is an observed zero-row result.");
    if (meta?.capped === true || data?.capped === true || meta?.truncated === true || data?.truncated === true)
        caveats.push("Result was capped or truncated by the tool.");
    for (const key of ["warning", "note"] as const) {
        const value = meta?.[key];
        if (typeof value === "string" && value.trim())
            caveats.push(clipText(value.trim(), 180));
    }
    const warnings = stringList(meta?.warnings, 3);
    for (const warning of warnings ?? [])
        caveats.push(clipText(warning, 180));
    if (typeof data?.lineup_variant_policy === "string" && data.lineup_variant_policy.trim())
        caveats.push(clipText(data.lineup_variant_policy.trim(), 240));
    const semantics = objectValue(data?.season_semantics);
    if (Array.isArray(semantics?.ambiguities) && semantics.ambiguities.length)
        caveats.push("Season semantics include ambiguities; verify labels before comparing seasons.");
    if (Array.isArray(semantics?.contradictions) && semantics.contradictions.length)
        caveats.push("Season semantics include contradictions; inspect the source before relying on season scope.");
    if (isError && !caveats.length)
        caveats.push("Source result is an error; inspect read_source before retrying.");
    return caveats.length ? caveats : undefined;
}
function sourcePayload(record: SourceRecord) {
    const response = record.response;
    const text = response.content.map(objectValue).filter(item => item?.type === "text").map(item => item?.text).join("\n");
    let result: unknown = response.structuredContent;
    if (result === undefined) {
        try {
            result = JSON.parse(text);
        }
        catch {
            result = text;
        }
    }
    const isError = response.isError === true || objectValue(result)?.ok === false;
    return { result, isError };
}
function buildEvidenceCard(record: SourceRecord, result: unknown, isError: boolean) {
    const state = { truncated: false };
    const data = objectValue(result);
    const meta = objectValue(data?.meta);
    const rowCount = finiteNumber(data?.row_count) ?? (Array.isArray(data?.rows) ? data.rows.length : undefined) ?? finiteNumber(meta?.profile && objectValue(meta.profile)?.returned_rows) ?? finiteNumber(meta?.rows);
    const card: Record<string, JsonValue> = {
        ref: record.ref, tool: record.tool,
        ok: typeof data?.ok === "boolean" ? data.ok : !isError,
        is_error: isError
    };
    if (rowCount !== undefined)
        card.row_count = rowCount;
    Object.assign(card, evidenceColumns(data, state));
    const fields = scalarFields(data, state);
    if (fields)
        card.fields = fields;
    const query = queryEvidence(record, data, meta, state);
    if (query)
        card.query = query;
    const season = seasonEvidence(data, meta, state);
    if (season)
        card.season = season;
    const schema = schemaEvidence(data, state);
    if (schema)
        card.schema = schema;
    const units = unitEvidence(data, state);
    if (units) {
        card.units = units.units;
        if (units.units_total !== undefined) {
            card.column_units_total = units.units_total;
            if (units.units_omitted !== undefined)
                card.column_units_omitted = units.units_omitted;
        }
    }
    const provenance = provenanceEvidence(data, meta, state);
    if (provenance)
        card.provenance = provenance;
    const error = errorEvidence(result, data, meta, isError, state);
    if (error !== undefined)
        card.error = error;
    const caveats = caveatEvidence(data, meta, isError, state.truncated);
    if (caveats)
        card.caveats = caveats;
    return card;
}
export function sourceEvidenceCard(record: SourceRecord): Record<string, JsonValue> {
    const { result, isError } = sourcePayload(record);
    return buildEvidenceCard(record, result, isError);
}
function jsonValue(value: unknown): JsonValue {
    if (value === null || typeof value === "string" || typeof value === "boolean")
        return value;
    if (typeof value === "number" && Number.isFinite(value))
        return value;
    if (Array.isArray(value))
        return value.map(jsonValue);
    const object = objectValue(value);
    if (object)
        return Object.fromEntries(Object.entries(object).map(([key, item]) => [key, jsonValue(item)]));
    throw new TypeError("Tool returned a non-JSON value");
}
export function sourceResult(record: SourceRecord) {
    const { result, isError } = sourcePayload(record);
    const content: {
        type: "text";
        text: string;
    }[] = isError ? [{ type: "text", text: typeof result === "string" ? result : JSON.stringify(result) }] : [];
    return { content, details: undefined, structuredContent: { ref: record.ref, tool: record.tool, result: jsonValue(result), evidence: buildEvidenceCard(record, result, isError), isError }, isError };
}
export type PythonToolsOptions = {
    python: string;
    cwd: string;
    env: NonNullable<StdioTransportOptions["env"]>;
};
export async function connectPythonTools({ python, cwd, env }: PythonToolsOptions) {
    if (!isAbsolute(python) || !isAbsolute(cwd) || !isAbsolute(env.DIME_WAREHOUSE ?? "")) {
        throw new TypeError("Absolute python, private cwd and explicit DIME_WAREHOUSE are required");
    }
    const transport = new StdioTransport({
        command: python,
        args: ["-B", fileURLToPath(new URL("../python_tools.py", import.meta.url))],
        cwd, env, inheritEnv: false, maxStderrBytes: 65536
    });
    const client = new McpClient({ name: "dime-analyst", version: "1", requestTimeoutMs: 90000 });
    const results = new Map<string, SourceRecord>();
    try {
        await client.connect(transport);
        const catalogue = (await client.listTools()).filter(tool =>
            (ANALYST_TOOL_NAMES as readonly string[]).includes(tool.name)
        );
        if (catalogue.length !== ANALYST_TOOL_NAMES.length ||
            !ANALYST_TOOL_NAMES.every(name => catalogue.some(tool => tool.name === name))) {
            throw new Error("Unexpected Python tool catalogue");
        }
        const tools = catalogue.map(tool => {
            const name = tool.name as PythonToolName;
            if (!ANALYST_TOOL_NAMES.includes(name))
                throw new Error("Unexpected Python tool");
            const namespace = TOOL_NAMESPACE_MAP.get(name);
            return defineTool({
                name, label: name,
                ...(namespace ? { namespace } : {}),
                description: tool.description + " Returns {ref, tool, result, evidence, isError}. evidence is a compact source card; result keeps full rows. Filter result before returning from codemode; retain ref.",
                parameters: Type.Unsafe<Record<string, unknown>>(tool.inputSchema), outputSchema: sourceOutputSchema,
                async execute(callId, args, signal) {
                    const response: CallToolResult = await client.callTool(name, args, { signal });
                    const recordArgs = objectValue(args);
                    const record: SourceRecord = { ref: randomUUID(), callId, tool: name, ...(recordArgs ? { args: recordArgs } : {}), response };
                    results.set(record.ref, record);
                    return sourceResult(record);
                }
            });
        });
        return { tools, results, get pid() { return transport.pid; }, close: () => client.close() };
    }
    catch (error) {
        await client.close();
        throw new Error(`Python tool connection failed: ${error instanceof Error ? error.message : String(error)}\n${transport.stderr}`, { cause: error });
    }
}

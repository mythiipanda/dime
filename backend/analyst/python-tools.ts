import { McpClient, StdioTransport, type CallToolResult, type StdioTransportOptions } from "@earendil-works/pi-mcp";
import { randomUUID } from "node:crypto";
import { isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import type { JsonValue } from "@earendil-works/pi-ai";
import { defineTool } from "@earendil-works/pi-coding-agent";

export type PythonToolName =
    | "sql_exec"
    | "warehouse_schema"
    | "get_rapm"
    | "get_game_prediction"
    | "get_wpa_leaders"
    | "get_comps"
    | "get_lineup_stats"
    | "get_win_prob"
    | "get_on_off"
    | "get_shot_zones"
    | "get_four_factors"
    | "get_clutch_stats"
    | "get_competitive_ratings"
    | "get_hustle"
    | "get_injuries"
    | "get_award_results"
    | "get_briefing"
    | "get_standings"
    | "get_rest"
    | "get_team_trajectory"
    | "get_ratings"
    | "get_rookie_leaders"
    | "get_cap_ledger"
    | "get_leaders"
    | "get_lineup_leaders"
    | "get_playoffs"
    | "get_team_leaders"
    | "get_team_compare"
    | "get_elo_standings"
    | "get_draft_board"
    | "get_combine"
    | "get_young_player_usage"
    | "get_contract_value"
    | "get_trade_check"
    | "get_trade_value"
    | "get_situational_splits"
    | "get_playoff_sim"
    | "get_playoff_team_ratings"
    | "get_player_risers"
    | "get_standings_deep"
    | "get_warehouse_freshness"
    | "get_finder"
    | "get_draft_model"
    | "get_leaderboard_deltas"
    | "get_player_ratings"
    | "get_risers"
    | "get_team_four_factors"
    | "get_streaks"
    | "get_playtype_profile"
    | "get_defensive_matchups"
    | "get_head_to_head"
    | "get_lineup_matchup_matrix"
    | "get_transactions"
    | "get_wowy"
    | "get_shot_compare"
    | "get_raptor_history"
    | "get_season_series"
    | "get_team_game_log"
    | "get_zone_deltas"
    | "search_shots"
    | "get_stint_timeline"
    | "get_possession_log"
    | "get_elo"
    | "get_team_shot_zones"
    | "get_historical_leaders"
    | "get_today"
    | "get_morning_briefing"
    | "get_tracking_profile"
    | "get_rest_advantage"
    | "get_rapm_prior"
    | "search_game_logs"
    | "get_dataset"
    | "get_dataset_freshness"
    | "get_career_arc"
    | "run_python";

export const ANALYST_TOOL_NAMES: readonly PythonToolName[] = [
    "sql_exec",
    "warehouse_schema",
    "get_rapm",
    "get_game_prediction",
    "get_wpa_leaders",
    "get_comps",
    "get_lineup_stats",
    "get_win_prob",
    "get_on_off",
    "get_shot_zones",
    "get_four_factors",
    "get_clutch_stats",
    "get_competitive_ratings",
    "get_hustle",
    "get_injuries",
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
] as const;

export const sourceRecordSchema = Type.Object({
    ref: Type.String(), callId: Type.String(),
    tool: Type.Union([
        Type.Literal("sql_exec"),
        Type.Literal("warehouse_schema"),
        Type.Literal("get_rapm"),
        Type.Literal("get_game_prediction"),
        Type.Literal("get_wpa_leaders"),
        Type.Literal("get_comps"),
        Type.Literal("get_lineup_stats"),
        Type.Literal("get_win_prob"),
        Type.Literal("get_on_off"),
        Type.Literal("get_shot_zones"),
        Type.Literal("get_four_factors"),
        Type.Literal("get_clutch_stats"),
        Type.Literal("get_competitive_ratings"),
        Type.Literal("get_hustle"),
        Type.Literal("get_injuries"),
        Type.Literal("get_award_results"),
        Type.Literal("get_briefing"),
        Type.Literal("get_standings"),
        Type.Literal("get_rest"),
        Type.Literal("get_team_trajectory"),
        Type.Literal("get_ratings"),
        Type.Literal("get_rookie_leaders"),
        Type.Literal("get_cap_ledger"),
        Type.Literal("get_leaders"),
        Type.Literal("get_lineup_leaders"),
        Type.Literal("get_playoffs"),
        Type.Literal("get_team_leaders"),
        Type.Literal("get_team_compare"),
        Type.Literal("get_elo_standings"),
        Type.Literal("get_draft_board"),
        Type.Literal("get_combine"),
        Type.Literal("get_young_player_usage"),
        Type.Literal("get_contract_value"),
        Type.Literal("get_trade_check"),
        Type.Literal("get_trade_value"),
        Type.Literal("get_situational_splits"),
        Type.Literal("get_playoff_sim"),
        Type.Literal("get_playoff_team_ratings"),
        Type.Literal("get_player_risers"),
        Type.Literal("get_standings_deep"),
        Type.Literal("get_warehouse_freshness"),
        Type.Literal("get_finder"),
        Type.Literal("get_draft_model"),
        Type.Literal("get_leaderboard_deltas"),
        Type.Literal("get_player_ratings"),
        Type.Literal("get_risers"),
        Type.Literal("get_team_four_factors"),
        Type.Literal("get_streaks"),
        Type.Literal("get_playtype_profile"),
        Type.Literal("get_defensive_matchups"),
        Type.Literal("get_head_to_head"),
        Type.Literal("get_lineup_matchup_matrix"),
        Type.Literal("get_transactions"),
        Type.Literal("get_wowy"),
        Type.Literal("get_shot_compare"),
        Type.Literal("get_raptor_history"),
        Type.Literal("get_season_series"),
        Type.Literal("get_team_game_log"),
        Type.Literal("get_zone_deltas"),
        Type.Literal("search_shots"),
        Type.Literal("get_stint_timeline"),
        Type.Literal("get_possession_log"),
        Type.Literal("get_elo"),
        Type.Literal("get_team_shot_zones"),
        Type.Literal("get_historical_leaders"),
        Type.Literal("get_today"),
        Type.Literal("get_morning_briefing"),
        Type.Literal("get_tracking_profile"),
        Type.Literal("get_rest_advantage"),
        Type.Literal("get_rapm_prior"),
        Type.Literal("search_game_logs"),
        Type.Literal("get_dataset"),
        Type.Literal("get_dataset_freshness"),
        Type.Literal("get_career_arc"),
        Type.Literal("run_python"),
    ]),
    response: Type.Object({
        content: Type.Array(Type.Unknown()),
        structuredContent: Type.Optional(Type.Unknown()), isError: Type.Optional(Type.Boolean())
    }, { additionalProperties: true }),
}, { additionalProperties: false });
export type SourceRecord = Static<typeof sourceRecordSchema>;
export const sourceOutputSchema = Type.Object({ ref: Type.String(), tool: Type.String(), result: Type.Unknown(), isError: Type.Boolean() }, { additionalProperties: false });
const objectSchema = Type.Record(Type.String(), Type.Unknown());
export function objectValue(value: unknown) {
    return Value.Check(objectSchema, value) ? value : undefined;
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
    const content: {
        type: "text";
        text: string;
    }[] = isError ? [{ type: "text", text: typeof result === "string" ? result : JSON.stringify(result) }] : [];
    return { content, details: undefined, structuredContent: { ref: record.ref, tool: record.tool, result: jsonValue(result), isError }, isError };
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
    const client = new McpClient({ name: "dime-analyst", version: "1", requestTimeoutMs: 15000 });
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
        // The Python catalogue remains the authority for arguments. Its JSON Schema is checked by Pi.
        const tools = catalogue.map(tool => {
            const name = tool.name as PythonToolName;
            if (!ANALYST_TOOL_NAMES.includes(name))
                throw new Error("Unexpected Python tool");
            return defineTool({
                name, label: name,
                description: tool.description + " Returns {ref, tool, result, isError}. Filter result before returning from codemode; retain ref.",
                parameters: Type.Unsafe<Record<string, unknown>>(tool.inputSchema), outputSchema: sourceOutputSchema,
                async execute(callId, args, signal) {
                    const response: CallToolResult = await client.callTool(name, args, { signal });
                    const record: SourceRecord = { ref: randomUUID(), callId, tool: name, response };
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

import { McpClient, StdioTransport, type CallToolResult, type StdioTransportOptions } from "@earendil-works/pi-mcp";
import { randomUUID } from "node:crypto";
import { isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import type { JsonValue } from "@earendil-works/pi-ai";
import { defineTool } from "@earendil-works/pi-coding-agent";

export const ANALYST_TOOL_NAMES = [
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
    "get_matchup_preview",
    "get_matchup_splits",
    "get_regression_check",
    "get_scout_pack",
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
] as const;

export type PythonToolName = (typeof ANALYST_TOOL_NAMES)[number];

type ToolLiteralTuple<T extends readonly string[]> = { -readonly [K in keyof T]: Type.TLiteral<T[K]> };
function makeToolLiterals<const T extends readonly string[]>(names: T): ToolLiteralTuple<T> {
    return names.map(name => Type.Literal(name)) as unknown as ToolLiteralTuple<T>;
}

export const sourceRecordSchema = Type.Object({
    ref: Type.String(), callId: Type.String(),
    tool: Type.Union(makeToolLiterals(ANALYST_TOOL_NAMES)),
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

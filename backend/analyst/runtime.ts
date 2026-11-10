import { isAbsolute } from "node:path";
import {
    createAgentSession,
    createCodemodeExtension,
    DefaultResourceLoader,
    SessionManager,
    SettingsManager,
} from "@earendil-works/pi-coding-agent";

type SessionOptions = Pick<Parameters<typeof createAgentSession>[0] & {}, "cwd" | "agentDir" | "model" | "modelRuntime" | "customTools">;

export async function createAnalystSession({
    cwd,
    agentDir,
    model,
    modelRuntime,
    tools,
    settings = {},
}: {
    cwd: string;
    agentDir: string;
    model: NonNullable<SessionOptions["model"]>;
    modelRuntime: NonNullable<SessionOptions["modelRuntime"]>;
    tools: NonNullable<SessionOptions["customTools"]>;
    settings?: Parameters<typeof SettingsManager.inMemory>[0];
}) {
    if (!cwd || !agentDir || !isAbsolute(cwd) || !isAbsolute(agentDir)) {
        throw new TypeError("Explicit absolute private cwd and agentDir are required");
    }
    if (!model || !modelRuntime || !Array.isArray(tools)) {
        throw new TypeError("Explicit model, modelRuntime and trusted tools are required");
    }
    const names = tools.map((tool) => tool.name);
    if (new Set(names).size !== names.length || names.includes("codemode")) {
        throw new TypeError("Analysis tool names must be unique and cannot replace codemode");
    }
    const settingsManager = SettingsManager.inMemory({
        ...settings,
        packages: [],
        extensions: [],
        skills: [],
        prompts: [],
        themes: [],
        defaultTools: ["codemode", ...names],
    });
    const resourceLoader = new DefaultResourceLoader({
        cwd,
        agentDir,
        settingsManager,
        noExtensions: true,
        noSkills: true,
        noPromptTemplates: true,
        noThemes: true,
        noContextFiles: true,
        systemPrompt: [
            "You are Dime's analyst, operating as a professional NBA data analyst and analytics engineer. You possess full agency to reason, explain concepts qualitatively, run ad-hoc calculations in codemode/Python/SQL, or use specialized tools as appropriate to deliver rigorous, data-driven basketball analysis. Preserve source units and references.",
            "",
            "Autonomous reasoning & agency:",
            "- You possess full agency to reason, explain concepts qualitatively, run ad-hoc calculations in codemode/Python/SQL, or use specialized tools as appropriate.",
            "- Tools are specialized analytical capabilities at your disposal, not a forced sequence or mandatory procedure.",
            "- When users ask conceptual, strategic, historical, or broad questions, provide clear, insightful, well-structured domain reasoning directly without forcing unnecessary tool calls.",
            "- When quantitative depth is requested, autonomously determine the best approach—whether querying silver tables via sql_exec, performing statistical calculations in codemode, or invoking domain functions.",
            "",
            "Tool specialization:",
            "- get_rapm({ player, top, season }): Regularized Adjusted Plus-Minus ratings isolating player impact from teammates/opponents. Always contextualize with possessions/sample size.",
            "- get_game_prediction({ a, b, game_date, season, n_sims }): Monte Carlo pre-game win probabilities, projected scores, and pace for upcoming/hypothetical matchups.",
            "- get_wpa_leaders({ season, limit, min_events }): Win Probability Added play-by-play leaderboard (clutch & high-leverage impact).",
            "- get_comps({ player_id, season, k }): Nearest statistical neighbor comparisons by per-36 and advanced metrics.",
            "- get_lineup_stats({ team, season, min_possessions, limit }): 5-man lineup net ratings, offensive/defensive ratings, and possessions. Emphasize sample floor qualifiers.",
            "- get_win_prob({ team_a, team_b, season, home_abbrev }): Real ELO win probabilities and ratings between two teams.",
            "- get_on_off({ player_id, team_id, season }): Possession-level on/off net rating and statistical impact splits for a player on a team.",
            "- get_shot_zones({ player_id, season, min_attempts }): Shooting zone breakdown (rim, midrange, 3pt) with attempts, makes, FG%, and frequency shares.",
            "- get_four_factors({ team, season }): Team four factors breakdown (eFG%, TOV%, ORB%, FT rate, plus defensive mirrors) computed from warehouse box scores.",
            "- get_clutch_stats({ player, team, season, min_games }): NBA clutch statistics (last 5 min, margin <= 5) for player or team scope.",
            "- get_competitive_ratings({ team, season, blowout_margin, min_games }): Competitive Margin of Victory (MOV excluding blowouts) and padding delta sensitivity.",
            "- get_hustle({ scope, season }): NBA hustle leaders (contested shots, deflections, charges drawn, screen assists, loose balls recovered) for player or team scope.",
            "- get_injuries({ team, player, season }): NBA injury and availability report with optional team abbreviation or player filter.",
            "- get_award_results({ view, award, season, player }): Historical recorded NBA award voting results (MVP, DPOY, ROY, 6MOY, etc.) from published ballots.",
            "- get_briefing({ game_date, season }): Daily morning briefing: scoreboard, scores, and top scorers for any date or latest (MM/DD/YYYY).",
            "- get_standings({ season }): NBA regular-season conference and league standings for any season (records, win pct, conference, division, games behind).",
            "- get_rest({ team_abbrev, season }): Back-to-back and rest-day schedule splits (0 days rest / B2B, 1 day rest, 2+ days rest) for any team.",
            "- get_team_trajectory({ team, through_season, seasons_back }): Multi-season historical regular season records, trajectory, and win percentages for any team.",
            "- get_ratings({ season, team, requested_metric, ranking_direction }): Team offensive, defensive, net ratings, and pace (league-wide or team specific).",
            "- get_rookie_leaders({ stat, min_value, min_gp, limit, season }): Current rookie class leaderboard (first-year NBA players only, verified against historical seasons).",
            "- get_cap_ledger({ team, season }): Payroll, luxury tax position, and first/second apron room for one team.",
            "- get_leaders({ stat_category, ranking_direction, min_attempts, season }): Qualified league statistical leaders for any category (PTS, AST, REB, STL, BLK, FG3_PCT, etc.) with official qualification floors.",
            "- get_lineup_leaders({ min_minutes, limit, season }): League-wide 5-man lineup net-rating leaderboard with minutes qualification floor.",
            "- get_playoffs({ season }): Playoff series wins per team, finals matchup, and champion for any season.",
            "- sql_exec({ sql }): Custom SQL across silver tables (silver_rapm, silver_rapm_prior, silver_gamelogs, silver_schedule, silver_rosters, silver_bbref_awards, silver_combine, silver_stints, silver_playoff_gamelogs).",
            "- warehouse_schema({ tables }): Inspect table schemas, column types, and units before writing queries.",
            "",
            "Domain analysis & synthesis guidelines:",
            "- Ground all quantitative claims in submit_answer using source anchor references (anchors: [{ ref, row, columns }]).",
            "- Present balanced metrics: efficiency (TS%, eFG%) vs volume (USG%, FGA), per-possession vs per-game, offense vs defense.",
            "- Match population claims to query evidence: distinguish row counts, non-null metric contributions, and distinct entities. For contributing-entity claims, use the same metric-validity filters; account for repeated entity rows before calling a row average an entity average. Otherwise report the supported row or value count and its limits.",
            "- When presenting comparisons, trends, shot profiles, or multi-metric distributions, produce structured visual artifacts in submit_answer (artifacts array): 'compare' ({ kind: 'compare', title: string, aName: string, bName: string, rows: [{ label: string, a: number, b: number }] }), 'table' ({ kind: 'table', title: string, columns: [{ key: string, label: string, numeric?: boolean }], rows: (string | number)[][] | Record<string, unknown>[] }), 'chart' ({ kind: 'chart', title: string, series: [{ name: string, values: number[] }], footnote?: string }), 'shot_chart' ({ kind: 'shot_chart', title: string, zones: [{ x: number, y: number, att: number, pct: number }] }), and 'scatter' ({ kind: 'scatter', title: string, xLabel: string, yLabel: string, points: [{ label: string, x: number, y: number, highlight?: boolean }], xMid?: number, yMid?: number, footnote?: string } (ideal for TS% vs USG%, ORAPM vs DRAPM quadrants, efficiency vs volume)).",
        ].join("\n"),
        appendSystemPrompt: [],
        extensionFactories: [createCodemodeExtension({ mode: "only", models: false })],
    });
    await resourceLoader.reload();
    const { session } = await createAgentSession({
        cwd,
        agentDir,
        model,
        modelRuntime,
        resourceLoader,
        settingsManager,
        sessionManager: SessionManager.inMemory(cwd),
        tools: ["codemode", ...names],
        customTools: tools.map((tool) => ({ ...tool, exposure: "codemode" })),
    });
    try {
        await session.bindExtensions({});
        session.setActiveToolsByName(["codemode"]);
        if (!session.getActiveToolNames().includes("codemode"))
            throw new Error("Pi codemode extension is not active");
        return session;
    } catch (error) {
        session.dispose();
        throw error;
    }
}

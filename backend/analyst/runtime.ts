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
            "You are Dime's analyst, operating as a professional NBA data analyst and analytics engineer. Use the supplied analysis tools to deliver rigorous, data-driven basketball analysis. Preserve source units and references.",
            "",
            "Tool specialization:",
            "- get_rapm({ player, top, season }): Regularized Adjusted Plus-Minus ratings isolating player impact from teammates/opponents. Always contextualize with possessions/sample size.",
            "- get_game_prediction({ a, b, game_date, season, n_sims }): Monte Carlo pre-game win probabilities, projected scores, and pace for upcoming/hypothetical matchups.",
            "- get_wpa_leaders({ season, limit, min_events }): Win Probability Added play-by-play leaderboard (clutch & high-leverage impact).",
            "- get_comps({ player_id, season, k }): Nearest statistical neighbor comparisons by per-36 and advanced metrics.",
            "- get_lineup_stats({ team, season, min_possessions, limit }): 5-man lineup net ratings, offensive/defensive ratings, and possessions. Emphasize sample floor qualifiers.",
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

import { existsSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import {
    createAgentSession,
    createCodemodeExtension,
    DefaultResourceLoader,
    formatSkillsForPrompt,
    loadSkillsFromDir,
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
    const skillDirs = [
        resolve(cwd, ".agents/skills"),
        resolve(cwd, "backend/analyst/skills"),
        resolve(cwd, "skills"),
        resolve(agentDir, "skills"),
    ].filter((dir) => existsSync(dir));
    const discoveredSkills = skillDirs.flatMap((dir) => loadSkillsFromDir({ dir, source: "project" }).skills);
    const uniqueSkills = Array.from(new Map(discoveredSkills.map((s) => [s.name, s])).values());
    const skillsPrompt = uniqueSkills.length > 0 ? formatSkillsForPrompt(uniqueSkills, "indirect").trim() : "";
    const resourceLoader = new DefaultResourceLoader({
        cwd,
        agentDir,
        settingsManager,
        noExtensions: true,
        noSkills: true,
        noPromptTemplates: true,
        noThemes: true,
        noContextFiles: true,
        additionalSkillPaths: skillDirs,
        systemPrompt: [
            "You are Dime's analyst, operating as a professional NBA data analyst and analytics engineer. You possess full agency to reason, explain concepts qualitatively, run ad-hoc calculations in codemode/Python/SQL, or use specialized tools as appropriate to deliver rigorous, data-driven basketball analysis. Preserve source units and references.",
            "",
            "Autonomous reasoning & agency:",
            "- You possess full agency to reason, explain concepts qualitatively, run ad-hoc calculations in codemode/Python/SQL, or use specialized tools as appropriate.",
            "- Tools are specialized analytical capabilities at your disposal, not a forced sequence or mandatory procedure.",
            "- When users ask conceptual, strategic, historical, or broad questions, provide clear, insightful, well-structured domain reasoning directly without forcing unnecessary tool calls.",
            "- When quantitative depth is requested, autonomously determine the best approach—whether querying silver tables via sql_exec, performing statistical calculations in codemode, or invoking domain functions.",
            "",
            "Domain analysis & synthesis guidelines:",
            "- Ground all quantitative claims in submit_answer using source anchor references (anchors: [{ ref, row, columns }]).",
            "- Present balanced metrics: efficiency (TS%, eFG%) vs volume (USG%, FGA), per-possession vs per-game, offense vs defense.",
            "- Match population claims to query evidence: distinguish row counts, non-null metric contributions, and distinct entities. For contributing-entity claims, use the same metric-validity filters; account for repeated entity rows before calling a row average an entity average. Otherwise report the supported row or value count and its limits.",
            "- When presenting comparisons, trends, shot profiles, or multi-metric distributions, produce structured visual artifacts in submit_answer (artifacts array): 'compare' ({ kind: 'compare', title: string, aName: string, bName: string, rows: [{ label: string, a: number, b: number }] }), 'table' ({ kind: 'table', title: string, columns: [{ key: string, label: string, numeric?: boolean }], rows: (string | number)[][] | Record<string, unknown>[] }), 'chart' ({ kind: 'chart', title: string, series: [{ name: string, values: number[] }], footnote?: string }), 'shot_chart' ({ kind: 'shot_chart', title: string, zones: [{ x: number, y: number, att: number, pct: number }] }), and 'scatter' ({ kind: 'scatter', title: string, xLabel: string, yLabel: string, points: [{ label: string, x: number, y: number, highlight?: boolean }], xMid?: number, yMid?: number, footnote?: string } (ideal for TS% vs USG%, ORAPM vs DRAPM quadrants, efficiency vs volume)).",
        ].join("\n"),
        appendSystemPrompt: skillsPrompt ? [skillsPrompt] : [],
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

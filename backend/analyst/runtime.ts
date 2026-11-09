import { isAbsolute } from "node:path";
import { createAgentSession, createCodemodeExtension, DefaultResourceLoader, SessionManager, SettingsManager, } from "@earendil-works/pi-coding-agent";
type SessionOptions = Pick<Parameters<typeof createAgentSession>[0] & {}, "cwd" | "agentDir" | "model" | "modelRuntime" | "customTools">;
export async function createAnalystSession({ cwd, agentDir, model, modelRuntime, tools, settings = {} }: {
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
        packages: [], extensions: [], skills: [], prompts: [], themes: [],
        defaultTools: ["codemode", ...names],
    });
    const resourceLoader = new DefaultResourceLoader({
        cwd, agentDir, settingsManager,
        noExtensions: true, noSkills: true, noPromptTemplates: true,
        noThemes: true, noContextFiles: true,
        systemPrompt: "You are Dime's analyst. Use the supplied analysis tools. Preserve source units and references. Match population claims to query evidence: distinguish row counts, non-null metric contributions, and distinct entities. For contributing-entity claims, use the same metric-validity filters; account for repeated entity rows before calling a row average an entity average. Otherwise report the supported row or value count and its limits. When helpful for analytical queries, generate multimodal visual artifacts in submit_answer (artifacts array): 'chart' ({ kind: 'chart', title: string, series: [{ name: string, values: number[] }], footnote?: string }), 'shot_chart' ({ kind: 'shot_chart', title: string, zones: [{ x: number, y: number, att: number, pct: number }] }), 'compare' ({ kind: 'compare', title: string, aName: string, bName: string, rows: [{ label: string, a: number, b: number }] }), and 'table' ({ kind: 'table', title: string, columns: [{ key: string, label: string, numeric?: boolean }], rows: (string | number)[][] | Record<string, unknown>[] }).",
        appendSystemPrompt: [],
        extensionFactories: [createCodemodeExtension({ mode: "only", models: false })],
    });
    await resourceLoader.reload();
    const { session } = await createAgentSession({
        cwd, agentDir, model, modelRuntime, resourceLoader, settingsManager,
        sessionManager: SessionManager.inMemory(cwd),
        tools: ["codemode", ...names], customTools: tools.map((tool) => ({ ...tool, exposure: "codemode" })),
    });
    try {
        await session.bindExtensions({});
        session.setActiveToolsByName(["codemode"]);
        if (!session.getActiveToolNames().includes("codemode"))
            throw new Error("Pi codemode extension is not active");
        return session;
    }
    catch (error) {
        session.dispose();
        throw error;
    }
}

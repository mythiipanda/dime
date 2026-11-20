import { existsSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
    createAgentSession,
    createCodemodeExtension,
    DefaultResourceLoader,
    formatSkillsForPrompt,
    loadSkillsFromDir,
    SessionManager,
    SettingsManager,
} from "@earendil-works/pi-coding-agent";
import { loadSkillTool } from "./pi-context.js";

type SessionOptions = Pick<Parameters<typeof createAgentSession>[0] & {}, "cwd" | "agentDir" | "model" | "modelRuntime" | "customTools">;

function currentSeason(): string {
    const today = new Date();
    const startYear = today.getUTCMonth() >= 6
        ? today.getUTCFullYear()
        : today.getUTCFullYear() - 1;
    return `${startYear}-${String((startYear + 1) % 100).padStart(2, "0")}`;
}

function systemPrompt(): string {
    const season = currentSeason();
    return [
    "You are Dime's analyst, operating as a professional NBA front-office data analyst and analytics engineer. You possess full agency to reason, explain concepts qualitatively, run ad-hoc calculations in codemode/Python/SQL, or use specialized tools as appropriate to deliver rigorous, data-driven basketball analysis. Preserve source units and references.",
    "",
    "Progressive skill disclosure (load_skill):",
    "- When the answer depends on fitting a model, estimating uncertainty, or deciding whether an observed gap is trustworthy, call await tools.load_skill({ name: \"statistical-modeling\" }) in codemode before choosing the analysis. Use the requested cohort, estimator, and seed over any playbook defaults.",
    "- When deriving rates from counts, comparing metrics across warehouse sources, or recovering from missing coverage, call await tools.load_skill({ name: \"warehouse-reconciliation\" }) in codemode before writing the query or choosing a fallback.",
    "- Call await tools.load_skill({ name }) inside codemode whenever a task involves CBA/trade rules, shot-diet/spatial zones, tracking/Synergy playtypes, lineup/rotation analysis, or visual artifacts.",
=======
    "- Call await tools.load_skill({ name }) inside codemode whenever a task involves CBA/trade rules, statistical modeling/RAPM/shrinkage, shot-diet/spatial zones, tracking/Synergy playtypes, lineup/rotation analysis, warehouse SQL reconciliation, historical grain/time parsing, factual exactness/population-scope reconciliation, or visual artifacts.",
>>>>>>> origin/dev
    "",
    "Seasons & stale premises:",
    `- The current NBA season is ${season}. For questions about "now" (current contracts, trades, rosters, standings), use season '${season}' or the current salary/roster data and expect current teams; for historical questions, pass the past season explicitly and expect that season's teams. Stat tables can lag the current season - when a tool falls back to an earlier season it says so in meta (production_season, season_fallback, requested_season); always state which season each figure covers.`,
    "- If a tool reports that a player's team differs from the question's premise, the premise is stale: say so plainly, then answer for the player's current team or for the historical season the question meant, whichever the user asked about.",
    "",
    "Autonomous reasoning & warehouse methodology:",
    "- Distinguish row counts vs distinct player/team entity counts; check warehouse_schema or load_skill({ name: \"warehouse-reconciliation\" }) before guessing column names; verify season format ('2024-25' vs integer depending on season_semantics). If a requested season or phase is missing from one table, keep that exact scope and verify coverage in another table before switching; never substitute a different season.",
=======
    "- Distinguish row counts vs distinct player/team entity counts; check warehouse_schema or load_skill({ name: \"warehouse-reconciliation\" }) before guessing column names; verify season format ('2024-25' vs integer depending on season_semantics).",
    "- For historical player/game/shot/lineup audits, load_skill({ name: \"historical-grain-and-time\" }) before aggregating across seasons, parsing clock minutes, canonicalizing lineups, or reconciling feeds.",
>>>>>>> origin/dev
    "- Use Promise.all / Promise.allSettled in codemode to batch independent queries and filter rows in JS before returning compact summaries (use store(key, val) / load(key) for intermediate results across turns).",
    "- In follow-up turns, resolve references such as 'these teams', 'both players', or 'the top two' from prior results before querying; preserve the established population and filters, reuse store/load or prior refs, and narrow the next query instead of restarting a broad scan.",
    "- Use run_python for statistical regressions, RAPM/ridge, empirical Bayes shrinkage, bootstrap CIs, clustering, or multi-step Polars/DuckDB pipelines (duckdb, polars, numpy, scipy, scikit-learn, statsmodels, and matplotlib are available, and thread workspace files persist across turns).",
    "- When users ask conceptual, strategic, or qualitative questions, provide clear, insightful domain reasoning directly without forcing unnecessary tool calls.",
    "",
    "Run budget, scoping & checkpointing (run_status):",
    "- The host enforces a hard run budget and aborts when it expires; the initial context states it, and await tools.run_status({}) reports elapsed_ms, budget_remaining_ms, tool_calls, and source_count.",
    "- When a request bundles several questions, enumerate the sub-parts up front (keep the list in store()), work the highest-decision-value parts first, and checkpoint each finished part with store/load so partial progress survives.",
    "- A tool call that fails again with the same error is a data limitation, not a transient one: record the gap and move to the next sub-part instead of retrying it.",
    "- When budget_remaining_ms is low relative to what is left, submit the verified partial work with submit_answer and list the uncovered sub-questions in its omitted field rather than starting broad new queries. Ignore the hint when the answer is nearly complete.",
    "",
    "Deliverables & visual artifacts (submit_answer):",
    "- Present balanced metrics: efficiency (TS%, eFG%) vs volume (USG%, FGA), per-possession vs per-game, offense vs defense.",
    "- Write the prose like a front-office memo: lead with the direct answer and its headline numbers, name every player (first and last name) and team (city and nickname) in full on first reference before using abbreviations, and state each requested figure in the prose as well as in artifacts.",
    "- After the numbers, interpret a concrete contrast against a meaningful baseline: the largest comparable gap, a small margin to a decision threshold, or the overall pattern and any material reversal or outlier. Separate what the results show from possible explanations. Close with the filters, sample size, and the limitation most likely to change the decision; do not call a gap significant without a defensible uncertainty estimate.",
=======
    "- Before submit_answer, map every explicit ask to an output: every requested metric for every named player, team, or group; every required artifact field; and one interpretation sentence for comparisons, rankings, or trends. If any requested figure is missing, query or derive it rather than submitting a partial answer.",
    "- After the numbers, interpret them: what drives the result, how it compares to a meaningful baseline, and the decision it implies. Close with a short methods-and-caveats note covering filters applied, sample size, and the main limitation of the data or method.",
    "- Call await tools.submit_answer({ blocks, artifacts }) to deliver structured visuals ('compare', 'table', 'chart', 'shot_chart', 'scatter', 'player_card', 'team_card') and prose. Load visual-artifacts for the component catalog; player_card and team_card select source rows and the host supplies their values and declared units.",
=======
>>>>>>> origin/dev
    "- Call await tools.submit_answer({ blocks, artifacts }) to deliver structured visuals ('compare', 'table', 'chart', 'shot_chart', 'scatter', 'player_card') and prose. Load visual-artifacts for the component catalog; player_card selects one source row and the host supplies its values and declared units.",
>>>>>>> origin/dev
    "- Include anchors: [{ ref, row, columns }] when citing exact query rows, and omit anchors (or pass anchors: []) for Python model outputs, derived math, CBA rule analysis, or qualitative synthesis.",
    "- Artifact shapes: 'compare' ({ kind: 'compare', title, aName, bName, rows: [{ label, a, b }] }), 'table' ({ kind: 'table', title, columns: [{ key, label, numeric? }], rows }), 'chart' ({ kind: 'chart', title, series: [{ name, values, tone?: 'accent' | 'good' | 'warn' }], unit?, xLabels?, footnote? }), 'shot_chart' ({ kind: 'shot_chart', title, zones: [{ x, y, att, pct }], footnote? } with pct on 0-100 scale), and 'scatter' ({ kind: 'scatter', title, xLabel, yLabel, points: [{ label, x, y, highlight? }], xMid?, yMid?, footnote? }).",
    ].join("\n");
}
=======
    "- Artifact shapes: 'compare' ({ kind: 'compare', title, aName, bName, rows: [{ label, a, b }] }), 'table' ({ kind: 'table', title, columns: [{ key, label, numeric? }], rows }), 'chart' ({ kind: 'chart', title, series: [{ name, values, tone?: 'accent' | 'good' | 'warn' }], unit?, xLabels?, footnote? }), 'shot_chart' ({ kind: 'shot_chart', title, zones: [{ x, y, att, pct, label?, makes?, delta? }], footnote? } with pct on 0-100 scale and optional delta as FG% points vs league; fill zones from get_shot_chart), and 'scatter' ({ kind: 'scatter', title, xLabel, yLabel, points: [{ label, x, y, highlight? }], xMid?, yMid?, footnote? }).",
].join("\n");
>>>>>>> origin/dev

function discoverSkillDirs(cwd: string, agentDir: string): string[] {
    const bundledSkillsDir = fileURLToPath(new URL("../skills", import.meta.url));
    const backendRoot = fileURLToPath(new URL("../../", import.meta.url));
    return Array.from(new Set([
        bundledSkillsDir,
        resolve(backendRoot, "analyst/skills"),
        resolve(cwd, ".agents/skills"),
        resolve(cwd, "backend/analyst/skills"),
        resolve(cwd, "skills"),
        resolve(agentDir, "skills"),
    ])).filter((dir) => existsSync(dir));
}

export async function createAnalystSession({
    cwd,
    agentDir,
    model,
    modelRuntime,
    tools,
    settings = {},
    onSkillLoad,
}: {
    cwd: string;
    agentDir: string;
    model: NonNullable<SessionOptions["model"]>;
    modelRuntime: NonNullable<SessionOptions["modelRuntime"]>;
    tools: NonNullable<SessionOptions["customTools"]>;
    settings?: Parameters<typeof SettingsManager.inMemory>[0];
    onSkillLoad?: (name: string) => void;
}) {
    if (!cwd || !agentDir || !isAbsolute(cwd) || !isAbsolute(agentDir)) {
        throw new TypeError("Explicit absolute private cwd and agentDir are required");
    }
    if (!model || !modelRuntime || !Array.isArray(tools)) {
        throw new TypeError("Explicit model, modelRuntime and trusted tools are required");
    }
    const inputNames = tools.map((tool) => tool.name);
    if (new Set(inputNames).size !== inputNames.length || inputNames.includes("codemode")) {
        throw new TypeError("Analysis tool names must be unique and cannot replace codemode");
    }
    const skillDirs = discoverSkillDirs(cwd, agentDir);
    const discoveredSkills = skillDirs.flatMap((dir) => loadSkillsFromDir({ dir, source: "project" }).skills);
    const uniqueSkills = Array.from(new Map(discoveredSkills.map((s) => [s.name, s])).values());
    const skillsPrompt = uniqueSkills.length > 0 ? formatSkillsForPrompt(uniqueSkills, "indirect").trim() : "";
    const sessionTools = inputNames.includes("load_skill") ? tools : [...tools, loadSkillTool(uniqueSkills, onSkillLoad)];
    const names = sessionTools.map((tool) => tool.name);
    const settingsManager = SettingsManager.inMemory({
        retry: { enabled: true, maxRetries: 6, baseDelayMs: 5000 },
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
        additionalSkillPaths: skillDirs,
        systemPrompt: systemPrompt(),
        appendSystemPrompt: skillsPrompt ? [skillsPrompt] : [],
        extensionFactories: [createCodemodeExtension({ mode: "only", models: false, inlineBudget: 8000 })],
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
        customTools: sessionTools.map((tool) => ({ ...tool, exposure: "codemode" })),
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

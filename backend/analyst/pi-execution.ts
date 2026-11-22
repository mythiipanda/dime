import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { extname, join } from "node:path";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import { createAnalystSession } from "./runtime.js";
import { connectPythonTools, objectValue, sourceEvidenceCard, sourceRecordSchema, sourceOutputSchema, sourceResult, type SourceRecord, type PythonToolsOptions } from "./python-tools.js";
import { priorSourceTool, resolvedRuntime } from "./pi-context.js";
import { createSubmitAnswerTool, submitAnswerSchema, type AnswerSubmission } from "./submit-tool.js";
import { createVerifyAnswerNumbersTool } from "./verify-answer.js";
import type { AssistantMessage, Message } from "@earendil-works/pi-ai";
import { countToolCall, createRunStatusTool, type RunStatusTracker } from "./run-status.js";
import type { AgentSessionEvent } from "@earendil-works/pi-coding-agent";

const WORKSPACE_ARTIFACT_EXTENSIONS = new Set([".parquet", ".csv", ".json", ".md", ".png", ".tsv", ".txt"]);
const WORKSPACE_IGNORED_DIRS = new Set(["node_modules", "__pycache__"]);
const WORKSPACE_ARTIFACT_LIMIT = 40;
const WORKSPACE_MAX_DEPTH = 2;
const ABORT_GRACE_MS = 10_000;
const TRACE_RESULT_PREVIEW_CHARS = 4096;

type TracedResult = Pick<Extract<AnalystEvent, { type: "tool_result" }>, "result" | "result_sha256" | "result_bytes" | "result_truncated">;

function tracedResult(payload: unknown): TracedResult {
    try {
        const serialized = JSON.stringify(payload ?? null);
        return {
            result: serialized.slice(0, TRACE_RESULT_PREVIEW_CHARS),
            result_sha256: createHash("sha256").update(serialized).digest("hex"),
            result_bytes: serialized.length,
            ...(serialized.length > TRACE_RESULT_PREVIEW_CHARS ? { result_truncated: true } : {})
        };
    }
    catch {
        return {};
    }
}
const CODEMODE_STORE_ENTRY_TYPE = "codemode-store";
const CODEMODE_STORE_FILE = "codemode-store.json";
const CODEMODE_STORE_MAX_BYTES = 512 * 1024;

export function codemodeStoreSnapshot(branch: ReadonlyArray<{ type: string }>): Record<string, unknown> {
    const store = new Map<string, unknown>();
    for (const entry of branch) {
        if (entry.type !== "custom")
            continue;
        const custom = entry as { customType?: string; data?: unknown };
        if (custom.customType !== CODEMODE_STORE_ENTRY_TYPE)
            continue;
        const data = objectValue(custom.data);
        if (!data)
            continue;
        if (Array.isArray(data.delete))
            for (const key of data.delete)
                if (typeof key === "string")
                    store.delete(key);
        const set = objectValue(data.set);
        if (!set)
            continue;
        for (const [key, value] of Object.entries(set))
            store.set(key, value);
    }
    return Object.fromEntries(store);
}

function readStoredSnapshot(dir: string): Record<string, unknown> | undefined {
    try {
        const value: unknown = JSON.parse(readFileSync(join(dir, CODEMODE_STORE_FILE), "utf8"));
        const snapshot = objectValue(value);
        return snapshot && Object.keys(snapshot).length > 0 ? snapshot : undefined;
    }
    catch {
        return undefined;
    }
}

function persistStoreSnapshot(dir: string, snapshot: Record<string, unknown>): void {
    try {
        const path = join(dir, CODEMODE_STORE_FILE);
        if (Object.keys(snapshot).length === 0) {
            if (existsSync(path))
                unlinkSync(path);
            return;
        }
        const json = JSON.stringify(snapshot);
        if (json.length > CODEMODE_STORE_MAX_BYTES)
            return;
        writeFileSync(path, json);
    }
    catch {
    }
}

export function analystEventFrom(event: AgentSessionEvent): AnalystEvent | undefined {
    if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta")
        return { type: "token", text: event.assistantMessageEvent.delta };
    if (event.type === "auto_retry_start")
        return { type: "tool_call", name: "provider_retry" };
    if (event.type === "auto_retry_end")
        return { type: "tool_result", name: "provider_retry", status: event.success ? "ok" : "fail", error: event.finalError };
    return undefined;
}

export type WorkspaceArtifact = {
    path: string;
    bytes: number;
};

function walkWorkspaceArtifacts(dir: string, prefix: string, depth: number, out: WorkspaceArtifact[]): void {
    let entries;
    try {
        entries = readdirSync(dir, { withFileTypes: true });
    }
    catch {
        return;
    }
    for (const entry of entries) {
        if (entry.name.startsWith("."))
            continue;
        const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
        const fullPath = join(dir, entry.name);
        if (entry.isDirectory()) {
            if (!WORKSPACE_IGNORED_DIRS.has(entry.name) && depth < WORKSPACE_MAX_DEPTH)
                walkWorkspaceArtifacts(fullPath, rel, depth + 1, out);
            continue;
        }
        if (!entry.isFile() || !WORKSPACE_ARTIFACT_EXTENSIONS.has(extname(entry.name).toLowerCase()))
            continue;
        try {
            out.push({ path: rel, bytes: statSync(fullPath).size });
        }
        catch {
        }
    }
}

export function listWorkspaceArtifacts(cwd: string): WorkspaceArtifact[] {
    if (!cwd)
        return [];
    const items: WorkspaceArtifact[] = [];
    walkWorkspaceArtifacts(cwd, "", 0, items);
    items.sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
    return items.slice(0, WORKSPACE_ARTIFACT_LIMIT);
}

const TEAM_ABBREV_TO_ID: Record<string, number> = {
    atl: 1610612737, bos: 1610612738, bkn: 1610612751, cha: 1610612766,
    chi: 1610612741, cle: 1610612739, dal: 1610612742, den: 1610612743,
    det: 1610612765, gsw: 1610612744, hou: 1610612745, ind: 1610612754,
    lac: 1610612746, lal: 1610612747, mem: 1610612763, mia: 1610612748,
    mil: 1610612749, min: 1610612750, nop: 1610612740, nyk: 1610612752,
    okc: 1610612760, orl: 1610612753, phi: 1610612755, phx: 1610612756,
    por: 1610612757, sac: 1610612758, sas: 1610612759, tor: 1610612761,
    uta: 1610612762, was: 1610612764,
};

const TEAM_ARG_KEYS = new Set(["team", "team_id", "team_abbr", "teams", "opponent", "opponent_team", "home_team", "away_team"]);

const TEAM_KEY_CANON: Record<string, string> = { team_id: "team", team_abbr: "team" };

function normalizeTeamArgValue(raw: string): string | undefined {
    const lower = raw.trim().toLowerCase();
    if (!lower) return "";
    const single = TEAM_ABBREV_TO_ID[lower];
    if (single) return `tid:${single}`;
    if (/^\d{10}$/.test(lower)) return `tid:${Number(lower)}`;
    const parts = lower.split(",").map(part => part.trim()).filter(Boolean);
    if (parts.length > 1) {
        const ids = parts.map(part => TEAM_ABBREV_TO_ID[part]);
        if (ids.every(id => id !== undefined))
            return `tid:${(ids as number[]).sort((a, b) => a - b).join("+")}`;
    }
    return lower;
}

function normalizeLoopArgValue(key: string | null, value: unknown): unknown {
    if (typeof value === "string") {
        const trimmed = value.trim();
        if (key && TEAM_ARG_KEYS.has(key))
            return normalizeTeamArgValue(trimmed);
        return trimmed.toLowerCase();
    }
    if (typeof value === "number" && key && TEAM_ARG_KEYS.has(key) && value > 1e9)
        return `tid:${value}`;
    if (Array.isArray(value))
        return value.map(item => normalizeLoopArgValue(null, item));
    if (value !== null && typeof value === "object") {
        const out: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
            const normalized = normalizeLoopArgValue(k, v);
            if (normalized === "" || normalized === null || normalized === undefined)
                continue;
            out[TEAM_KEY_CANON[k] ?? k] = normalized;
        }
        return out;
    }
    return value;
}

export function normalizeLoopArgs(args: unknown): unknown {
    return normalizeLoopArgValue(null, args);
}

export function canonicalArgsKey(value: unknown): string {
    if (value === null || typeof value !== "object")
        return JSON.stringify(value) ?? "null";
    if (Array.isArray(value))
        return "[" + value.map(item => canonicalArgsKey(item)).join(",") + "]";
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    const parts: string[] = [];
    for (const key of keys) {
        if (obj[key] !== undefined)
            parts.push(`${JSON.stringify(key)}:${canonicalArgsKey(obj[key])}`);
    }
    return "{" + parts.join(",") + "}";
}

const turnSchema = Type.Object({
    role: Type.Union([Type.Literal("user"), Type.Literal("assistant")]),
    content: Type.String(),
    reasoning: Type.Optional(Type.String())
});
export const analystContextSchema = Type.Object({
    q: Type.String({ minLength: 1 }), history: Type.Array(turnSchema, { maxItems: 24 }), model: Type.Unknown(), runTimeoutMs: Type.Optional(Type.Number({ minimum: 1 })),
    sources: Type.Optional(Type.Array(sourceRecordSchema)),
    submissions: Type.Optional(Type.Array(Type.Object({ run_id: Type.String(), submission: submitAnswerSchema }, { additionalProperties: false }), { maxItems: 8 })),
    cwd: Type.String(), agentDir: Type.String(),
    bridge: Type.Object({ python: Type.String(), cwd: Type.String(), env: Type.Record(Type.String(), Type.String()) }),
});
export type AnalystContext = Static<typeof analystContextSchema>;
export type AnalystEvent = {
    type: "token";
    text: string;
} | {
    type: "tool_call";
    name: string;
    args?: unknown;
} | {
    type: "tool_result";
    name: string;
    status: "ok" | "fail";
    error?: string;
    rows?: number;
    result?: string;
    result_sha256?: string;
    result_bytes?: number;
    result_truncated?: boolean;
} | {
    type: "source";
    record: SourceRecord;
} | {
    type: "answer";
    text: string;
    submission?: AnswerSubmission;
    reasoning?: string;
} | {
    type: "custom_data";
    tables?: Array<Record<string, unknown>>;
    artifacts?: Array<Record<string, unknown>>;
    unverified_numbers?: Array<number | string>;
} | {
    type: "failure";
    kind: string;
    message: string;
} | {
    type: "closed";
    pid?: number;
};

type AnalystDeps = {
    resolveRuntime?: typeof resolvedRuntime;
    connectTools?: (options: PythonToolsOptions) => ReturnType<typeof connectPythonTools>;
    abortGraceMs?: number;
    budgetNudgeDelayMs?: number;
};

const PRIOR_SUBMISSION_ITEM_LIMIT = 24;
const PRIOR_SUBMISSION_TEXT_CHARS = 500;
const PRIOR_SUBMISSIONS_CHARS = 12000;

function compactArtifactValue(value: unknown, depth: number): unknown {
    if (Array.isArray(value)) {
        const items = value.slice(0, PRIOR_SUBMISSION_ITEM_LIMIT).map(item => compactArtifactValue(item, depth + 1));
        if (value.length > PRIOR_SUBMISSION_ITEM_LIMIT)
            items.push(`…${value.length - PRIOR_SUBMISSION_ITEM_LIMIT} more`);
        return items;
    }
    const obj = objectValue(value);
    if (obj) {
        if (depth >= 5)
            return "[object]";
        return Object.fromEntries(Object.entries(obj).map(([key, item]) => [key, compactArtifactValue(item, depth + 1)]));
    }
    if (typeof value === "string" && value.length > PRIOR_SUBMISSION_TEXT_CHARS)
        return value.slice(0, PRIOR_SUBMISSION_TEXT_CHARS) + "…";
    return value;
}

export function compactPriorSubmissions(submissions: ReadonlyArray<{ run_id: string; submission: AnswerSubmission }>) {
    const out: Record<string, unknown>[] = [];
    let budget = PRIOR_SUBMISSIONS_CHARS;
    for (const { run_id, submission } of [...submissions].slice(-8).reverse()) {
        const entry: Record<string, unknown> = {
            run_id,
            blocks: submission.blocks.map(block => ({
                text: block.text.length > PRIOR_SUBMISSION_TEXT_CHARS ? block.text.slice(0, PRIOR_SUBMISSION_TEXT_CHARS) + "…" : block.text,
                ...(block.anchors?.length ? { anchors: block.anchors } : {})
            }))
        };
        if (submission.artifacts?.length)
            entry.artifacts = submission.artifacts.map(artifact => compactArtifactValue(artifact, 0));
        const size = JSON.stringify(entry).length;
        if (out.length > 0 && size > budget)
            break;
        out.push(entry);
        budget -= size;
    }
    return out;
}

function sourceSummary(record: SourceRecord) {
    return sourceEvidenceCard(record);
}

function safeFailureMessage(kind: string, error: unknown, apiKey?: string): string {
    const raw = error instanceof Error ? error.message : String(error ?? "");
    let sanitized = raw.trim();
    if (apiKey && apiKey.length >= 4)
        sanitized = sanitized.split(apiKey).join("[redacted]");
    sanitized = sanitized
        .replace(/\b(Bearer\s+|sk-|gsk_|AIza|xai-|key-)[^\s"']+/gi, "[redacted]")
        .replace(/\s+/g, " ")
        .slice(0, 240);
    return sanitized ? `Dime ${kind} failed: ${sanitized}` : `Dime ${kind} failed.`;
}

function toHistoryMessages(history: AnalystContext["history"], model: { api: AssistantMessage["api"]; provider: string; id: string; compat?: object }): Message[] {
    const requiresReasoning = !!(model.compat && "requiresReasoningContentOnAssistantMessages" in model.compat && model.compat.requiresReasoningContentOnAssistantMessages);
    return history.map(turn => {
        if (turn.role === "user")
            return { role: "user", content: turn.content, timestamp: Date.now() };
        const content: AssistantMessage["content"] = [];
        if (requiresReasoning)
            content.push({ type: "thinking", thinking: turn.reasoning?.trim() || "Reasoning was not retained for this earlier turn.", thinkingSignature: "reasoning_content" });
        content.push({ type: "text", text: turn.content });
        return {
            role: "assistant", content, api: model.api, provider: model.provider, model: model.id,
            usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
            stopReason: "stop", timestamp: Date.now()
        };
    });
}

function buildLoopRecord(
    toolName: string,
    callId: string,
    count: number,
    rawArgs: unknown,
    lastRef?: string
) {
    const error = `Already called ${toolName} ${count} times with equivalent arguments in this run — already called, pivot or finish.`;
    const parsedArgs = objectValue(rawArgs);
    const payload = {
        ok: false,
        loop_detected: true,
        error,
        summary: `Blocked repeated ${toolName} call (#${count}) with equivalent arguments — pivot to a different tool/args or call submit_answer.`,
        args: parsedArgs ? JSON.parse(canonicalArgsKey(parsedArgs)) : {},
        recovery_hint: lastRef
            ? `Reuse prior ref ${lastRef} via tools.read_source, change parameters/SQL, or call submit_answer.`
            : "Change parameters/SQL or call submit_answer.",
        next_actions: ["Inspect prior source ref", "Modify query/parameters", "Call submit_answer"]
    };
    const record: SourceRecord = {
        ref: `loop_${count}_${toolName.replace(/[^a-zA-Z0-9_]/g, "_")}`,
        callId,
        tool: toolName as SourceRecord["tool"],
        ...(parsedArgs ? { args: parsedArgs } : {}),
        response: {
            isError: true,
            structuredContent: payload,
            content: [{ type: "text", text: JSON.stringify(payload) }]
        }
    };
    return { record, payload };
}

const CONSECUTIVE_FAILURE_LIMIT = 5;

function buildBreakerRecord(
    toolName: string,
    callId: string,
    failures: number,
    lastError?: string
) {
    const error = `${toolName} disabled for this run after ${failures} consecutive failed calls`;
    const payload = {
        ok: false,
        circuit_open: true,
        error,
        summary: `${toolName} failed ${failures} calls in a row; it is blocked for the rest of this run.`,
        ...(lastError ? { last_error: lastError } : {}),
        recovery_hint: "Repeated failures mean a data or source limitation, not a transient error. Move on: answer from warehouse tools (sql_exec, run_python, domain tools), note the gap, or call submit_answer with what you have.",
        next_actions: ["Use a different tool", "Note the data gap in the answer", "Call submit_answer"]
    };
    const record: SourceRecord = {
        ref: `breaker_${failures}_${toolName.replace(/[^a-zA-Z0-9_]/g, "_")}`,
        callId,
        tool: toolName as SourceRecord["tool"],
        response: {
            isError: true,
            structuredContent: payload,
            content: [{ type: "text", text: JSON.stringify(payload) }]
        }
    };
    return { record, payload };
}

function wrapBridgeTools(
    tools: Awaited<ReturnType<typeof connectPythonTools>>["tools"],
    results: Map<string, SourceRecord>,
    emit: (event: AnalystEvent) => void,
    tracker: RunStatusTracker
) {
    const traceResults = Boolean(process.env.DIME_TRACE_TOOL_RESULTS);
    const callCounts = new Map<string, { count: number; lastRef?: string }>();
    const lastErrors = new Map<string, { error: string; count: number }>();
    const failStreaks = new Map<string, number>();
    const tripped = new Set<string>();
    return tools.map(tool => ({
        ...tool,
        async execute(...args: Parameters<typeof tool.execute>) {
            tracker.toolCalls += 1;
            emit({ type: "tool_call", name: tool.name, args: args[1] });
            const callId = typeof args[0] === "string" && args[0] ? args[0] : `call_${tracker.toolCalls}`;
            if (tripped.has(tool.name)) {
                const { record, payload } = buildBreakerRecord(tool.name, callId, failStreaks.get(tool.name) ?? 0, lastErrors.get(tool.name)?.error);
                results.set(record.ref, record);
                emit({ type: "source", record });
                emit({ type: "tool_result", name: tool.name, status: "fail", error: payload.error, ...(traceResults ? tracedResult(payload) : {}) });
                return sourceResult(record);
            }
            const key = `${tool.name}:${canonicalArgsKey(normalizeLoopArgs(args[1] ?? {}))}`;
            const entry = callCounts.get(key) ?? { count: 0 };
            entry.count += 1;
            callCounts.set(key, entry);
            if (entry.count >= 3) {
                const { record, payload } = buildLoopRecord(tool.name, callId, entry.count, args[1], entry.lastRef);
                results.set(record.ref, record);
                emit({ type: "source", record });
                emit({ type: "tool_result", name: tool.name, status: "fail", error: payload.error, ...(traceResults ? tracedResult(payload) : {}) });
                return sourceResult(record);
            }
            try {
                const result = await tool.execute(...args);
                if (!Value.Check(sourceOutputSchema, result.structuredContent))
                    throw new Error("Invalid source result");
                entry.lastRef = result.structuredContent.ref;
                const record = results.get(result.structuredContent.ref);
                if (!record)
                    throw new Error("Tool result has no source record");
                emit({ type: "source", record });
                const domain = objectValue(result.structuredContent.result);
                const failed = result.structuredContent.isError;
                const error = domain?.error;
                if (failed) {
                    const streak = (failStreaks.get(tool.name) ?? 0) + 1;
                    failStreaks.set(tool.name, streak);
                    if (streak >= CONSECUTIVE_FAILURE_LIMIT) {
                        tripped.add(tool.name);
                        const { record, payload } = buildBreakerRecord(tool.name, callId, streak, typeof error === "string" ? error : undefined);
                        results.set(record.ref, record);
                        emit({ type: "source", record });
                        emit({ type: "tool_result", name: tool.name, status: "fail", error: payload.error, ...(traceResults ? tracedResult(payload) : {}) });
                        return sourceResult(record);
                    }
                }
                else
                    failStreaks.delete(tool.name);
                if (failed && domain) {
                    const errorText = typeof error === "string" ? error : "Tool failed";
                    const previous = lastErrors.get(tool.name);
                    const count = previous && previous.error === errorText ? previous.count + 1 : 1;
                    lastErrors.set(tool.name, { error: errorText, count });
                    if (count >= 2) {
                        domain.repeated_error = `Same error as ${count - 1} earlier ${tool.name} call(s) in this run`;
                        domain.recovery_hint = "Treat as a data limitation: note the gap and move to the next sub-question instead of retrying.";
                        result.content = [{ type: "text", text: JSON.stringify(domain) }];
                    }
                }
                else if (!failed)
                    lastErrors.delete(tool.name);
                emit({
                    type: "tool_result", name: tool.name, status: failed ? "fail" : "ok",
                    ...(failed ? { error: typeof error === "string" ? error : "Tool failed" } : {}),
                    ...(Array.isArray(domain?.rows) ? { rows: domain.rows.length } : {}),
                    ...(traceResults ? tracedResult(domain) : {})
                });
                return result;
            }
            catch (error) {
                const streak = (failStreaks.get(tool.name) ?? 0) + 1;
                failStreaks.set(tool.name, streak);
                if (streak >= CONSECUTIVE_FAILURE_LIMIT)
                    tripped.add(tool.name);
                emit({ type: "tool_result", name: tool.name, status: "fail", error: error instanceof Error ? error.message : String(error) });
                throw error;
            }
        }
    }));
}

export function createPiExecution(deps: AnalystDeps = {}) {
    const resolveRuntime = deps.resolveRuntime ?? resolvedRuntime;
    const connectTools = deps.connectTools ?? connectPythonTools;
    const abortGraceMs = deps.abortGraceMs ?? ABORT_GRACE_MS;
    const budgetNudgeDelayMs = deps.budgetNudgeDelayMs;
    return {
        async *stream(input: unknown, signal?: AbortSignal): AsyncGenerator<AnalystEvent> {
            const controller = new AbortController();
            const events: AnalystEvent[] = [];
            let wake: (() => void) | undefined;
            let finished = false;
            const emit = (event: AnalystEvent) => { events.push(event); wake?.(); };
            let acceptedSubmission: AnswerSubmission | undefined;
            let answerEmitted = false;
            const emitAcceptedAnswer = () => {
                if (answerEmitted || !acceptedSubmission)
                    return;
                answerEmitted = true;
                const canonicalText = acceptedSubmission.blocks.map(block => block.text).join("\n\n");
                emit({ type: "answer", text: canonicalText, submission: acceptedSubmission });
            };
            const onAbort = () => { emitAcceptedAnswer(); controller.abort(); };
            signal?.addEventListener("abort", onAbort, { once: true });
            let abandoned = false;
            const abandon = new Promise<void>(resolve => controller.signal.addEventListener("abort", () => setTimeout(resolve, abortGraceMs).unref(), { once: true }));
            void abandon.then(() => { abandoned = true; wake?.(); });
            if (signal?.aborted)
                controller.abort();
            async function run() {
                let session: Awaited<ReturnType<typeof createAnalystSession>> | undefined;
                let bridge: Awaited<ReturnType<typeof connectPythonTools>> | undefined;
                let kind = "configuration";
                let bridgeCwd: string | undefined;
                let bridgePid: number | undefined;
                let modelApiKey: string | undefined;
                let budgetNudge: ReturnType<typeof setTimeout> | undefined;
                const startedAt = Date.now();
                const cancel = () => { void session?.abort(); };
                controller.signal.addEventListener("abort", cancel, { once: true });
                try {
                    if (!Value.Check(analystContextSchema, input) || !input.q.trim())
                        throw new Error("Invalid product context");
                    const start = input;
                    bridgeCwd = start.bridge.cwd;
                    modelApiKey = objectValue(start.model)?.apiKey as string | undefined;
                    const { runtime, model } = await resolveRuntime(start.model);
                    controller.signal.throwIfAborted();
                    kind = "startup";
                    bridge = await connectTools(start.bridge);
                    bridgePid = bridge.pid;
                    controller.signal.throwIfAborted();
                    const connected = bridge;
                    const tracker: RunStatusTracker = {
                        startedAt,
                        budgetMs: start.runTimeoutMs,
                        toolCalls: 0,
                        sourceCount: () => (start.sources?.length ?? 0) + connected.results.size,
                        submitted: false,
                    };
                    const submitTool = createSubmitAnswerTool(
                        () => [...(start.sources ?? []), ...connected.results.values()],
                        (submission) => {
                            tracker.submitted = true;
                            acceptedSubmission = submission;
                            if (submission.artifacts && submission.artifacts.length > 0)
                                emit({ type: "custom_data", artifacts: submission.artifacts });
                        }
                    );
                    const verifyTool = createVerifyAnswerNumbersTool(
                        () => [...(start.sources ?? []), ...connected.results.values()]
                    );
                    session = await createAnalystSession({
                        cwd: start.cwd, agentDir: start.agentDir, model, modelRuntime: runtime,
                        tools: [
                            ...wrapBridgeTools(bridge.tools, connected.results, emit, tracker),
                            countToolCall(priorSourceTool(start.sources ?? []), tracker),
                            verifyTool,
                            countToolCall(submitTool, tracker),
                            countToolCall(createRunStatusTool(tracker), tracker),
                        ],
                        onSkillLoad: () => {
                            tracker.toolCalls += 1;
                            emit({ type: "tool_call", name: "load_skill" });
                            emit({ type: "tool_result", name: "load_skill", status: "ok" });
                        }
                    });
                    controller.signal.throwIfAborted();
                    session.subscribe(event => {
                        const mapped = analystEventFrom(event);
                        if (mapped)
                            emit(mapped);
                    });
                    const history = toHistoryMessages(start.history, model);
                    for (const message of history)
                        session.sessionManager.appendMessage(message);
                    session.agent.state.messages = [...session.agent.state.messages, ...history];
                    if (start.sources?.length) {
                        const context: Message = { role: "user", content: "Prior source evidence cards. Use tools.read_source({ref}) inside codemode and return only filtered results; cards omit full rows:\n" + JSON.stringify(start.sources.map(sourceSummary)), timestamp: Date.now() };
                        session.sessionManager.appendMessage(context);
                        session.agent.state.messages.push(context);
                    }
                    const restoredStore = readStoredSnapshot(start.bridge.cwd);
                    if (restoredStore)
                        session.sessionManager.appendCustomEntry(CODEMODE_STORE_ENTRY_TYPE, { set: restoredStore, delete: [] });
                    const priorSubmissions = start.submissions?.length ? compactPriorSubmissions(start.submissions) : [];
                    if (priorSubmissions.length > 0) {
                        const submissionsContext: Message = {
                            role: "user",
                            content: "Prior submitted answers and artifacts in this thread, most recent first (compact specs). These are reference material for resolving references like 'the earlier table' or 'that player' - never re-emit or restate their artifacts or numbers in the new submission unless the user's current question explicitly asks for the earlier output. Reuse or extend a prior spec only when the question refers to it; otherwise build fresh artifacts for the current answer only:\n" + JSON.stringify(priorSubmissions),
                            timestamp: Date.now()
                        };
                        session.sessionManager.appendMessage(submissionsContext);
                        session.agent.state.messages.push(submissionsContext);
                    }
                    const workspaceFiles = listWorkspaceArtifacts(start.bridge.cwd);
                    if (workspaceFiles.length > 0) {
                        const workspaceContext: Message = {
                            role: "user",
                            content: "Thread workspace files available in run_python cwd:\n" + JSON.stringify(workspaceFiles),
                            timestamp: Date.now()
                        };
                        session.sessionManager.appendMessage(workspaceContext);
                        session.agent.state.messages.push(workspaceContext);
                    }
                    if (start.runTimeoutMs !== undefined) {
                        const budgetContext: Message = {
                            role: "user",
                            content: `Host run budget: ${Math.round(start.runTimeoutMs / 1000)}s (${Math.round(start.runTimeoutMs)}ms total). The host aborts this run when it expires; tools.run_status({}) reports elapsed and remaining budget.`,
                            timestamp: Date.now()
                        };
                        session.sessionManager.appendMessage(budgetContext);
                        session.agent.state.messages.push(budgetContext);
                        const runTimeoutMs = start.runTimeoutMs;
                        const nudgeAtMs = budgetNudgeDelayMs ?? Math.max(5000, Math.min(runTimeoutMs * 0.85, runTimeoutMs - 30000));
                        const agent = session.agent;
                        budgetNudge = setTimeout(() => {
                            if (acceptedSubmission)
                                return;
                            const remaining = Math.max(0, Math.round((runTimeoutMs - (Date.now() - startedAt)) / 1000));
                            agent.steer({
                                role: "user",
                                content: `Host run budget nearly exhausted (~${remaining}s remaining before abort). Call tools.submit_answer now with the verified partial work and list the uncovered sub-questions in its omitted field — a verified partial answer beats no answer. Skip this only if submit_answer already ran.`,
                                timestamp: Date.now()
                            });
                        }, nudgeAtMs);
                        budgetNudge.unref();
                    }
                    kind = "model";
                    await session.prompt(start.q);
                    controller.signal.throwIfAborted();
                    const last = session.messages.filter(m => m.role === "assistant").at(-1);
                    if (!last || last.stopReason === "error" || last.stopReason === "aborted") {
                        const detail = last && "errorMessage" in last && typeof last.errorMessage === "string" ? last.errorMessage : "";
                        throw new Error(detail || "Model failed");
                    }
                    const text = last.content.filter(c => c.type === "text").map(c => c.text).join("");
                    const reasoning = last.content.flatMap(block => block.type === "thinking" ? [block.thinking] : []).join("\n").trim();
                    const replayReasoning = reasoning ? { reasoning } : {};
                    if (acceptedSubmission) {
                        const canonicalText = acceptedSubmission.blocks.map(b => b.text).join("\n\n");
                        emit({ type: "answer", text: canonicalText, submission: acceptedSubmission, ...replayReasoning });
                    } else {
                        const last = session.messages.filter(m => m.role === "assistant").at(-1);
                        if (!last || last.stopReason === "error" || last.stopReason === "aborted") {
                            const detail = last && "errorMessage" in last && typeof last.errorMessage === "string" ? last.errorMessage : "";
                            throw new Error(detail || "Model failed");
                        }
                        const text = last.content.filter(c => c.type === "text").map(c => c.text).join("");
                        if (!text.trim())
                            throw new Error("Model returned no answer");
                        emit({ type: "answer", text, ...replayReasoning });
                    }
                }
                catch (error) {
                    emitAcceptedAnswer();
                    if (!answerEmitted && !controller.signal.aborted)
                        emit({ type: "failure", kind, message: safeFailureMessage(kind, error, modelApiKey) });
                }
                finally {
                    if (budgetNudge)
                        clearTimeout(budgetNudge);
                    try {
                        if (session && bridgeCwd)
                            persistStoreSnapshot(bridgeCwd, codemodeStoreSnapshot(session.sessionManager.getBranch()));
                    }
                    catch {
                    }
                    try {
                        await session?.abort();
                    }
                    finally {
                        session?.dispose();
                        await bridge?.close();
                        controller.signal.removeEventListener("abort", cancel);
                        emit({ type: "closed", pid: bridgePid });
                    }
                }
            }
            const pending = run().finally(() => { finished = true; wake?.(); });
            try {
                while ((!finished && !abandoned) || events.length) {
                    const next = events.shift();
                    if (next)
                        yield next;
                    else
                        await new Promise<void>(resolve => { wake = resolve; });
                }
                await Promise.race([pending, abandon]);
            }
            finally {
                controller.abort();
                await Promise.race([pending, abandon]);
                signal?.removeEventListener("abort", onAbort);
            }
        }
    };
}

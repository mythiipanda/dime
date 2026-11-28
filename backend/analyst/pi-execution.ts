import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { extname, join } from "node:path";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import { createAnalystSession } from "./runtime.js";
import { connectPythonTools, objectValue, sourceEvidenceCard, sourceRecordSchema, sourceOutputSchema, sourceResult, type SourceRecord, type PythonToolsOptions } from "./python-tools.js";
import { priorSourceTool, resolvedRuntime } from "./pi-context.js";
import { artifactRejectionReason, createSubmitAnswerTool, resolveSalvagedArtifacts, submitAnswerSchema, type AnswerSubmission, stripToolCallMarkup } from "./submit-tool.js";
import { auditAnswerNumbers, auditLimitationClaims, createVerifyAnswerNumbersTool, isCapAsk, isDataAsk, limitationChallengeAdvisory, loadWarehouseInventory, missingRequiredTables, WAREHOUSE_TABLE_RE, ZERO_EVIDENCE_DATA_ASK_FLAG } from "./verify-answer.js";
import type { AssistantMessage, Message } from "@earendil-works/pi-ai";
import { countToolCall, createRunStatusTool, type RunStatusTracker } from "./run-status.js";
import type { AgentSessionEvent } from "@earendil-works/pi-coding-agent";

const WORKSPACE_ARTIFACT_EXTENSIONS = new Set([".parquet", ".csv", ".json", ".md", ".png", ".tsv", ".txt"]);
const WORKSPACE_IGNORED_DIRS = new Set(["node_modules", "__pycache__"]);
const WORKSPACE_ARTIFACT_LIMIT = 40;
const TURN_END_STEER_MIN_CHARS = 240;
const SUBMIT_FORCE_REMAINING_MS = 60_000;
const WORKSPACE_MAX_DEPTH = 2;
const ABORT_GRACE_MS = 10_000;
const HARD_KILL_GRACE_MS = 5_000;
const ABANDON_SENTINEL = Symbol("abandon-sentinel");
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

function salvageDraftSubmission(snapshot: Record<string, unknown>): AnswerSubmission | undefined {
    let best: { text: string; anchors: [] }[] | undefined;
    let bestLen = 0;
    const candidates: unknown[] = [];
    for (const value of Object.values(snapshot)) {
        if (Array.isArray(value)) {
            candidates.push(value);
            continue;
        }
        const record = objectValue(value);
        if (!record)
            continue;
        for (const [nestedKey, nested] of Object.entries(record))
            if (Array.isArray(nested) && /block|answer|draft|submission|final/i.test(nestedKey))
                candidates.push(nested);
    }
    for (const value of candidates) {
        if (!Array.isArray(value) || value.length === 0 || value.length > 12)
            continue;
        const items = value.map(objectValue).filter((item): item is Record<string, unknown> => item !== undefined);
        if (items.length !== value.length || !items.every(item => typeof item.text === "string" && item.text.trim().length >= 40))
            continue;
        const total = items.reduce((n, item) => n + (item.text as string).trim().length, 0);
        if (total >= 200 && total > bestLen) {
            bestLen = total;
            best = items.map(item => ({ text: stripToolCallMarkup((item.text as string).trim()), anchors: [] as [] })).filter(block => block.text.length > 0);
        }
    }
    if (!best)
        return undefined;
    const artifacts = salvageDraftArtifacts(snapshot);
    return { blocks: best, omitted: ["submission salvaged from the codemode store draft — the run ended before submit_answer completed"], ...(artifacts ? { artifacts } : {}) };
}

function salvageDraftArtifacts(snapshot: Record<string, unknown>): Record<string, unknown>[] | undefined {
    const out: Record<string, unknown>[] = [];
    const scan = (arr: unknown) => {
        if (!Array.isArray(arr) || arr.length === 0 || arr.length > 8)
            return;
        const items = arr.map(objectValue).filter((item): item is Record<string, unknown> => item !== undefined);
        if (items.length !== arr.length || !items.every(item => typeof item.kind === "string"))
            return;
        for (const item of items) {
            if (artifactRejectionReason(item) !== null)
                continue;
            if (!out.some(existing => JSON.stringify(existing) === JSON.stringify(item)))
                out.push(item);
        }
    };
    for (const value of Object.values(snapshot)) {
        if (Array.isArray(value)) {
            scan(value);
            continue;
        }
        const record = objectValue(value);
        if (!record)
            continue;
        for (const nested of Object.values(record)) {
            if (Array.isArray(nested))
                scan(nested);
            else
                scan([nested]);
        }
        if (typeof record.kind === "string")
            scan([record]);
    }
    return out.length > 0 ? out.slice(0, 4) : undefined;
}

function salvageNarrationSubmission(messages: ReadonlyArray<{ role: string; content?: unknown }>): AnswerSubmission | undefined {
    for (let i = messages.length - 1; i >= 0; i--) {
        const message = messages[i];
        if (message.role !== "assistant" || !Array.isArray(message.content))
            continue;
        const text = (message.content as { type: string; text?: string }[])
            .filter(block => block.type === "text" && typeof block.text === "string")
            .map(block => block.text as string)
            .join("")
            .trim();
        const cleaned = stripToolCallMarkup(text);
        if (cleaned.length >= 200)
            return { blocks: [{ text: cleaned, anchors: [] }], omitted: ["submission salvaged from the final narration — the run ended before submit_answer completed"] };
    }
    return undefined;
}


function mergedStoreSnapshot(branchSnapshot: Record<string, unknown>, dir: string | undefined): Record<string, unknown> {
    const fileSnapshot = (dir ? readStoredSnapshot(dir) : undefined) ?? {};
    return { ...branchSnapshot, ...fileSnapshot };
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

function isSeasonKey(key: string): boolean {
    return key === "season" || key === "seasons" || key.endsWith("_season");
}

function normalizeSeasonArgValue(value: number | string): string | number {
    const text = typeof value === "number" && Number.isInteger(value) ? String(value) : typeof value === "string" ? value.trim() : null;
    if (text && /^\d{4}(-\d{4})?$/.test(text)) {
        const start = text.slice(0, 4);
        return `${start}-${String(Number(start) + 1).slice(2)}`;
    }
    return value;
}

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
        if (key && isSeasonKey(key)) {
            const season = normalizeSeasonArgValue(trimmed);
            return typeof season === "string" ? season.toLowerCase() : season;
        }
        return trimmed.toLowerCase();
    }
    if (typeof value === "number" && key && TEAM_ARG_KEYS.has(key) && value > 1e9)
        return `tid:${value}`;
    if (typeof value === "number" && key && isSeasonKey(key))
        return normalizeSeasonArgValue(value);
    if (Array.isArray(value))
        return value.map(item => normalizeLoopArgValue(key, item));
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
    type: "status";
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
    retryTimeBudgetMs?: number;
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

const RATE_LIMIT_EVIDENCE = /(rate.?limit|too many (tokens|requests)|token[s]? per minute|\b429\b|quota exceeded|token_quota)/i;

export function isRateLimitEvidence(text: string): boolean {
    return RATE_LIMIT_EVIDENCE.test(text);
}

export function classifyFailureKind(kind: string, error: unknown, session: { messages: ReadonlyArray<{ role?: unknown; errorMessage?: unknown }> } | null | undefined, extraEvidence?: string): string {
    if (kind !== "model")
        return kind;
    const parts: string[] = [error instanceof Error ? error.message : String(error ?? "")];
    if (extraEvidence)
        parts.push(extraEvidence);
    if (session) {
        for (const message of session.messages) {
            if (message.role === "assistant" && typeof message.errorMessage === "string")
                parts.push(message.errorMessage);
        }
    }
    return parts.some(part => isRateLimitEvidence(part)) ? "quota" : kind;
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
    const replayThinking = !!(model.compat && (("requiresReasoningContentOnAssistantMessages" in model.compat && model.compat.requiresReasoningContentOnAssistantMessages) || ("requiresThinkingAsText" in model.compat && model.compat.requiresThinkingAsText)));
    return history.map(turn => {
        if (turn.role === "user")
            return { role: "user", content: turn.content, timestamp: Date.now() };
        const content: AssistantMessage["content"] = [];
        if (replayThinking)
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
    lastRef?: string,
    lastError?: string
) {
    const error = lastError
        ? `${toolName} keeps failing after ${count} equivalent calls (${lastError}) — do not retry it; pivot to a different tool or arguments, or call submit_answer.`
        : `Already called ${toolName} ${count} times with equivalent arguments in this run — already called, pivot or finish.`;
    const parsedArgs = objectValue(rawArgs);
    const payload = {
        ok: false,
        loop_detected: true,
        repeated_failure: Boolean(lastError),
        error,
        summary: lastError
            ? `Blocked repeated ${toolName} call (#${count}) — it failed every time with equivalent arguments; retrying is wasted. Pivot now.`
            : `Blocked repeated ${toolName} call (#${count}) with equivalent arguments — pivot to a different tool/args or call submit_answer.`,
        args: parsedArgs ? JSON.parse(canonicalArgsKey(parsedArgs)) : {},
        ...(lastError ? { last_error: lastError } : {}),
        recovery_hint: lastError
            ? "This call cannot succeed with these arguments. Change parameters/SQL, switch tools (warehouse_schema, run_python, another domain tool), or call submit_answer noting the gap."
            : lastRef
                ? `Reuse prior ref ${lastRef} via tools.read_source, change parameters/SQL, or call submit_answer.`
                : "Change parameters/SQL or call submit_answer.",
        next_actions: lastError
            ? ["Change arguments or tool", "Note the data gap", "Call submit_answer"]
            : ["Inspect prior source ref", "Modify query/parameters", "Call submit_answer"]
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

export type CompositionGate = {
    readonly directiveFired: boolean;
    readonly lifted: boolean;
    readonly evidenceSeen: boolean;
    noteEvidence(): void;
    fireDirective(): boolean;
    recordDataCall(): "allow" | "block";
    recordSubmitAttempt(): void;
};

export const COMPOSITION_GATE_CALLS_AFTER_DIRECTIVE = 3;

export function createCompositionGate(): CompositionGate {
    let directiveFired = false;
    let lifted = false;
    let evidenceSeen = false;
    let dataCallsAfterDirective = 0;
    return {
        get directiveFired() { return directiveFired; },
        get lifted() { return lifted; },
        get evidenceSeen() { return evidenceSeen; },
        noteEvidence() { evidenceSeen = true; },
        fireDirective() {
            if (directiveFired || lifted || !evidenceSeen)
                return false;
            directiveFired = true;
            return true;
        },
        recordDataCall() {
            if (!directiveFired || lifted)
                return "allow";
            dataCallsAfterDirective += 1;
            return dataCallsAfterDirective > COMPOSITION_GATE_CALLS_AFTER_DIRECTIVE ? "block" : "allow";
        },
        recordSubmitAttempt() { lifted = true; },
    };
}

function buildCompositionGateRecord(toolName: string, callId: string) {
    const error = "composition gate: call submit_answer with your current verified partial draft before any further data calls — submission is not final: it banks the partial answer, and you may keep querying and resubmit after it.";
    const payload = {
        ok: false,
        composition_gate: true,
        error,
        summary: "Data tools are paused until you submit the verified partial work already in hand. submit_answer does not end the run — resubmission after revision is unlimited.",
        next_actions: ["Call submit_answer with the verified partial draft now", "Resume data calls freely once any submission attempt is made"]
    };
    const record: SourceRecord = {
        ref: `composition_gate_${toolName.replace(/[^a-zA-Z0-9_]/g, "_")}`,
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

const LOOP_STOP_AFTER_INJECTIONS = 3;
const SUBMIT_AUDIT_MAX_REJECTIONS = 3;

export function flagAcknowledgedByOmissions(flag: string, omitted: string[]): boolean {
    const tokens = flag.toLowerCase().split(/[^a-z0-9]+/).filter(t => t.length >= 3);
    if (tokens.length === 0)
        return false;
    return omitted.some(item => {
        const norm = item.toLowerCase();
        if (norm.includes(flag.toLowerCase()) || flag.toLowerCase().includes(norm))
            return true;
        const hits = tokens.filter(t => norm.includes(t)).length;
        return hits / tokens.length >= 0.6;
    });
}

function intEnv(name: string, fallback: number): number {
    const raw = process.env[name];
    const parsed = raw ? Number.parseInt(raw, 10) : Number.NaN;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function callCeilingLimits(): { warn: number; stop: number } {
    const stop = intEnv("DIME_CALL_CEILING_STOP", 140);
    const warn = Math.min(intEnv("DIME_CALL_CEILING_WARN", 80), stop);
    return { warn, stop };
}

function buildLoopStopRecord(
    toolName: string,
    callId: string,
    count: number
) {
    const error = `Run stopped: ${toolName} called ${count} times with equivalent arguments after repeated pivot warnings.`;
    const payload = {
        ok: false,
        loop_terminated: true,
        stop_reason: "tool_call_loop",
        error,
        summary: `${toolName} kept re-calling with equivalent arguments after ${LOOP_STOP_AFTER_INJECTIONS} pivot warnings — the run is being terminated so it does not burn the remaining budget.`,
        next_actions: ["Call submit_answer with verified partial work"]
    };
    const record: SourceRecord = {
        ref: `loop_stop_${count}_${toolName.replace(/[^a-zA-Z0-9_]/g, "_")}`,
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

function buildCallCeilingRecord(toolName: string, callId: string, count: number) {
    const error = `High tool-call count (${count}) — wrap up and submit verified work now with submit_answer instead of opening new queries.`;
    const payload = {
        ok: false,
        call_ceiling: true,
        error,
        summary: `This run has already spent ${count} tool calls; churning more queries burns the run budget without improving the answer.`,
        next_actions: ["Call submit_answer with verified partial work", "List uncovered sub-questions in its omitted field"]
    };
    const record: SourceRecord = {
        ref: `call_ceiling_${count}_${toolName.replace(/[^a-zA-Z0-9_]/g, "_")}`,
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

function buildCallCeilingStopRecord(toolName: string, callId: string, count: number) {
    const error = `Run stopped: ${count} tool calls in a single run exceeded the churn ceiling. Wrap up verified partial work in the next run.`;
    const payload = {
        ok: false,
        loop_terminated: true,
        stop_reason: "tool_call_churn",
        error,
        summary: `The run kept issuing varied tool calls past the churn ceiling — terminating so it does not burn the remaining budget on dithering.`,
        next_actions: ["Call submit_answer with verified partial work"]
    };
    const record: SourceRecord = {
        ref: `churn_stop_${count}_${toolName.replace(/[^a-zA-Z0-9_]/g, "_")}`,
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

function normalizeSqlIdentity(sql: string): string {
    return sql
        .replace(/--[^\n]*/g, " ")
        .replace(/\/\*[\s\S]*?\*\//g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/[\s;]+$/, "")
        .toLowerCase();
}

function loopArgsKey(toolName: string, rawArgs: unknown): string {
    const plain = rawArgs !== null && typeof rawArgs === "object" && !Array.isArray(rawArgs) ? { ...(rawArgs as Record<string, unknown>) } : {};
    if (toolName === "sql_exec" && typeof plain.sql === "string")
        plain.sql = normalizeSqlIdentity(plain.sql);
    return `${toolName}:${canonicalArgsKey(normalizeLoopArgs(plain))}`;
}

const POOL_ARG_KEY_RE = /^(player|player_name|player_id|name)$/i;
const TEAM_ARG_KEY_RE = /^(team|team_id|team_name|team_abbr|team_abbreviation)$/i;
const TEAM_POOL_TOOLS = new Set(["get_lineup_stats", "get_lineups"]);
const POOL_FANOUT_HINT_AT = 3;

function poolSignature(toolName: string, rawArgs: unknown): { key: string; entity: string; entityKind: "players" | "teams" } | undefined {
    const parsed = objectValue(rawArgs);
    if (!parsed)
        return undefined;
    const argKeyRe = TEAM_POOL_TOOLS.has(toolName) ? TEAM_ARG_KEY_RE : POOL_ARG_KEY_RE;
    let entity: string | undefined;
    for (const [k, v] of Object.entries(parsed)) {
        if (argKeyRe.test(k) && (typeof v === "string" || typeof v === "number") && String(v).trim())
            entity = String(v).trim().toLowerCase();
    }
    if (!entity)
        return undefined;
    return { key: toolName, entity, entityKind: TEAM_POOL_TOOLS.has(toolName) ? "teams" : "players" };
}

const DEFAULT_RETRY_TIME_BUDGET_MS = 90_000;

export function createProviderRetryStormGuard(
    emit: (event: AnalystEvent) => void,
    stopRun: (reason: string) => void,
    onRetryBudget?: (burnedMs: number) => void,
    retryBudgetMs: number = DEFAULT_RETRY_TIME_BUDGET_MS
) {
    let exhausted = 0;
    let retryDelayMs = 0;
    let budgetFired = false;
    return (event: AgentSessionEvent) => {
        if (event.type === "auto_retry_start") {
            retryDelayMs += event.delayMs;
            if (!budgetFired && retryDelayMs >= retryBudgetMs && onRetryBudget) {
                budgetFired = true;
                onRetryBudget(retryDelayMs);
            }
            return;
        }
        if (event.type !== "auto_retry_end" || event.success)
            return;
        exhausted += 1;
        if (exhausted === 1) {
            const detail = typeof event.finalError === "string" && event.finalError ? event.finalError : "provider unavailable";
            stopRun(`Run stopped: provider call exhausted all retries against a saturated lane (${detail}). Retry the task when the provider recovers.`);
        }
    };
}

const WEB_TOOLS = new Set(["web_search", "web_fetch"]);
const SQL_STEER_SKIP_TOOLS = new Set(["sql_exec", "run_python", "web_search", "web_fetch", "warehouse_schema", "get_warehouse_freshness", "load_skill", "run_status"]);
const DATA_PULL_TOOLS = new Set(["sql_exec", "run_python"]);
const DATA_PULL_SYNTH_AT = 12;

type FallbackSpec = { table: string; nameCol?: string; teamCol?: string; seasonCol?: string; seasonText?: boolean; idCol?: string; orderCol?: string };
const TOOL_FALLBACK_TABLE: Record<string, FallbackSpec> = {};
{
    const playerSeasons: FallbackSpec = { table: "silver_hist_player_seasons", nameCol: "player_name", teamCol: "team_abbreviation", seasonCol: "season", idCol: "player_id", orderCol: "season" };
    for (const t of ["get_scouting_report", "get_raptor_history", "get_percentiles", "get_comps", "get_player_report", "get_player_evaluation", "get_player_intel", "get_player_ratings", "get_player_rankings", "get_season_averages", "get_career_arc", "get_career_totals", "get_compare", "get_splits", "get_situational_splits", "get_roster_fit", "get_young_player_usage", "get_impact_rank", "get_impact_estimate", "get_rapm", "get_rapm_prior", "get_award_race", "get_award_results", "get_risers", "get_player_risers", "get_leaderboard_deltas", "get_leaders", "get_historical_leaders", "get_rookie_leaders", "get_clutch_stats", "get_clutch", "get_last_x", "get_trend", "get_streaks", "get_head_to_head", "get_competitive_ratings", "get_debate_card", "get_matchup_brief", "get_opponent_scout", "get_scout_pack", "get_finder", "get_wpa_leaders", "get_hustle_boards", "get_team_leaders"])
        TOOL_FALLBACK_TABLE[t] = playerSeasons;
    const teamSeasons: FallbackSpec = { table: "silver_hist_team_seasons", teamCol: "team_name", seasonCol: "season", orderCol: "season" };
    for (const t of ["get_team_compare", "get_team_season_summary", "get_team_hub", "get_standings", "get_standings_deep", "get_team_splits", "get_team_trajectory", "get_team_daily_brief"])
        TOOL_FALLBACK_TABLE[t] = teamSeasons;
    const draftBoard: FallbackSpec = { table: "silver_draft_boards", nameCol: "PLAYER_NAME", seasonCol: "_season", seasonText: true, orderCol: "\"ORDER\"" };
    for (const t of ["get_draft_board", "get_draft_model", "get_prospect", "get_combine"])
        TOOL_FALLBACK_TABLE[t] = draftBoard;
    TOOL_FALLBACK_TABLE["get_draft_capital"] = { table: "silver_future_picks", teamCol: "ORIG_TEAM", seasonCol: "DRAFT_YEAR" };
    TOOL_FALLBACK_TABLE["get_draft_history"] = { table: "silver_hist_draft", nameCol: "PLAYER_NAME", teamCol: "TEAM_ABBREVIATION", seasonCol: "SEASON", idCol: "PERSON_ID" };
}
const FALLBACK_LIMIT = 25;

function fallbackWhere(spec: FallbackSpec, toolArgs: unknown): string[] {
    const args = (toolArgs && typeof toolArgs === "object" ? toolArgs : {}) as Record<string, unknown>;
    const parts: string[] = [];
    const esc = (v: unknown) => String(v).replace(/'/g, "''");
    for (const [key, raw] of Object.entries(args)) {
        const k = key.toLowerCase();
        if (typeof raw === "number" && (k === "player_id" || k === "person_id")) {
            if (spec.idCol)
                parts.push(`${spec.idCol} = ${Math.trunc(raw)}`);
            continue;
        }
        if (typeof raw !== "string" || !raw.trim())
            continue;
        const v = esc(raw.trim());
        if (spec.nameCol && /player.*name|^name$|^player$/.test(k))
            parts.push(`${spec.nameCol} ILIKE '%${v}%'`);
        else if (spec.teamCol && /team(_(abbreviation|name|abbr))?$|^team$/.test(k))
            parts.push(`${spec.teamCol} ILIKE '%${v}%'`);
        else if (spec.seasonCol && /season|draft_year|^year$/.test(k)) {
            const m = v.match(/^(\d{4})(?:-(\d{2}))?/);
            if (m) {
                const end = m[2] ? Number(m[1]) + 1 : Number(m[1]);
                parts.push(spec.seasonText ? `${spec.seasonCol} = '${end}'` : `${spec.seasonCol} = ${end}`);
            }
        }
    }
    return parts;
}

function fallbackSql(spec: FallbackSpec, toolArgs: unknown): string | null {
    const parts = fallbackWhere(spec, toolArgs);
    if (parts.length === 0)
        return null;
    return `SELECT * FROM ${spec.table} WHERE ${parts.join(" AND ")}${spec.orderCol ? ` ORDER BY ${spec.orderCol} DESC` : ""} LIMIT ${FALLBACK_LIMIT}`;
}

function wrapBridgeTools(
    tools: Awaited<ReturnType<typeof connectPythonTools>>["tools"],
    results: Map<string, SourceRecord>,
    emit: (event: AnalystEvent) => void,
    tracker: RunStatusTracker,
    stopRun: (reason: string) => void,
    question?: string,
    compositionGate?: CompositionGate
) {
    const traceResults = Boolean(process.env.DIME_TRACE_TOOL_RESULTS);
    const callCounts = new Map<string, { count: number; lastRef?: string; lastSuccessRef?: string; lastError?: string; blocked?: number; intercepted?: number }>();
    let sqlInterceptions = 0;
    let stormFired = false;
    const toolTotals = new Map<string, number>();
    let dataPulls = 0;
    const repeatedToolSteered = new Set<string>();
    const lastErrors = new Map<string, { error: string; count: number }>();
    const failStreaks = new Map<string, number>();
    const tripped = new Set<string>();
    const poolSigs = new Map<string, Set<string>>();
    const poolSteered = new Set<string>();
    let capWarehouseSteered = false;
    const namedToolSteered = new Set<string>();
    const capAsk = isCapAsk(question);
    const sqlExecTool = tools.find(t => t.name === "sql_exec");
    const namedToolSqlSteer = async (tool: { name: string }, domain: Record<string, unknown>, result: { content?: unknown }, reason: "failed" | "no_rows", toolArgs: unknown, callArgs: readonly unknown[]) => {
        if (namedToolSteered.has(tool.name) || SQL_STEER_SKIP_TOOLS.has(tool.name))
            return false;
        namedToolSteered.add(tool.name);
        domain.named_tool_steer = reason === "failed"
            ? `${tool.name} failed for this ask. The warehouse usually covers this class directly: run sql_exec over silver_hist_player_seasons (per-player season rows — _season, player_name, team_abbreviation, age, gp, min, pts/reb/ast/stl/blk/tov per game, fg3_pct, ts_pct, usg_pct, off/def/net_rating, pie), silver_hist_team_seasons (team rows with *_rank league ranks), or the draft tables silver_draft_boards, silver_draft_value_curve, silver_future_picks and silver_hist_draft for prospect/pick asks — applying the stated season and pool filter. Scouting, percentile, comp, fit and draft-board asks resolve there instead of through this named tool.`
            : `${tool.name} returned no rows for this ask — a coverage gap, not necessarily an empty answer. The warehouse usually covers this class directly: run sql_exec over silver_hist_player_seasons (per-player season rows — _season, player_name, team_abbreviation, age, gp, min, pts/reb/ast/stl/blk/tov per game, fg3_pct, ts_pct, usg_pct, off/def/net_rating, pie), silver_hist_team_seasons (team rows with *_rank league ranks), or the draft tables silver_draft_boards, silver_draft_value_curve, silver_future_picks and silver_hist_draft for prospect/pick asks — applying the stated season and pool filter.`;
        const spec = TOOL_FALLBACK_TABLE[tool.name];
        const sql = spec ? fallbackSql(spec, toolArgs) : null;
        if (sql && sqlExecTool) {
            emit({ type: "tool_call", name: "named_tool_sql_fallback", args: { tool: tool.name, table: spec!.table, sql } });
            try {
                const fb = await sqlExecTool.execute(`fb_${tool.name}_${tracker.toolCalls}`, { sql }, callArgs[2] as never, callArgs[3] as never, callArgs[4] as never);
                const fbDomain = objectValue((fb?.structuredContent as Record<string, unknown> | undefined)?.result);
                const fbRows = Array.isArray(fbDomain?.rows) ? (fbDomain.rows as unknown[]) : [];
                if (fbRows.length > 0) {
                    domain.warehouse_fallback = {
                        table: spec!.table,
                        sql,
                        rows: fbRows.slice(0, FALLBACK_LIMIT),
                        note: `${tool.name} ${reason === "failed" ? "failed" : "returned no rows"} — these warehouse rows answer the ask directly. Build the answer from them (and further sql_exec over this table for aggregates/percentiles) instead of retrying the named tool.`,
                    };
                }
                emit({ type: "tool_result", name: "named_tool_sql_fallback", status: fbRows.length > 0 ? "ok" : "fail", rows: fbRows.length });
            }
            catch {
                emit({ type: "tool_result", name: "named_tool_sql_fallback", status: "fail", error: "fallback query failed" });
            }
        }
        result.content = [{ type: "text", text: JSON.stringify(domain) }];
        emit({ type: "tool_call", name: "named_tool_sql_steer", args: { tool: tool.name, reason, fallback: Boolean(domain.warehouse_fallback) } });
        emit({ type: "tool_result", name: "named_tool_sql_steer", status: "ok" });
        return true;
    };
    return tools.map(tool => ({
        ...tool,
        async execute(...args: Parameters<typeof tool.execute>) {
            tracker.toolCalls += 1;
            emit({ type: "tool_call", name: tool.name, args: args[1] });
            const callId = typeof args[0] === "string" && args[0] ? args[0] : `call_${tracker.toolCalls}`;
            if (compositionGate && compositionGate.recordDataCall() === "block") {
                const { record, payload } = buildCompositionGateRecord(tool.name, callId);
                results.set(record.ref, record);
                emit({ type: "source", record });
                emit({ type: "tool_result", name: tool.name, status: "fail", error: payload.error, ...(traceResults ? tracedResult(payload) : {}) });
                return sourceResult(record);
            }
            const ceiling = callCeilingLimits();
            if (tracker.toolCalls >= ceiling.stop) {
                const { record, payload } = buildCallCeilingStopRecord(tool.name, callId, tracker.toolCalls);
                results.set(record.ref, record);
                emit({ type: "source", record });
                emit({ type: "tool_result", name: tool.name, status: "fail", error: payload.error, ...(traceResults ? tracedResult(payload) : {}) });
                stopRun(payload.error);
                return sourceResult(record);
            }
            if (tracker.toolCalls === ceiling.warn) {
                const { record, payload } = buildCallCeilingRecord(tool.name, callId, tracker.toolCalls);
                results.set(record.ref, record);
                emit({ type: "source", record });
                emit({ type: "tool_result", name: tool.name, status: "fail", error: payload.error, ...(traceResults ? tracedResult(payload) : {}) });
                return sourceResult(record);
            }
            if (tripped.has(tool.name)) {
                const { record, payload } = buildBreakerRecord(tool.name, callId, failStreaks.get(tool.name) ?? 0, lastErrors.get(tool.name)?.error);
                results.set(record.ref, record);
                emit({ type: "source", record });
                emit({ type: "tool_result", name: tool.name, status: "fail", error: payload.error, ...(traceResults ? tracedResult(payload) : {}) });
                return sourceResult(record);
            }
            const key = loopArgsKey(tool.name, args[1]);
            const entry = callCounts.get(key) ?? { count: 0 };
            entry.count += 1;
            callCounts.set(key, entry);
            if (entry.count >= (tool.name === "run_status" ? 3 : 2)) {
                if (entry.lastSuccessRef) {
                    const prior = results.get(entry.lastSuccessRef);
                    if (prior) {
                        entry.intercepted = (entry.intercepted ?? 0) + 1;
                        let stormNotice = "";
                        if (tool.name === "sql_exec") {
                            sqlInterceptions += 1;
                            if (!stormFired && sqlInterceptions >= 6) {
                                stormFired = true;
                                stormNotice = " You have re-issued already-answered queries repeatedly this run — the data you need is already in the refs in context; analysis goes in run_python, delivery goes in submit_answer. Further duplicate queries will be rejected.";
                                emit({ type: "tool_call", name: "dupe_storm_steer", args: { interceptions: sqlInterceptions } });
                                emit({ type: "tool_result", name: "dupe_storm_steer", status: "ok" });
                            }
                        }
                        if (entry.intercepted === 1) {
                            emit({ type: "tool_result", name: tool.name, status: "ok", result: `reused result of ${entry.lastSuccessRef} — this identical call already ran and the data is unchanged; do not send it again: reuse ref ${entry.lastSuccessRef}, change the arguments, switch tools, or call submit_answer.${stormNotice}` });
                            return sourceResult(prior);
                        }
                        entry.blocked = (entry.blocked ?? 0) + 1;
                        if (entry.blocked > LOOP_STOP_AFTER_INJECTIONS) {
                            const { record, payload } = buildLoopStopRecord(tool.name, callId, entry.count);
                            results.set(record.ref, record);
                            emit({ type: "source", record });
                            emit({ type: "tool_result", name: tool.name, status: "fail", error: payload.error, ...(traceResults ? tracedResult(payload) : {}) });
                            stopRun(payload.error);
                            return sourceResult(record);
                        }
                        const error = `STOP re-issuing this query. The data is already in your context as ${entry.lastSuccessRef}. Your next action must be one of: run_python analysis over the fetched rows, a DIFFERENT sql_exec query, or submit_answer.${stormNotice}`;
                        const parsedArgs = objectValue(args[1]);
                        const payload = {
                            ok: false,
                            loop_detected: true,
                            repeat_interception: true,
                            reused_ref: entry.lastSuccessRef,
                            error,
                            summary: error,
                            args: parsedArgs ? JSON.parse(canonicalArgsKey(parsedArgs)) : {},
                            recovery_hint: `The rows you need are already in context as ${entry.lastSuccessRef}. Analyze them with run_python or deliver with submit_answer.`,
                            next_actions: ["run_python over the fetched rows", "a different sql_exec query", "submit_answer"]
                        };
                        const record: SourceRecord = {
                            ref: `dupe_${entry.count}_${tool.name.replace(/[^a-zA-Z0-9_]/g, "_")}`,
                            callId,
                            tool: tool.name as SourceRecord["tool"],
                            ...(parsedArgs ? { args: parsedArgs } : {}),
                            response: {
                                isError: true,
                                structuredContent: payload,
                                content: [{ type: "text", text: JSON.stringify(payload) }]
                            }
                        };
                        results.set(record.ref, record);
                        emit({ type: "source", record });
                        emit({ type: "tool_result", name: tool.name, status: "fail", error, ...(traceResults ? tracedResult(payload) : {}) });
                        return sourceResult(record);
                    }
                }
                entry.blocked = (entry.blocked ?? 0) + 1;
                if (entry.blocked > LOOP_STOP_AFTER_INJECTIONS) {
                    const { record, payload } = buildLoopStopRecord(tool.name, callId, entry.count);
                    results.set(record.ref, record);
                    emit({ type: "source", record });
                    emit({ type: "tool_result", name: tool.name, status: "fail", error: payload.error, ...(traceResults ? tracedResult(payload) : {}) });
                    stopRun(payload.error);
                    return sourceResult(record);
                }
                const { record, payload } = buildLoopRecord(tool.name, callId, entry.count, args[1], entry.lastRef, entry.lastError);
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
                if (domain && tracker.budgetMs !== undefined)
                    domain.budget_remaining_ms = Math.max(0, Math.round(tracker.budgetMs - (Date.now() - tracker.startedAt)));
                const failed = result.structuredContent.isError;
                const error = domain?.error;
                if (!failed) {
                    entry.lastSuccessRef = record.ref;
                    if (compositionGate && !(Array.isArray(domain?.rows) && (domain.rows as unknown[]).length === 0))
                        compositionGate.noteEvidence();
                }
                else if (typeof error === "string")
                    entry.lastError = error;
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
                    await namedToolSqlSteer(tool, domain, result, "failed", args[1], args);
                }
                else if (failed && !domain)
                    await namedToolSqlSteer(tool, {}, result, "failed", args[1], args);
                else if (!failed)
                    lastErrors.delete(tool.name);
                if (!failed && domain) {
                    if (Array.isArray(domain.rows) && domain.rows.length === 0)
                        await namedToolSqlSteer(tool, domain, result, "no_rows", args[1], args);
                    const total = (toolTotals.get(tool.name) ?? 0) + 1;
                    toolTotals.set(tool.name, total);
                    if (DATA_PULL_TOOLS.has(tool.name)) {
                        dataPulls += 1;
                        domain.data_pulls = dataPulls;
                        if (dataPulls === DATA_PULL_SYNTH_AT) {
                            domain.synthesis_hint = `${dataPulls} data pulls so far — past this point extra queries rarely change the answer. Reuse the refs you already have, write the deliverable, and submit_answer; reach for another query only if the ask names a figure still missing.`;
                            emit({ type: "tool_call", name: "data_pull_synth_steer", args: { count: dataPulls } });
                            emit({ type: "tool_result", name: "data_pull_synth_steer", status: "ok" });
                        }
                        result.content = [{ type: "text", text: JSON.stringify(domain) }];
                    }
                    if (total === 4 && !repeatedToolSteered.has(tool.name) && !SQL_STEER_SKIP_TOOLS.has(tool.name)) {
                        repeatedToolSteered.add(tool.name);
                        const spec = TOOL_FALLBACK_TABLE[tool.name];
                        domain.repeated_tool_steer = spec
                            ? `${tool.name} has now been called ${total} times in this run. Repeated calls to one tool usually mean the ask wants the whole frame, not one slice — one sql_exec over ${spec.table} returns the full cohort; fetch it once and build the deliverable, or submit what you have, instead of enumerating more calls.`
                            : `${tool.name} has now been called ${total} times in this run. Repeated calls to one tool usually mean the ask wants the whole frame, not one slice — one sql_exec query over the relevant silver table returns it; fetch it once and build the deliverable, or submit what you have, instead of enumerating more calls.`;
                        result.content = [{ type: "text", text: JSON.stringify(domain) }];
                        emit({ type: "tool_call", name: "repeated_tool_steer", args: { tool: tool.name, count: total } });
                        emit({ type: "tool_result", name: "repeated_tool_steer", status: "ok" });
                    }
                    if (!capWarehouseSteered && capAsk && WEB_TOOLS.has(tool.name)) {
                        capWarehouseSteered = true;
                        domain.warehouse_steer = "This is a cap/trade question the warehouse answers directly. Prefer the cap tools — get_cap_scenario, get_trade_legality, get_fa_plan, get_draft_capital, get_cap_ledger, get_cap_table — or sql_exec over silver_salaries, silver_cap_room, silver_contracts, silver_future_picks: they carry committed salaries, projected cap/tax/apron lines, and the outgoing/incoming pick ledger. Web search is a fallback only when the warehouse lacks the input (e.g. a live news claim); cite the warehouse figures for the numbers.";
                        result.content = [{ type: "text", text: JSON.stringify(domain) }];
                        emit({ type: "tool_call", name: "cap_warehouse_steer", args: { tool: tool.name } });
                        emit({ type: "tool_result", name: "cap_warehouse_steer", status: "ok" });
                    }
                    const sig = poolSignature(tool.name, args[1]);
                    if (sig) {
                        const seen = poolSigs.get(sig.key) ?? new Set<string>();
                        seen.add(sig.entity);
                        poolSigs.set(sig.key, seen);
                        if (seen.size >= POOL_FANOUT_HINT_AT && !poolSteered.has(sig.key)) {
                            poolSteered.add(sig.key);
                            domain.pool_fanout_hint = sig.entityKind === "teams"
                                ? `${tool.name} has now been called for ${seen.size} different teams — that is a pool enumeration. For league-wide lineup boards, get_lineup_leaders or one sql_exec over silver_hist_lineups (filter _season/season_type/measure_type/per_mode, apply the minutes floor, ORDER BY the rating) returns the whole cohort in a single call; use it for the remaining teams instead of more per-team calls.`
                                : `${tool.name} has now been called for ${seen.size} different players — that is a pool enumeration. For leaderboard/pool-cut asks the whole cohort comes back in one call: shot-diet/zone boards (midrange, rim, corner three, above-the-break volume or efficiency) -> get_shot_zone_leaders with the zone, season, position and min_attempts filters; counting-stat boards -> get_leaders; anything else -> one sql_exec (GROUP BY player, HAVING the min-sample filter, ORDER BY the ranking metric). Use the single-call path for the remaining players instead of more per-player calls.`;
                            result.content = [{ type: "text", text: JSON.stringify(domain) }];
                            emit({ type: "tool_call", name: "pool_fanout_steer", args: sig.entityKind === "teams" ? { tool: tool.name, teams: seen.size } : { tool: tool.name, players: seen.size } });
                            emit({ type: "tool_result", name: "pool_fanout_steer", status: "ok" });
                        }
                    }
                }
                emit({
                    type: "tool_result", name: tool.name, status: failed ? "fail" : "ok",
                    ...(failed ? { error: typeof error === "string" ? error : "Tool failed" } : {}),
                    ...(Array.isArray(domain?.rows) ? { rows: domain.rows.length } : {}),
                    ...(traceResults ? tracedResult(domain) : {})
                });
                return result;
            }
            catch (error) {
                entry.lastError = error instanceof Error ? error.message : String(error);
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
            const events: (AnalystEvent | typeof ABANDON_SENTINEL)[] = [];
            let wake: (() => void) | undefined;
            let finished = false;
            const emit = (event: AnalystEvent) => { events.push(event); wake?.(); };
            let acceptedSubmission: AnswerSubmission | undefined;
            let lastRejectedSubmission: AnswerSubmission | undefined;
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
            void abandon.then(() => { abandoned = true; events.push(ABANDON_SENTINEL); wake?.(); });
            if (signal?.aborted)
                controller.abort();
            async function run() {
                let session: Awaited<ReturnType<typeof createAnalystSession>> | undefined;
                let bridge: Awaited<ReturnType<typeof connectPythonTools>> | undefined;
                let bridgeClosePromise: Promise<unknown> | undefined;
                const closeBridge = () => {
                    if (!bridgeClosePromise && bridge)
                        bridgeClosePromise = bridge.close().catch(() => undefined);
                    return bridgeClosePromise;
                };
                let kind = "configuration";
                let providerErrorEvidence = "";
                let bridgeCwd: string | undefined;
                let bridgePid: number | undefined;
                let modelApiKey: string | undefined;
                let budgetNudge: ReturnType<typeof setTimeout> | undefined;
                let compositionDirective: ReturnType<typeof setTimeout> | undefined;
                let narrationSalvage: ReturnType<typeof setTimeout> | undefined;
                let emittedFromNarration = false;
                let narrationSubmissionRef: unknown;
                const startedAt = Date.now();
                const cancel = () => { void session?.abort(); };
                controller.signal.addEventListener("abort", cancel, { once: true });
                let runSettled = false;
                let hardKillTimer: ReturnType<typeof setTimeout> | undefined;
                controller.signal.addEventListener("abort", () => {
                    hardKillTimer = setTimeout(() => {
                        if (runSettled)
                            return;
                        if (bridgePid !== undefined)
                            try {
                                process.kill(bridgePid, "SIGKILL");
                            }
                            catch {
                            }
                        try {
                            session?.dispose();
                        }
                        catch {
                        }
                    }, HARD_KILL_GRACE_MS);
                    hardKillTimer.unref();
                }, { once: true });
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
                    controller.signal.addEventListener("abort", () => { void closeBridge(); }, { once: true });
                    controller.signal.throwIfAborted();
                    const connected = bridge;
                    const tracker: RunStatusTracker = {
                        startedAt,
                        budgetMs: start.runTimeoutMs,
                        toolCalls: 0,
                        sourceCount: () => (start.sources?.length ?? 0) + connected.results.size,
                        submitted: false,
                    };
                    const compositionGate = createCompositionGate();
                    let submitAuditRejections = 0;
                    let zeroEvidenceRepromptUsed = false;
                    const consultedTables = new Set<string>();
                    const toolArgsText: string[] = [];
                    let dataToolCalls = 0;
                    const submitTool = createSubmitAnswerTool(
                        () => [...(start.sources ?? []), ...connected.results.values()],
                        (submission) => {
                            compositionGate.recordSubmitAttempt();
                            tracker.submitted = true;
                            const rejected = lastRejectedSubmission;
                            if (rejected) {
                                const acceptedText = submission.blocks.map(block => block.text).join("\n\n").trim().length;
                                const rejectedText = rejected.blocks.map(block => block.text).join("\n\n").trim().length;
                                const acceptedArtifacts = submission.artifacts?.length ?? 0;
                                const rejectedArtifacts = rejected.artifacts?.length ?? 0;
                                if (rejectedArtifacts > acceptedArtifacts && rejectedText > acceptedText) {
                                    submission = {
                                        ...rejected,
                                        omitted: [...(rejected.omitted ?? []), "restored the richer audit-rejected draft: the accepted submission was strictly smaller in both prose and artifacts"]
                                    };
                                }
                            }
                            acceptedSubmission = submission;
                            if (submission.artifacts && submission.artifacts.length > 0)
                                emit({ type: "custom_data", artifacts: submission.artifacts });
                        },
                        (submission) => {
                            compositionGate.recordSubmitAttempt();
                            if (submitAuditRejections >= SUBMIT_AUDIT_MAX_REJECTIONS)
                                return null;
                            const audit = auditAnswerNumbers(
                                submission,
                                [...(start.sources ?? []), ...connected.results.values()],
                                start.q,
                                toolArgsText.join(" ")
                            );
                            const omitted = submission.omitted ?? [];
                            const missingArtifacts = audit.missing_in_artifacts
                                .map(claim => {
                                    const near = claim.context.replace(/\s+/g, " ").replace(/\*+/g, "").trim();
                                    const short = near.length > 90 ? near.slice(0, 90).trimEnd() + "…" : near;
                                    return `${claim.raw} — this figure is stated in the prose but appears in no artifact payload; copy it into an artifact row (stated near: "${short}")`;
                                })
                                .filter(flag => !flagAcknowledgedByOmissions(flag, omitted));
                            const uncoveredAsks = audit.uncovered_asks
                                .filter(flag => !flagAcknowledgedByOmissions(flag, omitted));
                            const noArtifacts = audit.no_artifacts_on_artifact_ask
                                .filter(flag => !flagAcknowledgedByOmissions(flag, omitted));
                            const metricGaps = audit.metric_value_gaps
                                .filter(flag => !flagAcknowledgedByOmissions(flag, omitted));
                            const missingTables = missingRequiredTables(start.q, consultedTables)
                                .filter(flag => !flagAcknowledgedByOmissions(flag, omitted));
                            const unsupportedClaims = audit.unsupported_claims
                                .filter(flag => !flagAcknowledgedByOmissions(flag, omitted));
                            const unevidencedAsks = audit.unevidenced_asks
                                .filter(flag => !flagAcknowledgedByOmissions(flag, omitted));
                            const missingEntities = audit.missing_entities
                                .filter(flag => !flagAcknowledgedByOmissions(flag, omitted));
                            const zeroEvidenceOnSubmit = dataToolCalls === 0
                                && (start.sources?.length ?? 0) === 0
                                && connected.results.size === 0
                                && isDataAsk(start.q);
                            if (!zeroEvidenceOnSubmit && missingArtifacts.length === 0 && uncoveredAsks.length === 0 && noArtifacts.length === 0 && metricGaps.length === 0 && missingTables.length === 0 && unsupportedClaims.length === 0 && unevidencedAsks.length === 0 && missingEntities.length === 0)
                                return null;
                            submitAuditRejections += 1;
                            const gaps: Record<string, unknown> = {};
                            if (missingArtifacts.length > 0)
                                gaps.missing_in_artifacts = missingArtifacts;
                            if (uncoveredAsks.length > 0)
                                gaps.uncovered_asks = uncoveredAsks;
                            if (noArtifacts.length > 0)
                                gaps.no_artifacts_on_artifact_ask = noArtifacts;
                            if (missingArtifacts.length > 0 || noArtifacts.length > 0)
                                gaps.artifact_payload_shape = 'a table artifact is {kind:"table", title:"<takeaway>", columns:[{key:"rank",label:"Rank",numeric:true},{key:"player",label:"Player"},{key:"value",label:"Net",numeric:true}], rows:[{rank:1,player:"X",value:4.8}]} — copy each figure stated in blocks into a row; a figure in block text alone does not count';
                            if (metricGaps.length > 0)
                                gaps.metric_value_gaps = metricGaps;
                            if (missingTables.length > 0)
                                gaps.missing_required_tables = missingTables;
                            if (unsupportedClaims.length > 0)
                                gaps.unsupported_claims = unsupportedClaims;
                            if (unevidencedAsks.length > 0)
                                gaps.unevidenced_asks = unevidencedAsks;
                            if (missingEntities.length > 0)
                                gaps.missing_entities = missingEntities;
                            if (zeroEvidenceOnSubmit)
                                gaps.no_evidence_on_data_ask = [ZERO_EVIDENCE_DATA_ASK_FLAG];
                            const limitationAdvisories = auditLimitationClaims(submission, loadWarehouseInventory())
                                .map(challenge => limitationChallengeAdvisory(challenge))
                                .filter(flag => !flagAcknowledgedByOmissions(flag, omitted));
                            if (limitationAdvisories.length > 0)
                                gaps.limitation_challenges = limitationAdvisories;

                            lastRejectedSubmission = submission;
                            emit({ type: "tool_call", name: "submit_answer_audit" });
                            emit({ type: "tool_result", name: "submit_answer_audit", status: "fail", error: JSON.stringify(gaps) });
                            return `Not submitted — the honesty audit still finds unacknowledged gaps (rejection ${submitAuditRejections}/${SUBMIT_AUDIT_MAX_REJECTIONS}): ${JSON.stringify(gaps)}. Produce the requested artifact kinds, move prose-stated figures into artifact payloads, cover every flagged ask, query every table named in missing_required_tables, state every required metric value in prose or a payload, and correct or drop each unsupported figure that matches no tool output, back every narrated ask facet with at least one tool call or result, or record each one in the omitted field. A submission whose blocks only announce or confirm the analysis ("Submitted.", "Done", "see above") is never acceptable — copy the computed figures and tables into the blocks themselves even when gaps remain; when an artifact kind genuinely cannot be produced, deliver that content as a markdown table inside a block and name it in omitted. After ${SUBMIT_AUDIT_MAX_REJECTIONS} rejections the next submission is accepted as-is.`;
                        }
                    );
                    const verifyTool = createVerifyAnswerNumbersTool(
                        () => [...(start.sources ?? []), ...connected.results.values()],
                        start.q
                    );
                    session = await createAnalystSession({
                        cwd: start.cwd, agentDir: start.agentDir, model, modelRuntime: runtime,
                        tools: [
                            ...wrapBridgeTools(bridge.tools, connected.results, (event: Parameters<typeof emit>[0]) => {
                                if (event.type === "tool_call" && event.args !== undefined) {
                                    dataToolCalls += 1;
                                    const argsJson = JSON.stringify(event.args).toLowerCase();
                                    toolArgsText.push(argsJson);
                                    for (const match of argsJson.matchAll(WAREHOUSE_TABLE_RE))
                                        consultedTables.add(match[0]);
                                }
                                emit(event);
                            }, tracker, (reason: string) => {
                                emit({ type: "failure", kind: "loop_stop", message: reason });
                                controller.abort();
                            }, start.q, compositionGate),
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
                    const retryStormGuard = createProviderRetryStormGuard(emit, (reason: string) => {
                        emit({ type: "failure", kind: "provider_retry_storm", message: reason });
                        controller.abort();
                    }, (burnedMs: number) => {
                        emit({ type: "tool_call", name: "retry_budget_steer", args: { burned_ms: burnedMs } });
                        emit({ type: "tool_result", name: "retry_budget_steer", status: "ok" });
                        session?.agent.steer({
                            role: "user",
                            content: `Provider calls are hitting retry backoffs (latency, not an outage): this run has already spent ~${Math.round(burnedMs / 1000)}s waiting on them. The warehouse tools still work normally — keep using them for the remaining sub-questions and do not spend calls speculating about availability. When the verified work is enough to answer the core ask, submit with it and list uncovered sub-questions in omitted. Skip this only if submit_answer already ran.`,
                            timestamp: Date.now()
                        });
                    }, deps.retryTimeBudgetMs);
                    let notFoundCorrections = 0;
                    let scannedToolResults = 0;
                    let turnCount = 0;
                    const correctedNotFoundNames = new Set<string>();
                    session.subscribe(event => {
                        if (event.type === "turn_start")
                            emit({ type: "status", text: turnCount++ === 0 ? "Reading the question" : "Weighing the evidence" });
                        const mapped = analystEventFrom(event);
                        if (mapped)
                            emit(mapped);
                        retryStormGuard(event);
                        if (event.type === "auto_retry_end" && !event.success && typeof event.finalError === "string")
                            providerErrorEvidence += ` ${event.finalError}`;
                        if (event.type === "message_end" && event.message && event.message.role === "assistant" && typeof event.message.errorMessage === "string")
                            providerErrorEvidence += ` ${event.message.errorMessage}`;
                        if (notFoundCorrections < 6) {
                            const messages = session?.messages ?? [];
                            for (let i = scannedToolResults; i < messages.length; i++) {
                                const message = messages[i];
                                if (message.role !== "toolResult")
                                    continue;
                                const text = (message.content || []).map(c => c.type === "text" ? c.text : "").join("\n");
                                const notFound = text.match(/Tool\s+"?([A-Za-z0-9_.]+)"?\s+not found/);
                                if (notFound && !correctedNotFoundNames.has(notFound[1])) {
                                    correctedNotFoundNames.add(notFound[1]);
                                    notFoundCorrections++;
                                    emit({ type: "tool_call", name: "tool_not_found_correction", args: { malformed: notFound[1] } });
                                    emit({ type: "tool_result", name: "tool_not_found_correction", status: "ok", result: `corrected malformed tool name: ${notFound[1]}` });
                                    session?.agent.steer({
                                        role: "user",
                                        content: `Correction: nothing is missing — the error you saw means only the invocation form was wrong, not that any tool is unavailable. submit_answer is a direct tool you invoke as a tool_call in your response — never JavaScript, never inside codemode — and there is no tools.xxx invocation form for it. The failing call used a malformed name (${notFound[1]}). The same holds for sql_exec, verify_answer_numbers and the warehouse tools: invoke them as direct tool_calls by bare name. Retry what you were doing right now.`,
                                        timestamp: Date.now()
                                    });
                                    break;
                                }
                            }
                            scannedToolResults = messages.length;
                        }
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
                        const directiveAtMs = Math.max(5000, runTimeoutMs * 0.5);
                        compositionDirective = setTimeout(() => {
                            if (acceptedSubmission)
                                return;
                            if (!compositionGate.fireDirective())
                                return;
                            emit({ type: "tool_call", name: "composition_directive" });
                            emit({ type: "tool_result", name: "composition_directive", status: "ok" });
                            agent.steer({
                                role: "user",
                                content: "Half the run budget is gone and you hold verified data. Call submit_answer NOW with a partial draft of what you have verified — submission is not final: it banks the partial answer, and you may keep querying and resubmit after it. A banked partial answer plus revision beats a perfect answer that never submits. Data tools pause if several more calls pass with no submission. Skip this only if submit_answer already ran.",
                                timestamp: Date.now()
                            });
                        }, directiveAtMs);
                        compositionDirective.unref();
                        budgetNudge = setTimeout(() => {
                            if (acceptedSubmission)
                                return;
                            const remaining = Math.max(0, Math.round((runTimeoutMs - (Date.now() - startedAt)) / 1000));
                            agent.steer({
                                role: "user",
                                content: `Host run budget nearly exhausted (~${remaining}s remaining before abort). Call submit_answer directly now with the verified partial work and list the uncovered sub-questions in its omitted field — a verified partial answer beats no answer. Skip this only if submit_answer already ran.`,
                                timestamp: Date.now()
                            });
                        }, nudgeAtMs);
                        budgetNudge.unref();
                        const salvageAtMs = Math.max(5000, Math.min(runTimeoutMs * 0.88, nudgeAtMs + 10000));
                        narrationSalvage = setTimeout(() => {
                            if (acceptedSubmission || answerEmitted || !session)
                                return;
                            if (!session.messages.some(message => message.role === "toolResult"))
                                return;
                            const drafted = salvageDraftSubmission(mergedStoreSnapshot(codemodeStoreSnapshot(session.sessionManager.getBranch()), start.bridge.cwd));
                            let salvaged = drafted ?? salvageNarrationSubmission(session.messages);
                            if (!salvaged)
                                return;
                            if (salvaged.artifacts?.length) {
                                const salvageSources = [...(start.sources ?? []), ...connected.results.values()];
                                const salvageSourceMap = new Map(salvageSources.map(source => [source.ref, source]));
                                const resolved = resolveSalvagedArtifacts(salvaged.artifacts, ref => salvageSourceMap.get(ref), [...salvageSourceMap.keys()]);
                                const { artifacts: _rawSalvagedArtifacts, ...salvagedRest } = salvaged;
                                salvaged = {
                                    ...salvagedRest,
                                    ...(resolved.artifacts.length ? { artifacts: resolved.artifacts } : {}),
                                    ...(resolved.dropped ? { omitted: [...(salvaged.omitted ?? []), `${resolved.dropped} draft artifact(s) could not be resolved against this run's sources and were dropped`] } : {})
                                };
                            }
                            acceptedSubmission = salvaged;
                            if (!drafted) {
                                emittedFromNarration = true;
                                narrationSubmissionRef = salvaged;
                            }
                            emitAcceptedAnswer();
                        }, salvageAtMs);
                        narrationSalvage.unref();
                    }
                    kind = "model";
                    const turnStartMessageCount = session.messages.length;
                    await session.prompt(start.q);
                    let nondeliverySteersUsed = 0;
                    let submitSteerUsed = false;
                    let giveUpSteerUsed = false;
                    let emptyRetryUsed = false;
                    let notFoundSteerUsed = false;
                    let text = "";
                    let reasoning = "";
                    for (;;) {
                        controller.signal.throwIfAborted();
                        const last = session.messages.filter(m => m.role === "assistant").at(-1);
                        if (!last || last.stopReason === "error" || last.stopReason === "aborted") {
                            const detail = last && "errorMessage" in last && typeof last.errorMessage === "string" ? last.errorMessage : "";
                            throw new Error(detail || "Model failed");
                        }
                        text = last.content.filter(c => c.type === "text").map(c => c.text).join("");
                        reasoning = last.content.flatMap(block => block.type === "thinking" ? [block.thinking] : []).join("\n").trim();
                        if (!acceptedSubmission && !text.trim() && !last.content.some(c => c.type === "toolCall") && !emptyRetryUsed) {
                            emptyRetryUsed = true;
                            emit({ type: "tool_call", name: "empty_completion_retry" });
                            emit({ type: "tool_result", name: "empty_completion_retry", status: "ok" });
                            await session.prompt("Your last response came back empty. Continue: if the ask still needs data work, call the next tool now; if you already hold verified results, call submit_answer directly with them.");
                            continue;
                        }
                        if (!notFoundSteerUsed) {
                            const toolResultText = session.messages.filter(m => m.role === "toolResult").flatMap(m => m.content || []).map(c => c.type === "text" ? c.text : "").join("\n");
                            const notFoundMatch = toolResultText.match(/Tool\s+"?([A-Za-z0-9_.]+)"?\s+not found/);
                            if (notFoundMatch) {
                                notFoundSteerUsed = true;
                                const available = [...new Set([...(bridge?.tools ?? []).map(t => t.name), "submit_answer", "verify_answer_numbers", "load_skill", "run_status"])].sort().join(", ");
                                emit({ type: "tool_call", name: "tool_not_found_correction" });
                                emit({ type: "tool_result", name: "tool_not_found_correction", status: "ok" });
                                await session.prompt(`Correction: the tools ARE available and working in this session — the error you saw means only the invocation form was wrong, not that any tool is missing. The failing call used a malformed name (${notFoundMatch[1]}). Call every tool by its bare registered name with no tools. prefix and no other prefix or suffix — the prefixed form does not exist and always errors. Available right now: ${available}. Retry what you were doing with the exact bare name now.`);
                                continue;
                            }
                        }
                        if (!acceptedSubmission && nondeliverySteersUsed < 2) {
                            const turnText = session.messages.slice(turnStartMessageCount).filter(m => m.role === "assistant").flatMap(m => m.content || []).filter(c => c.type === "text").map(c => c.text).join("");
                            const turnHasToolResults = session.messages.slice(turnStartMessageCount).some(m => m.role === "toolResult");
                            const endsInQuestion = /\?\s*$/.test(text.trim());
                            if (turnHasToolResults && turnText.trim().length >= TURN_END_STEER_MIN_CHARS && !endsInQuestion) {
                                const remainingMs = start.runTimeoutMs !== undefined
                                    ? Math.max(0, start.runTimeoutMs - (Date.now() - startedAt))
                                    : undefined;
                                if (remainingMs === undefined || remainingMs > 45_000) {
                                    nondeliverySteersUsed++;
                                    emit({ type: "tool_call", name: "nondelivery_interception" });
                                    emit({ type: "tool_result", name: "nondelivery_interception", status: "ok" });
                                    await session.prompt("Your analysis exists only as narration — the reader receives nothing until it is submitted. Call submit_answer now with the text you already wrote moved verbatim into blocks; do not rewrite or extend it.");
                                    continue;
                                }
                            }
                        }
                        if (acceptedSubmission || text.trim().length < TURN_END_STEER_MIN_CHARS)
                            break;
                        const zeroEvidenceDataAsk = dataToolCalls === 0
                            && (start.sources?.length ?? 0) === 0
                            && connected.results.size === 0
                            && isDataAsk(start.q);
                        if (zeroEvidenceDataAsk && !zeroEvidenceRepromptUsed) {
                            const remainingMs = start.runTimeoutMs !== undefined
                                ? Math.max(0, start.runTimeoutMs - (Date.now() - startedAt))
                                : undefined;
                            if (remainingMs === undefined || remainingMs > SUBMIT_FORCE_REMAINING_MS) {
                                zeroEvidenceRepromptUsed = true;
                                emit({ type: "tool_call", name: "zero_evidence_reprompt" });
                                emit({ type: "tool_result", name: "zero_evidence_reprompt", status: "ok" });
                                await session.prompt("This is a data question and no data tool has been called yet — nothing has failed: submit_answer, sql_exec and verify_answer_numbers are available and working right now, the warehouse is up and reachable, and there is no tools.xxx invocation form — these are direct tools you call by bare name, so do not answer from memory and do not conclude any tool is missing. First action: run sql_exec with a count probe on the silver table the ask names — {sql: \"SELECT count(*) FROM <the silver table the ask names>\"} — or, if unsure which table, sql_exec with {sql: \"SELECT table_name, estimated_size FROM duckdb_tables() WHERE table_name LIKE 'silver%' ORDER BY table_name\"} to list the real populated tables. Then query the tables your figures rely on and call submit_answer directly with the verified text, its artifacts and source anchors, and anything left out in omitted.");
                                continue;
                            }
                        }
                        if (!submitSteerUsed) {
                            submitSteerUsed = true;
                            emit({ type: "tool_call", name: "turn_end_steer" });
                            emit({ type: "tool_result", name: "turn_end_steer", status: "ok" });
                            await session.prompt("You ended the run with an answer but never called submit_answer. Route it through a direct submit_answer tool call now (plain tool name, no tools. prefix): put that answer's text into blocks, add the artifacts and source anchors it should carry, list anything left out in omitted, and submit. Do not rewrite the answer.");
                            continue;
                        }
                        if (!giveUpSteerUsed && !zeroEvidenceDataAsk) {
                            const remainingMs = start.runTimeoutMs !== undefined
                                ? Math.max(0, start.runTimeoutMs - (Date.now() - startedAt))
                                : undefined;
                            if (remainingMs === undefined || remainingMs > SUBMIT_FORCE_REMAINING_MS) {
                                giveUpSteerUsed = true;
                                emit({ type: "tool_call", name: "give_up_correction_steer" });
                                emit({ type: "tool_result", name: "give_up_correction_steer", status: "ok" });
                                await session.prompt("submit_answer is available and working — it is a plain direct tool you call by its bare name submit_answer, with no tools. prefix (the prefixed name does not exist and errors), and not something you narrate in the answer text. Any earlier rejection was a content audit, not a tool failure. Call submit_answer now: move your drafted answer into its blocks field, attach the artifacts and source anchors it names, list anything left out in omitted, and submit.");
                                continue;
                            }
                        }
                        break;
                    }
                    const replayReasoning = reasoning ? { reasoning } : {};
                    if (!acceptedSubmission && lastRejectedSubmission) {
                        const rejectedText = lastRejectedSubmission.blocks.map(block => block.text).join("\n\n");
                        if (rejectedText.trim().length > text.trim().length * 1.5)
                            acceptedSubmission = lastRejectedSubmission;
                    }
                    if (!acceptedSubmission && session) {
                        const drafted = salvageDraftSubmission(mergedStoreSnapshot(codemodeStoreSnapshot(session.sessionManager.getBranch()), start.bridge.cwd))
                            ?? (session.messages.some(message => message.role === "toolResult") ? salvageNarrationSubmission(session.messages) : undefined);
                        if (drafted)
                            acceptedSubmission = drafted;
                    }
                    if (acceptedSubmission) {
                        if (!answerEmitted) {
                            const canonicalText = acceptedSubmission.blocks.map(b => b.text).join("\n\n");
                            emit({ type: "answer", text: canonicalText, submission: acceptedSubmission, ...replayReasoning });
                            answerEmitted = true;
                        }
                    } else {
                        if (!text.trim())
                            throw new Error("Model returned no answer");
                        const zeroEvidence = dataToolCalls === 0
                            && (start.sources?.length ?? 0) === 0
                            && connected.results.size === 0
                            && isDataAsk(start.q);
                        if (zeroEvidence) {
                            emit({ type: "tool_call", name: "submit_answer_audit" });
                            emit({ type: "tool_result", name: "submit_answer_audit", status: "fail", error: JSON.stringify({ no_evidence_on_data_ask: [ZERO_EVIDENCE_DATA_ASK_FLAG] }) });
                            answerEmitted = true;
                            emit({ type: "answer", text, submission: { blocks: [{ text, anchors: [] }], omitted: [ZERO_EVIDENCE_DATA_ASK_FLAG] }, ...replayReasoning });
                        } else {
                            emit({ type: "answer", text, ...replayReasoning });
                        }
                    }
                }
                catch (error) {
                    emitAcceptedAnswer();
                    if (!answerEmitted && !acceptedSubmission && lastRejectedSubmission) {
                        acceptedSubmission = lastRejectedSubmission;
                        emitAcceptedAnswer();
                    }
                    if (!answerEmitted && !acceptedSubmission && session) {
                        const drafted = salvageDraftSubmission(mergedStoreSnapshot(codemodeStoreSnapshot(session.sessionManager.getBranch()), bridgeCwd));
                        if (drafted) {
                            acceptedSubmission = drafted;
                            emitAcceptedAnswer();
                        }
                    }
                    if (!answerEmitted && !acceptedSubmission && session && session.messages.some(message => message.role === "toolResult")) {
                        const narrated = salvageNarrationSubmission(session.messages);
                        if (narrated) {
                            acceptedSubmission = narrated;
                            emittedFromNarration = true;
                            narrationSubmissionRef = narrated;
                            emitAcceptedAnswer();
                        }
                    }
                    if (emittedFromNarration && acceptedSubmission === narrationSubmissionRef && session) {
                        const upgrade = salvageDraftSubmission(mergedStoreSnapshot(codemodeStoreSnapshot(session.sessionManager.getBranch()), bridgeCwd));
                        if (upgrade && upgrade.blocks.map(block => block.text).join("\n\n") !== acceptedSubmission?.blocks.map(block => block.text).join("\n\n")) {
                            acceptedSubmission = upgrade;
                            emittedFromNarration = false;
                            emit({ type: "answer", text: upgrade.blocks.map(block => block.text).join("\n\n"), submission: upgrade });
                        }
                    }
                    if (!answerEmitted && !controller.signal.aborted) {
                        const failureKind = classifyFailureKind(kind, error, session, providerErrorEvidence);
                        const rawErrorText = error instanceof Error ? error.message : String(error ?? "");
                        const failureError = failureKind === "quota" && !isRateLimitEvidence(rawErrorText)
                            ? new Error("the model provider's rate limit or quota was exhausted mid-run")
                            : error;
                        emit({ type: "failure", kind: failureKind, message: safeFailureMessage(failureKind, failureError, modelApiKey) });
                    }
                }
                finally {
                    runSettled = true;
                    if (hardKillTimer)
                        clearTimeout(hardKillTimer);
                    if (budgetNudge)
                        clearTimeout(budgetNudge);
                    if (compositionDirective)
                        clearTimeout(compositionDirective);
                    if (narrationSalvage)
                        clearTimeout(narrationSalvage);
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
                        await closeBridge();
                        controller.signal.removeEventListener("abort", cancel);
                        emit({ type: "closed", pid: bridgePid });
                    }
                }
            }
            const pending = run().finally(() => { finished = true; wake?.(); });
            try {
                while ((!finished && !abandoned) || events.length) {
                    const next = events.shift();
                    if (next === ABANDON_SENTINEL)
                        break;
                    if (next)
                        yield next as AnalystEvent;
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

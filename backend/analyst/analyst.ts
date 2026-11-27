import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash, randomUUID } from "node:crypto";
import { Type, type Static } from "typebox";
import { viewContextSchema, withViewContext, type ViewContext } from "./view-context.js";
import { Value } from "typebox/value";
import { createPiExecution, type AnalystEvent } from "./pi-execution.js";
import { ProductStore, type Identity } from "./product-store.js";
import { providerPolicy } from "./providers.js";
import type { SourceRecord } from "./python-tools.js";
import type { AnswerSubmission } from "./submit-tool.js";

const MAX_TURN_CHARS = 64000;
const MAX_HISTORY_ITEMS = 24;

const optionalText = (max: number) => Type.Optional(Type.Union([Type.String({ minLength: 1, maxLength: max, pattern: "\\S" }), Type.Null()]));
export const analystRequestSchema = Type.Object({
    q: Type.String({ minLength: 1, maxLength: MAX_TURN_CHARS, pattern: "\\S" }), model: optionalText(256),
    thread: optionalText(80), client: optionalText(80), diagnostics: Type.Optional(Type.Boolean()), context: Type.Optional(Type.Union([viewContextSchema, Type.Null()])),
    history: Type.Optional(Type.Array(Type.Object({ role: Type.Union([Type.Literal("user"), Type.Literal("assistant")]), content: Type.String({ minLength: 1, maxLength: MAX_TURN_CHARS, pattern: "\\S" }) }, { additionalProperties: false }), { maxItems: MAX_HISTORY_ITEMS }))
}, { additionalProperties: false });
export type AnalystRequest = Static<typeof analystRequestSchema>;
export type ProductEvent = {
    type: "ping";
    data: {
        ok: true;
    };
} | {
    type: "token";
    data: {
        text: string;
    };
} | {
    type: "status";
    data: {
        text: string;
    };
} | {
    type: "tool_call";
    data: {
        node: "tools";
        name: string;
        data: { args?: unknown };
    };
} | {
    type: "tool_result";
    data: {
        node: "tools";
        name: string;
        status: "ok" | "fail";
        rows?: number;
        error?: string;
        result?: string;
        result_sha256?: string;
        result_bytes?: number;
        result_truncated?: boolean;
    };
} | {
    type: "failure";
    data: {
        kind: string;
        message: string;
    };
} | {
    type: "error";
    data: {
        message: string;
    };
} | {
    type: "work_log";
    data: {
        run_id: string;
        status: "partial";
    };
} | {
    type: "custom_data";
    data: {
        tables?: Array<Record<string, unknown>>;
        artifacts?: Array<Record<string, unknown>>;
        unverified_numbers?: Array<number | string>;
    };
} | {
    type: "final_answer";
    data: {
        text: string;
        carry: {
            run_id: string;
            verification: "unassessed";
            answer_status: "unassessed";
            source_refs: string[];
            submission?: AnswerSubmission;
        };
    };
} | {
    type: "graph_end";
    data: Record<string, never>;
};

export const backendRoot = fileURLToPath(new URL("../../", import.meta.url));
export function runTimeoutMs(env: NodeJS.ProcessEnv) {
    const n = Number(env.DIME_V2_RUN_TIMEOUT_S);
    return Number.isFinite(n) && n > 0 ? Math.round(n * 1000) : 360000;
}
export function productPaths(env: NodeJS.ProcessEnv) {
    const data = join(backendRoot, "data");
    return { conversations: resolve(env.DIME_CONVERSATION_STORE ?? join(data, "v2-conversations.sqlite3")), sources: resolve(env.DIME_PI_SOURCES_DIR ?? join(data, "pi-sources")), private: resolve(env.DIME_PI_PRIVATE_DIR ?? join(data, "pi-private")), warehouse: resolve(env.DIME_WAREHOUSE || join(data, "warehouse.duckdb")) };
}

export function dataEnvironment(env: NodeJS.ProcessEnv, cwd: string, workspaceDir?: string) {
    const allowed = ["SystemRoot", "WINDIR", "PATH", "LANG", "SSL_CERT_FILE", "SSL_CERT_DIR", "PYTHONPATH", "DIME_STATE_DB", "DIME_PY_PERSIST_NS", "DIME_PY_NS_CAP_MB"];
    const clean: Record<string, string> = {};
    for (const name of allowed)
        if (env[name])
            clean[name] = env[name];
    return { ...clean, DIME_STATE_DB: resolve(env.DIME_STATE_DB || join(backendRoot, "data/state.duckdb")), HOME: cwd, USERPROFILE: cwd, TEMP: cwd, TMP: cwd, OPENBLAS_NUM_THREADS: "1", OMP_NUM_THREADS: "1", POLARS_MAX_THREADS: "1", DIME_WAREHOUSE: productPaths(env).warehouse, DIME_THREAD_WORKSPACE: workspaceDir ?? cwd };
}

export function newRunId() { return "run-" + randomUUID().replaceAll("-", ""); }
export function encodeEvent({ type, data }: ProductEvent) { return `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`; }

export function threadWorkspacePath(privateDir: string, identity: Identity): string {
    const safeHash = createHash("sha256").update(`${identity.owner}\0${identity.thread}`).digest("hex").slice(0, 32);
    return join(privateDir, "workspaces", safeHash);
}

async function prepareRunWorkspace(paths: ReturnType<typeof productPaths>, identity?: Identity) {
    await mkdir(paths.private, { recursive: true });
    const directory = await mkdtemp(join(paths.private, "pi-"));
    const agentDir = join(directory, "agent");
    await mkdir(agentDir);
    if (!identity)
        return { directory, agentDir, workspaceDir: directory };
    const workspaceDir = threadWorkspacePath(paths.private, identity);
    await mkdir(workspaceDir, { recursive: true });
    return { directory, agentDir, workspaceDir };
}

type RunState = {
    answer?: string;
    reasoning?: string;
    failed: boolean;
    streamed: boolean;
    submission?: AnswerSubmission;
    records: SourceRecord[];
    fresh: SourceRecord[];
};

function mapExecutionEvent(event: AnalystEvent, state: RunState): ProductEvent | undefined {
    switch (event.type) {
        case "source":
            state.records.push(event.record);
            state.fresh.push(event.record);
            return undefined;
        case "answer":
            state.answer = event.text;
            state.submission = event.submission;
            state.reasoning = event.reasoning;
            return undefined;
        case "custom_data":
            return {
                type: "custom_data",
                data: {
                    ...(event.tables ? { tables: event.tables } : {}),
                    ...(event.artifacts ? { artifacts: event.artifacts } : {}),
                    ...(event.unverified_numbers ? { unverified_numbers: event.unverified_numbers } : {})
                }
            };
        case "closed":
            return undefined;
        case "token":
            state.streamed = true;
            return { type: "token", data: { text: event.text } };
        case "status":
            return { type: "status", data: { text: event.text } };
        case "failure":
            state.failed = true;
            return { type: "failure", data: { kind: event.kind, message: event.message } };
        case "tool_call":
            return { type: "tool_call", data: { node: "tools", name: event.name, data: { args: event.args } } };
        case "tool_result":
            return {
                type: "tool_result",
                data: {
                    node: "tools",
                    name: event.name,
                    status: event.status,
                    ...(event.rows === undefined ? {} : { rows: event.rows }),
                    ...(event.status === "fail" ? { error: event.error || "Tool failed" } : {}),
                    ...(event.result === undefined ? {} : {
                        result: event.result,
                        result_sha256: event.result_sha256,
                        result_bytes: event.result_bytes,
                        ...(event.result_truncated ? { result_truncated: true } : {})
                    })
                }
            };
    }
}

type AnalystOptions = {
    env: NodeJS.ProcessEnv;
    python?: string;
    resolveModel?: ReturnType<typeof providerPolicy>["resolve"];
    store?: ProductStore;
    execution?: ReturnType<typeof createPiExecution>;
    saveChat: (thread: string, role: string, content: string, owner: string) => Promise<void>;
    saveRun: (thread: string, q: string, answer: string, owner: string, run: string) => Promise<void>;
};

async function persistCompletedRun(
    options: AnalystOptions,
    store: ProductStore,
    identity: Identity | undefined,
    question: string,
    run: string,
    state: RunState
) {
    if (state.records.length || !state.failed)
        store.saveSources(run, state.fresh, state.records, state.submission);
    if (!state.failed && state.answer && identity) {
        await options.saveChat(identity.thread, "ai", state.answer, identity.owner.slice(0, 80));
        await options.saveRun(identity.thread, question.slice(0, MAX_TURN_CHARS), state.answer, identity.owner.slice(0, 80), run);
        store.append(identity, question, state.answer, run, state.reasoning);
    }
}

function completionEvents(run: string, state: RunState): ProductEvent[] {
    const events: ProductEvent[] = [{ type: "work_log", data: { run_id: run, status: "partial" } }];
    if (!state.failed && state.answer) {
        if (!state.streamed)
            events.push({ type: "token", data: { text: state.answer } });
        events.push({
            type: "final_answer",
            data: {
                text: state.answer,
                carry: {
                    run_id: run,
                    verification: "unassessed",
                    answer_status: "unassessed",
                    source_refs: state.records.map(r => r.ref),
                    ...(state.submission ? { submission: state.submission } : {})
                }
            }
        });
    }
    events.push({ type: "graph_end", data: {} });
    return events;
}

function resolveAnalystModel(resolveModel: ReturnType<typeof providerPolicy>["resolve"], modelId?: string) {
    try {
        return resolveModel(modelId);
    }
    catch {
        return undefined;
    }
}

export function createAnalyst(options: AnalystOptions) {
    const paths = productPaths(options.env), store = options.store ?? new ProductStore(paths.conversations, paths.sources);
    const policy = providerPolicy(options.env), execution = options.execution ?? createPiExecution();
    return {
        store,
        async *stream(input: unknown, signal?: AbortSignal, run = newRunId(), streamOptions: { runTimeoutMs?: number } = {}): AsyncGenerator<ProductEvent> {
            if (!Value.Check(analystRequestSchema, input) || (input.thread && !input.client))
                throw new Error("Invalid analyst request");
            if (input.context && JSON.stringify(input.context.entities).length > 4000)
                throw new Error("Invalid analyst request");
            const turnText = withViewContext(input as { q: string; context?: ViewContext | null });
            const model = resolveAnalystModel(options.resolveModel ?? policy.resolve, input.model ?? undefined);
            if (!model) {
                yield { type: "failure", data: { kind: "configuration", message: "Dime model configuration is unavailable." } };
                yield { type: "graph_end", data: {} };
                return;
            }
            const identity = input.thread && input.client ? { owner: input.client, thread: input.thread } : undefined;
            let directory: string | undefined;
            const state: RunState = { failed: false, streamed: false, records: identity ? store.priorSources(identity) : [], fresh: [] };
            try {
                const history = identity ? store.read(identity) : input.history ?? [];
                const workspace = await prepareRunWorkspace(paths, identity);
                directory = workspace.directory;
                if (identity)
                    await options.saveChat(identity.thread, "human", turnText.slice(0, MAX_TURN_CHARS), identity.owner.slice(0, 80));
                const bridgeEnv = dataEnvironment(options.env, directory, workspace.workspaceDir);
                for await (const event of execution.stream({ q: turnText, history, model, submissions: identity ? store.priorSubmissions(identity).slice(-8) : undefined, ...(streamOptions.runTimeoutMs === undefined ? {} : { runTimeoutMs: streamOptions.runTimeoutMs }), sources: state.records, cwd: directory, agentDir: workspace.agentDir, bridge: { python: options.python, cwd: workspace.workspaceDir, env: bridgeEnv } }, signal)) {
                    const mapped = mapExecutionEvent(event, state);
                    if (mapped)
                        yield mapped;
                }
                if (signal?.aborted) {
                    if (state.records.length || state.answer || state.submission)
                        await persistCompletedRun(options, store, identity, turnText, run, state).catch(() => undefined);
                    return;
                }
                await persistCompletedRun(options, store, identity, turnText, run, state);
            }
            catch {
                if (signal?.aborted) {
                    if (state.records.length || state.answer || state.submission)
                        await persistCompletedRun(options, store, identity, turnText, run, state).catch(() => undefined);
                    return;
                }
                state.failed = true;
                yield { type: "failure", data: { kind: "transport", message: "Dime could not finish this run." } };
            }
            finally {
                if (directory)
                    await rm(directory, { recursive: true, force: true });
            }
            for (const event of completionEvents(run, state))
                yield event;
        }
    };
}

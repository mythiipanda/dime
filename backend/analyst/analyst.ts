import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import { createPiExecution } from "./pi-execution.js";
import { ProductStore } from "./product-store.js";
import { providerPolicy } from "./providers.js";
import type { SourceRecord } from "./python-tools.js";
const optionalText = (max: number) => Type.Optional(Type.Union([Type.String({ minLength: 1, maxLength: max, pattern: "\\S" }), Type.Null()]));
export const analystRequestSchema = Type.Object({
    q: Type.String({ minLength: 1, maxLength: 2000, pattern: "\\S" }), model: optionalText(256),
    thread: optionalText(80), client: optionalText(80), diagnostics: Type.Optional(Type.Boolean()),
    history: Type.Optional(Type.Array(Type.Object({ role: Type.Union([Type.Literal("user"), Type.Literal("assistant")]), content: Type.String({ minLength: 1, maxLength: 2000, pattern: "\\S" }) }, { additionalProperties: false }), { maxItems: 8 }))
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
    type: "tool_call";
    data: {
        node: "tools";
        name: string;
        data: Record<string, never>;
    };
} | {
    type: "tool_result";
    data: {
        node: "tools";
        name: string;
        status: "ok" | "fail";
        rows?: number;
        error?: string;
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
    type: "final_answer";
    data: {
        text: string;
        carry: {
            run_id: string;
            verification: "unassessed";
            answer_status: "unassessed";
            source_refs: string[];
        };
    };
} | {
    type: "graph_end";
    data: Record<string, never>;
};
export const backendRoot = fileURLToPath(new URL("../../", import.meta.url));
export function productPaths(env: NodeJS.ProcessEnv) {
    const data = join(backendRoot, "data");
    return { conversations: resolve(env.DIME_CONVERSATION_STORE ?? join(data, "v2-conversations.sqlite3")), sources: resolve(env.DIME_PI_SOURCES_DIR ?? join(data, "pi-sources")), private: resolve(env.DIME_PI_PRIVATE_DIR ?? join(data, "pi-private")), warehouse: resolve(env.DIME_WAREHOUSE || join(data, "warehouse.duckdb")) };
}
export function dataEnvironment(env: NodeJS.ProcessEnv, cwd: string) {
    const allowed = ["SystemRoot", "WINDIR", "PATH", "LANG", "SSL_CERT_FILE", "SSL_CERT_DIR", "PYTHONPATH", "DIME_STATE_DB"];
    const clean: Record<string, string> = {};
    for (const name of allowed)
        if (env[name])
            clean[name] = env[name];
    return { ...clean, DIME_STATE_DB: resolve(env.DIME_STATE_DB || join(backendRoot, "data/state.duckdb")), HOME: cwd, USERPROFILE: cwd, TEMP: cwd, TMP: cwd, OPENBLAS_NUM_THREADS: "1", OMP_NUM_THREADS: "1", POLARS_MAX_THREADS: "1", DIME_WAREHOUSE: productPaths(env).warehouse };
}
export function newRunId() { return "run-" + randomUUID().replaceAll("-", ""); }
export function encodeEvent({ type, data }: ProductEvent) { return `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`; }
export function createAnalyst(options: {
    env: NodeJS.ProcessEnv;
    python: string;
    resolveModel?: ReturnType<typeof providerPolicy>["resolve"];
    saveChat: (thread: string, role: string, content: string, owner: string) => Promise<void>;
    saveRun: (thread: string, q: string, answer: string, owner: string, run: string) => Promise<void>;
}) {
    const paths = productPaths(options.env), store = new ProductStore(paths.conversations, paths.sources);
    const policy = providerPolicy(options.env), execution = createPiExecution();
    return {
        store,
        async *stream(input: unknown, signal?: AbortSignal, run = newRunId()): AsyncGenerator<ProductEvent> {
            if (!Value.Check(analystRequestSchema, input) || (input.thread && !input.client))
                throw new Error("Invalid analyst request");
            let model;
            try {
                model = (options.resolveModel ?? policy.resolve)(input.model ?? undefined);
            }
            catch {
                yield { type: "failure", data: { kind: "configuration", message: "Dime model configuration is unavailable." } };
                yield { type: "graph_end", data: {} };
                return;
            }
            const identity = input.thread && input.client ? { owner: input.client, thread: input.thread } : undefined;
            let directory: string | undefined;
            let answer: string | undefined, failed = false, streamed = false;
            let records: SourceRecord[] = [];
            const fresh: SourceRecord[] = [];
            try {
                records = identity ? store.priorSources(identity) : [];
                const history = identity ? store.read(identity) : input.history ?? [];
                await mkdir(paths.private, { recursive: true });
                directory = await mkdtemp(join(paths.private, "pi-"));
                const agentDir = join(directory, "agent");
                await mkdir(agentDir);
                if (identity)
                    await options.saveChat(identity.thread, "human", input.q.slice(0, 2000), identity.owner.slice(0, 80));
                for await (const event of execution.stream({ q: input.q, history, model, sources: records, cwd: directory, agentDir, bridge: { python: options.python, cwd: directory, env: dataEnvironment(options.env, directory) } }, signal)) {
                    switch (event.type) {
                        case "source":
                            records.push(event.record);
                            fresh.push(event.record);
                            break;
                        case "answer":
                            answer = event.text;
                            break;
                        case "closed": break;
                        case "token":
                            streamed = true;
                            yield { type: "token", data: { text: event.text } };
                            break;
                        case "failure":
                            failed = true;
                            yield { type: "failure", data: { kind: event.kind, message: event.message } };
                            break;
                        case "tool_call":
                            yield { type: "tool_call", data: { node: "tools", name: event.name, data: {} } };
                            break;
                        case "tool_result":
                            yield { type: "tool_result", data: { node: "tools", name: event.name, status: event.status, ...(event.rows === undefined ? {} : { rows: event.rows }), ...(event.status === "fail" ? { error: "Tool failed" } : {}) } };
                            break;
                    }
                }
                if (signal?.aborted)
                    return;
                if (records.length || !failed)
                    store.saveSources(run, fresh, records);
                if (!failed && answer && identity) {
                    await options.saveChat(identity.thread, "ai", answer, identity.owner.slice(0, 80));
                    await options.saveRun(identity.thread, input.q.slice(0, 2000), answer, identity.owner.slice(0, 80), run);
                    store.append(identity, input.q, answer, run);
                }
            }
            catch {
                if (signal?.aborted)
                    return;
                failed = true;
                yield { type: "failure", data: { kind: "transport", message: "Dime could not finish this run." } };
            }
            finally {
                if (directory)
                    await rm(directory, { recursive: true, force: true });
            }
            yield { type: "work_log", data: { run_id: run, status: "partial" } };
            if (!failed && answer) {
                if (!streamed)
                    yield { type: "token", data: { text: answer } };
                yield { type: "final_answer", data: { text: answer, carry: { run_id: run, verification: "unassessed", answer_status: "unassessed", source_refs: records.map(r => r.ref) } } };
            }
            yield { type: "graph_end", data: {} };
        }
    };
}

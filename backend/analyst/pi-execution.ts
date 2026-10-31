import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import { createAnalystSession } from "./runtime.js";
import { connectPythonTools, objectValue, sourceRecordSchema, sourceOutputSchema, sourceResult, type SourceRecord, type PythonToolsOptions } from "./python-tools.js";
import { priorSourceTool, resolvedRuntime } from "./pi-context.js";
import { createSubmitAnswerTool, type AnswerSubmission } from "./submit-tool.js";
import type { Message } from "@earendil-works/pi-ai";
const turnSchema = Type.Object({ role: Type.Union([Type.Literal("user"), Type.Literal("assistant")]), content: Type.String() });
export const analystContextSchema = Type.Object({
    q: Type.String({ minLength: 1 }), history: Type.Array(turnSchema, { maxItems: 8 }), model: Type.Unknown(),
    sources: Type.Optional(Type.Array(sourceRecordSchema)), cwd: Type.String(), agentDir: Type.String(),
    bridge: Type.Object({ python: Type.String(), cwd: Type.String(), env: Type.Record(Type.String(), Type.String()) }),
});
export type AnalystContext = Static<typeof analystContextSchema>;
export type AnalystEvent = {
    type: "token";
    text: string;
} | {
    type: "tool_call";
    name: string;
} | {
    type: "tool_result";
    name: string;
    status: "ok" | "fail";
    error?: string;
    rows?: number;
} | {
    type: "source";
    record: SourceRecord;
} | {
    type: "answer";
    text: string;
    submission?: AnswerSubmission;
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
};
function sourceSummary(record: SourceRecord) {
    const { result, isError } = sourceResult(record).structuredContent;
    const data = objectValue(result);
    return {
        ref: record.ref, tool: record.tool, failed: isError, columns: data?.columns,
        declared_column_semantics: data?.declared_column_semantics, season_semantics: data?.season_semantics, provenance: data?.meta
    };
}
// HTTP and CLI adapters consume events without depending on Pi session types.
export function createPiExecution(deps: AnalystDeps = {}) {
    const resolveRuntime = deps.resolveRuntime ?? resolvedRuntime;
    const connectTools = deps.connectTools ?? connectPythonTools;
    return {
        async *stream(input: unknown, signal?: AbortSignal): AsyncGenerator<AnalystEvent> {
            const controller = new AbortController();
            const events: AnalystEvent[] = [];
            let wake: (() => void) | undefined;
            let finished = false;
            const emit = (event: AnalystEvent) => { events.push(event); wake?.(); };
            const onAbort = () => controller.abort();
            signal?.addEventListener("abort", onAbort, { once: true });
            if (signal?.aborted)
                controller.abort();
            async function run() {
                let session: Awaited<ReturnType<typeof createAnalystSession>> | undefined;
                let bridge: Awaited<ReturnType<typeof connectPythonTools>> | undefined;
                let kind = "configuration";
                let bridgePid: number | undefined;
                let acceptedSubmission: AnswerSubmission | undefined;
                const cancel = () => { void session?.abort(); };
                controller.signal.addEventListener("abort", cancel, { once: true });
                try {
                    if (!Value.Check(analystContextSchema, input) || !input.q.trim())
                        throw new Error("Invalid product context");
                    const start = input;
                    const { runtime, model } = await resolveRuntime(start.model);
                    controller.signal.throwIfAborted();
                    kind = "startup";
                    bridge = await connectTools(start.bridge);
                    bridgePid = bridge.pid;
                    controller.signal.throwIfAborted();
                    const connected = bridge;
                    const submitTool = createSubmitAnswerTool(
                        () => [...(start.sources ?? []), ...connected.results.values()],
                        (submission) => { acceptedSubmission = submission; }
                    );
                    session = await createAnalystSession({
                        cwd: start.cwd, agentDir: start.agentDir, model, modelRuntime: runtime,
                        tools: [...bridge.tools.map(tool => ({
                                ...tool,
                                async execute(...args: Parameters<typeof tool.execute>) {
                                    emit({ type: "tool_call", name: tool.name });
                                    try {
                                        const result = await tool.execute(...args);
                                        if (!Value.Check(sourceOutputSchema, result.structuredContent))
                                            throw new Error("Invalid source result");
                                        const record = connected.results.get(result.structuredContent.ref);
                                        if (!record)
                                            throw new Error("Tool result has no source record");
                                        emit({ type: "source", record });
                                        const domain = objectValue(result.structuredContent.result);
                                        const failed = result.structuredContent.isError;
                                        const error = domain?.error;
                                        emit({
                                            type: "tool_result", name: tool.name, status: failed ? "fail" : "ok",
                                            ...(failed ? { error: typeof error === "string" ? error : "Tool failed" } : {}),
                                            ...(Array.isArray(domain?.rows) ? { rows: domain.rows.length } : {})
                                        });
                                        return result;
                                    }
                                    catch (error) {
                                        emit({ type: "tool_result", name: tool.name, status: "fail", error: error instanceof Error ? error.message : String(error) });
                                        throw error;
                                    }
                                }
                            })), priorSourceTool(start.sources ?? []), submitTool]
                    });
                    controller.signal.throwIfAborted();
                    session.subscribe(event => {
                        if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
                            emit({ type: "token", text: event.assistantMessageEvent.delta });
                        }
                    });
                    const history: Message[] = start.history.map(turn => turn.role === "user"
                        ? { role: "user", content: turn.content, timestamp: Date.now() }
                        : {
                            role: "assistant", content: [{ type: "text", text: turn.content }], api: model.api, provider: model.provider, model: model.id,
                            usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
                            stopReason: "stop", timestamp: Date.now()
                        });
                    for (const message of history)
                        session.sessionManager.appendMessage(message);
                    session.agent.state.messages = [...session.agent.state.messages, ...history];
                    if (start.sources?.length) {
                        const context: Message = { role: "user", content: "Prior source catalogue. Use tools.read_source({ref}) inside codemode and return only filtered results:\n" + JSON.stringify(start.sources.map(sourceSummary)), timestamp: Date.now() };
                        session.sessionManager.appendMessage(context);
                        session.agent.state.messages.push(context);
                    }
                    kind = "model";
                    await session.prompt(start.q);
                    controller.signal.throwIfAborted();
                    const last = session.messages.filter(m => m.role === "assistant").at(-1);
                    if (!last || last.stopReason === "error" || last.stopReason === "aborted")
                        throw new Error("Model failed");
                    const text = last.content.filter(c => c.type === "text").map(c => c.text).join("");
                    if (acceptedSubmission) {
                        const canonicalText = acceptedSubmission.blocks.map(b => b.text).join("\n\n");
                        emit({ type: "answer", text: canonicalText, submission: acceptedSubmission });
                    } else {
                        if (!text.trim())
                            throw new Error("Model returned no answer");
                        emit({ type: "answer", text });
                    }
                }
                catch {
                    if (!controller.signal.aborted)
                        emit({ type: "failure", kind, message: `Dime ${kind} failed.` });
                }
                finally {
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
                while (!finished || events.length) {
                    const next = events.shift();
                    if (next)
                        yield next;
                    else
                        await new Promise<void>(resolve => { wake = resolve; });
                }
                await pending;
            }
            finally {
                controller.abort();
                await pending;
                signal?.removeEventListener("abort", onAbort);
            }
        }
    };
}

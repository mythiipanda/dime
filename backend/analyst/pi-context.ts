import { readFileSync } from "node:fs";
import { Type } from "typebox";
import { defineTool, ModelRuntime, type Skill } from "@earendil-works/pi-coding-agent";
import { InMemoryCredentialStore } from "@earendil-works/pi-ai";
import { Value } from "typebox/value";
import { sourceResult, sourceOutputSchema, type SourceRecord } from "./python-tools.js";

export const modelConfigSchema = Type.Object({
    provider: Type.String({ minLength: 1 }), model: Type.String({ minLength: 1 }),
    baseUrl: Type.String({ minLength: 1 }), apiKey: Type.String({ minLength: 1 }),
    contextWindow: Type.Integer({ minimum: 1 }), maxTokens: Type.Integer({ minimum: 1 }),
    headers: Type.Optional(Type.Record(Type.String(), Type.String())),
    reasoning: Type.Optional(Type.Boolean()),
    compat: Type.Optional(Type.Object({
        requiresReasoningContentOnAssistantMessages: Type.Optional(Type.Boolean()),
        thinkingFormat: Type.Optional(Type.Union([
            Type.Literal("openai"), Type.Literal("openrouter"), Type.Literal("deepseek"),
            Type.Literal("together"), Type.Literal("baseten"), Type.Literal("zai"),
            Type.Literal("qwen"), Type.Literal("chat-template"), Type.Literal("qwen-chat-template"),
            Type.Literal("string-thinking"), Type.Literal("ant-ling"),
        ])),
        supportsReasoningEffort: Type.Optional(Type.Boolean()),
    })),
});

const UVARC_MAX_IN_FLIGHT = 4;
const UVARC_RETRY_ATTEMPTS = 6;
const uvarcLimiter = (() => {
    let inFlight = 0;
    const queue: Array<() => void> = [];
    return {
        async acquire() {
            if (inFlight >= UVARC_MAX_IN_FLIGHT)
                await new Promise<void>(resolve => queue.push(resolve));
            inFlight += 1;
        },
        release() {
            inFlight -= 1;
            queue.shift()?.();
        },
    };
})();
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

function sanitizeUvarcMessages(init: RequestInit | undefined): RequestInit | undefined {
    if (!init || typeof init.body !== "string")
        return init;
    let parsed: { messages?: unknown };
    try {
        parsed = JSON.parse(init.body);
    } catch {
        return init;
    }
    if (!Array.isArray(parsed.messages))
        return init;
    let dirty = false;
    const messages = parsed.messages.map((message: unknown) => {
        if (!message || typeof message !== "object")
            return message;
        const record = { ...(message as Record<string, unknown>) };
        if (record.content === null || record.content === undefined) {
            record.content = "";
            dirty = true;
        } else if (Array.isArray(record.content) && record.content.some(item => item === null || item === undefined)) {
            record.content = record.content.filter(item => item !== null && item !== undefined);
            dirty = true;
        }
        return record;
    });
    if (!dirty)
        return init;
    return { ...init, body: JSON.stringify({ ...parsed, messages }) };
}

export function uvarcGuardedFetch(baseUrl: string, realFetch: typeof globalThis.fetch): typeof globalThis.fetch {
    return async (input, init) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        if (!url.startsWith(baseUrl))
            return realFetch(input, init);
        init = sanitizeUvarcMessages(init);
        await uvarcLimiter.acquire();
        try {
            for (let attempt = 0; ; attempt++) {
                const res = await realFetch(input, init);
                if (res.status === 400) {
                    const body = await res.clone().text().catch(() => "");
                    if (body.includes("'messages'") && attempt < UVARC_RETRY_ATTEMPTS - 1) {
                        await sleep(Math.min(1500 * 2 ** attempt, 20000) + Math.random() * 750);
                        continue;
                    }
                    if (body.includes("'messages'") || /input tokens|context length|context window/i.test(body))
                        return new Response(JSON.stringify({ error: { message: `prompt is too long: input exceeds the context window of this model (uvarc relay: ${body.slice(0, 300)})` } }),
                            { status: res.status, statusText: res.statusText, headers: { "content-type": "application/json" } });
                }
                if (res.status === 429 && attempt < UVARC_RETRY_ATTEMPTS - 1) {
                    await sleep(Math.min(1500 * 2 ** attempt, 20000) + Math.random() * 750);
                    continue;
                }
                return res;
            }
        }
        finally {
            uvarcLimiter.release();
        }
    };
}
let uvarcFetchInstalled = false;

export async function resolvedRuntime(input: unknown) {
    if (!Value.Check(modelConfigSchema, input))
        throw new Error("Explicit resolved provider configuration required");
    const config = input;
    const runtime = await ModelRuntime.create({ credentials: new InMemoryCredentialStore(), modelsPath: null, allowModelNetwork: false, refreshOnCreate: false });
    runtime.registerProvider(config.provider, {
        api: config.provider === "gemini" ? "google-generative-ai" : "openai-completions", baseUrl: config.baseUrl, apiKey: config.apiKey, headers: config.headers,
        models: [{
                id: config.model, name: config.model, input: ["text"], reasoning: config.reasoning ?? false, contextWindow: config.contextWindow, maxTokens: config.maxTokens, compat: config.compat,
                cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }
            }]
    });
    if (config.provider === "uvarc" && !uvarcFetchInstalled) {
        uvarcFetchInstalled = true;
        globalThis.fetch = uvarcGuardedFetch(config.baseUrl, globalThis.fetch);
    }
    const model = runtime.getModel(config.provider, config.model);
    if (!model)
        throw new Error("Selected model is unavailable");
    return { runtime, model };
}

export function priorSourceTool(records: SourceRecord[]) {
    const catalogue = new Map(records.map(record => [record.ref, record]));
    return defineTool({
        name: "read_source", label: "Read prior source",
        description: "Read a prior source by ref from this conversation. Returns {ref, tool, result, evidence, isError}. evidence is a compact source card; result keeps full rows. Filter result before returning from codemode; retain ref.",
        outputSchema: sourceOutputSchema,
        parameters: Type.Object({ ref: Type.String() }, { additionalProperties: false }),
        async execute(_callId, { ref }) {
            const record = catalogue.get(ref);
            if (!record)
                throw new Error("Unknown conversation source ref");
            return sourceResult(record);
        }
    });
}

const skillOutputSchema = Type.Object({
    ok: Type.Boolean(),
    name: Type.String(),
    content: Type.String(),
    available_skills: Type.Array(Type.String()),
}, { additionalProperties: false });

export function loadSkillTool(skills: readonly Skill[], onLoad?: (name: string) => void) {
    const byName = new Map(skills.map(skill => [skill.name.toLowerCase(), skill]));
    const available = skills.map(skill => skill.name).sort();
    return defineTool({
        name: "load_skill", label: "Load skill",
        description: "Load the full markdown playbook for an NBA analytical skill by name (returns {ok, name, content, available_skills}).",
        outputSchema: skillOutputSchema,
        parameters: Type.Object({ name: Type.String({ minLength: 1 }) }, { additionalProperties: false }),
        async execute(_callId, { name }) {
            const skill = byName.get(name.trim().toLowerCase());
            if (!skill) {
                const text = `Unknown skill '${name}'. Available skills: ${available.join(", ") || "none"}`;
                return {
                    content: [{ type: "text", text }],
                    details: undefined,
                    structuredContent: { ok: false, name, content: text, available_skills: available },
                };
            }
            const text = readFileSync(skill.filePath, "utf8");
            onLoad?.(skill.name);
            return {
                content: [{ type: "text", text }],
                details: undefined,
                structuredContent: { ok: true, name: skill.name, content: text, available_skills: available },
            };
        }
    });
}

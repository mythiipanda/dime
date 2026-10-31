import { Type } from "typebox";
import { defineTool, ModelRuntime } from "@earendil-works/pi-coding-agent";
import { InMemoryCredentialStore } from "@earendil-works/pi-ai";
import { Value } from "typebox/value";
import { sourceResult, sourceOutputSchema, type SourceRecord } from "./python-tools.js";
export const modelConfigSchema = Type.Object({
    provider: Type.String({ minLength: 1 }), model: Type.String({ minLength: 1 }),
    baseUrl: Type.String({ minLength: 1 }), apiKey: Type.String({ minLength: 1 }),
    contextWindow: Type.Integer({ minimum: 1 }), maxTokens: Type.Integer({ minimum: 1 }),
    headers: Type.Optional(Type.Record(Type.String(), Type.String())),
});
export async function resolvedRuntime(input: unknown) {
    if (!Value.Check(modelConfigSchema, input))
        throw new Error("Explicit resolved provider configuration required");
    const config = input;
    const runtime = await ModelRuntime.create({ credentials: new InMemoryCredentialStore(), modelsPath: null, allowModelNetwork: false, refreshOnCreate: false });
    runtime.registerProvider(config.provider, {
        api: "openai-completions", baseUrl: config.baseUrl, apiKey: config.apiKey, headers: config.headers,
        models: [{
                id: config.model, name: config.model, input: ["text"], reasoning: false, contextWindow: config.contextWindow, maxTokens: config.maxTokens,
                cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }
            }]
    });
    const model = runtime.getModel(config.provider, config.model);
    if (!model)
        throw new Error("Selected model is unavailable");
    return { runtime, model };
}
export function priorSourceTool(records: SourceRecord[]) {
    const catalogue = new Map(records.map(record => [record.ref, record]));
    return defineTool({
        name: "read_source", label: "Read prior source",
        description: "Read a prior source by ref from this conversation. Returns {ref, tool, result, isError}. Filter result before returning from codemode; retain ref. Includes units and provenance.",
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

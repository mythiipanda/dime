import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { Type } from "typebox";
import { Value } from "typebox/value";
const policies = {
    gemini: { models: ["gemini-3.5-flash", "gemini-3.8-flash", "gemma-4-31b-it", "gemini-3.5-flash-lite"], key: "GEMINI_API_KEY", url: "https://generativelanguage.googleapis.com/v1beta/openai/" },
    nvidia: { models: ["z-ai/glm-5.3-flash", "deepseek-ai/deepseek-v4.1-flash"], key: "NVIDIA_NIM_API_KEY", url: "https://integrate.api.nvidia.com/v1" },
    openrouter: { models: ["nvidia/nemotron-3-super-120b-a12b:free", "dots-studio/dots-3-note-preview:free", "openrouter/free"], key: "OPENROUTER_API_KEY", url: "https://openrouter.ai/api/v1" },
    mistral: { models: ["ministral-8b-2512"], key: "MISTRAL_API_KEY", url: "https://api.mistral.ai/v1" },
    cerebras: { models: ["gpt-oss-120b", "qwen-3.8-27b"], key: "CEREBRAS_API_KEY", url: "https://api.cerebras.ai/v1" },
    groq: { models: ["openai/gpt-oss-120b", "openai/gpt-oss-20b"], key: "GROQ_API_KEY", url: "https://api.groq.com/openai/v1" },
    agnes: { models: ["agnes-3.0-flash", "agnes-2.5-flash"], key: "AGNES_API_KEY", url: "https://apihub.agnes-ai.com/v1" },
    reflection: { models: ["Beam-1.0-501B-A23B"], key: "REFLECTION_API_KEY", url: "https://api.reflection.ai/openai/v1" },
    inception: { models: ["mercury-2.5"], key: "INCEPTION_API_KEY", url: "https://api.inceptionlabs.ai/v1" },
};
type Provider = keyof typeof policies;
function isProvider(name: string): name is Provider { return Object.hasOwn(policies, name); }
const order: Provider[] = ["groq", "agnes", "cerebras", "nvidia", "openrouter", "mistral", "gemini", "inception"];
const gated = new Set<Provider>(["groq", "agnes", "reflection", "inception"]);
const limitSchema = Type.Record(Type.String(), Type.Record(Type.String(), Type.Object({ id: Type.String(), contextWindow: Type.Integer(), maxTokens: Type.Integer() }, { additionalProperties: true })));
export function providerPolicy(env: NodeJS.ProcessEnv) {
    const enabled = (name: Provider) => !gated.has(name) || ["true", "1", "yes", "on"].includes((env["DIME_ENABLE_" + name.toUpperCase()] ?? "false").toLowerCase());
    const key = (name: Provider) => env[policies[name].key] || (name === "gemini" ? env.GOOGLE_API_KEY : "");
    const available = (name: Provider) => Boolean(enabled(name) && key(name));
    const defaultModel = (name: Provider) => {
        const value = env[(name === "nvidia" ? "NVIDIA_NIM" : name.toUpperCase()) + "_MODEL"];
        const models = policies[name].models;
        return value && (models.includes(value) || name === "mistral" || name === "inception") ? value : models[0];
    };
    function selection(id?: string) {
        const raw = (id || env.DIME_V2_MODEL || "").trim();
        const defaultProvider = order.find(available) ?? "mistral";
        if (!raw)
            return { provider: defaultProvider, model: defaultModel(defaultProvider) };
        const prefix = raw.slice(0, raw.indexOf(":"));
        let provider: Provider;
        let model: string;
        if (isProvider(prefix)) {
            provider = prefix;
            model = raw.slice(prefix.length + 1);
        }
        else {
            const match = order.find(name => policies[name].models.includes(raw));
            if (!match)
                throw new Error("Selected model is not approved");
            provider = match;
            model = raw;
        }
        if (provider === "reflection" && model === "beam-1")
            model = "Beam-1.0-501B-A23B";
        if (!policies[provider].models.includes(model) && model !== defaultModel(provider))
            throw new Error("Selected model is not approved");
        return { provider, model };
    }
    return {
        catalog() {
            const defaultProvider = order.find(available) ?? "mistral";
            const availability = Object.fromEntries(Object.keys(policies).filter(isProvider).filter(name => !gated.has(name) || available(name)).map(name => [name, available(name)]));
            return { models: ["gemini", "nvidia", "openrouter", "cerebras", "mistral", "groq", "agnes", "reflection", "inception"].filter(isProvider).filter(name => !gated.has(name) || available(name)).flatMap(name => (name === "openrouter" ? [...policies[name].models.filter(m => m !== "openrouter/free").sort(), "openrouter/free"] : name === "groq" ? [defaultModel(name)] : ["mistral", "reflection", "inception"].includes(name) ? [defaultModel(name)] : policies[name].models).map(model => ({ id: name + ":" + model, engine: name, default: name === defaultProvider && model === defaultModel(defaultProvider), available: availability[name] }))), available: availability };
        },
        resolve(id?: string) {
            const { provider, model } = selection(id);
            if (!available(provider))
                throw new Error("Selected provider is unavailable");
            // Existing Nvidia policy requires chat_template_kwargs, which this Pi adapter does not support.
            if (provider === "nvidia")
                throw new Error("Provider requires request options not yet supported by Pi adapter");
            let limits: {
                contextWindow: number;
                maxTokens: number;
            } | undefined;
            if (provider === "reflection")
                limits = { contextWindow: 1048576, maxTokens: 131072 };
            else {
                const name = provider === "gemini" ? "google" : provider;
                const data: unknown = JSON.parse(readFileSync(fileURLToPath(new URL(`../node_modules/@earendil-works/pi-ai/dist/providers/data/${name}.json`, import.meta.url)), "utf8"));
                if (!Value.Check(limitSchema, data))
                    throw new Error("Invalid SDK token metadata");
                limits = Object.values(data).flatMap(Object.values).find(entry => entry.id === model);
            }
            if (!limits)
                throw new Error("Selected model has no supported token metadata");
            const headers: Record<string, string> = provider === "openrouter" ? { "HTTP-Referer": "https://github.com/mythiipanda/dime", "X-Title": "Dime NBA Analyst" } : ["groq", "cerebras", "agnes"].includes(provider) ? { "User-Agent": "dime-agent/1.0" } : {};
            return { provider, model, apiKey: key(provider), baseUrl: policies[provider].url, headers, contextWindow: limits.contextWindow, maxTokens: limits.maxTokens };
        }
    };
}

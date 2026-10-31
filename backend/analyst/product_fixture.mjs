// Synthetic provider only. Used by product_session_test.py, never the product entrypoint.
import { writeFileSync, appendFileSync } from "node:fs";
import { join } from "node:path";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";
import { InMemoryCredentialStore, createAssistantMessageEventStream } from "@earendil-works/pi-ai";
import { serve } from "./worker.mjs";

const root = process.env.DIME_PI_TEST_ROOT;
if (!root) throw new Error("Isolated fixture root required");
writeFileSync(join(root, "worker.pid"), String(process.pid));
const write = process.stdout.write.bind(process.stdout);
process.stdout.write = (chunk, ...args) => {
  appendFileSync(join(root, "worker-events.jsonl"), chunk);
  return write(chunk, ...args);
};
await serve(async config => {
  if (config.scenario === "startup") throw new Error("fixture configuration failure");
  const runtime = await ModelRuntime.create({ credentials: new InMemoryCredentialStore(),
    modelsPath: null, allowModelNetwork: false, refreshOnCreate: false });
  let count = 0;
  runtime.registerProvider("fixture", {
    api: "openai-completions", apiKey: "fixture", baseUrl: "http://invalid.test",
    models: [{ id: "fixture", name: "fixture", input: ["text"], reasoning: false,
      contextWindow: 100000, maxTokens: 4000,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } }],
    streamSimple(model, context, options) {
      appendFileSync(join(root, "requests.jsonl"), JSON.stringify(context) + "\n");
      const stream = createAssistantMessageEventStream();
      if (config.scenario === "cancel") {
        options.signal.addEventListener("abort", () => {
          stream.push({ type: "error", reason: "aborted", error: {
            role: "assistant", api: model.api, provider: model.provider, model: model.id,
            content: [], stopReason: "aborted", timestamp: Date.now(),
            usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
              cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
          } });
          stream.end();
        }, { once: true });
        writeFileSync(join(root, "entered"), "1");
        return stream;
      }
      const first = count++ === 0 && config.scenario !== "model_immediate";
      const code = config.scenario === "followup" ? `
        const raw = await tools.read_source({ref:${JSON.stringify(config.priorRef)}});
        const data = raw.result;
        const denied = await tools.read_source({ref:"not-in-conversation"}).then(() => false, () => true);
        return {retrieved: data.rows[0].secret.length === 14 && data.rows[0].PTS === 71, unit: data.declared_column_semantics.PTS.unit, denied};
      ` : `const bad = await tools.sql_exec({sql:"SELECT missing FROM silver_leaders_pts"});
        const good = await tools.sql_exec({sql:"SELECT PTS FROM silver_leaders_pts"});
        return {bad, good};`;
      const message = { role: "assistant", api: model.api, provider: model.provider, model: model.id,
        content: first ? [{ type: "toolCall", id: "query", name: "codemode", arguments: {code} }]
          : [{ type: "text", text: "Synthetic answer with retained sources" }],
        stopReason: config.scenario.startsWith("model") && !first ? "error" : first ? "toolUse" : "stop",
        errorMessage: config.scenario.startsWith("model") ? "invalid request: fixture failure" : undefined,
        timestamp: Date.now(), usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0,
          totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
      stream.push({ type: "start", partial: message });
      if (!first && message.stopReason === "stop") {
        stream.push({ type: "text_delta", contentIndex: 0, delta: message.content[0].text, partial: message });
      }
      stream.push(message.stopReason === "error" ? {type:"error", reason:"error", error:message}
        : { type: "done", reason: message.stopReason, message });
      stream.end();
      return stream;
    },
  });
  return { runtime, model: runtime.getModel("fixture", "fixture") };
});

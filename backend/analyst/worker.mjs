import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";
import { ModelRuntime } from "@earendil-works/pi-coding-agent";
import { InMemoryCredentialStore } from "@earendil-works/pi-ai";
import { createAnalystSession } from "./runtime.mjs";
import { connectPythonTools, sourceOutputSchema, sourceResult } from "./python-tools.mjs";

export async function resolvedRuntime(config) {
  if (!config?.provider || !config?.model || !config?.baseUrl || !config?.apiKey ||
      !Number.isInteger(config.contextWindow) || config.contextWindow <= 0 ||
      !Number.isInteger(config.maxTokens) || config.maxTokens <= 0) {
    throw new Error("Explicit resolved provider configuration required");
  }
  const runtime = await ModelRuntime.create({ credentials: new InMemoryCredentialStore(),
    modelsPath: null, allowModelNetwork: false, refreshOnCreate: false });
  runtime.registerProvider(config.provider, { api: "openai-completions", baseUrl: config.baseUrl,
    apiKey: config.apiKey, headers: config.headers,
    models: [{ id: config.model, name: config.model, input: ["text"], reasoning: false,
      contextWindow: config.contextWindow, maxTokens: config.maxTokens,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } }] });
  return { runtime, model: runtime.getModel(config.provider, config.model) };
}


function sourceSummary(record) {
  const {result: data, isError} = sourceResult(record).structuredContent;
  return { ref: record.ref, tool: record.tool, failed: isError, columns: data?.columns,
    declared_column_semantics: data?.declared_column_semantics,
    season_semantics: data?.season_semantics, provenance: data?.meta };
}

export function priorSourceTool(records) {
  const catalogue = new Map(records.map(record => [record.ref, record]));
  return { name: "read_source", label: "Read prior source",
    description: "Read a prior source by ref from this conversation. Returns a native object {ref, tool, result, isError}. result contains the authoritative output or original error text. Filter result before returning from codemode; retain ref. Includes units and provenance.",
    outputSchema: sourceOutputSchema,
    parameters: { type: "object", properties: { ref: { type: "string" } }, required: ["ref"], additionalProperties: false },
    async execute(_callId, { ref }) {
      if (!catalogue.has(ref)) throw new Error("Unknown conversation source ref");
      return sourceResult(catalogue.get(ref));
    } };
}

// One stdin start followed by cancellation. EOF also cancels the request.
export async function serve(runtimeFactory = resolvedRuntime) {
  const lines = createInterface({ input: process.stdin });
  const send = value => process.stdout.write(JSON.stringify(value) + "\n");
  let session, bridge, bridgePid, pending, cancelled = false;
  const cancel = () => { cancelled = true; void session?.abort(); };
  lines.on("close", cancel);
  async function run(start) {
    let kind = "configuration";
    try {
      if (typeof start.q !== "string" || !start.q.trim() || !Array.isArray(start.history) ||
          start.history.length > 8 || start.history.some(t =>
            !["user", "assistant"].includes(t.role) || typeof t.content !== "string")) {
        throw new Error("Invalid product context");
      }
      const { runtime, model } = await runtimeFactory(start.model);
      kind = "startup";
      bridge = await connectPythonTools(start.bridge);
      bridgePid = bridge.pid;
      session = await createAnalystSession({ cwd: start.cwd, agentDir: start.agentDir,
        model, modelRuntime: runtime, tools: [...bridge.tools.map(tool => ({ ...tool,
          async execute(...args) {
            send({ type: "tool_call", name: tool.name });
            try {
              const result = await tool.execute(...args);
              const record = bridge.results.get(result.structuredContent.ref);
              send({ type: "source", record });
              const {result: domain, isError: failed} = result.structuredContent;
              send({ type: "tool_result", name: tool.name, status: failed ? "fail" : "ok",
                ...(failed ? { error: typeof domain === "string" ? domain : domain?.error ?? "Tool failed" } : {}),
                rows: Array.isArray(domain?.rows) ? domain.rows.length : undefined });
              return result;
            } catch (error) {
              send({ type: "tool_result", name: tool.name, status: "fail", error: error.message });
              throw error;
            }
          } })), priorSourceTool(start.sources ?? [])] });
      session.subscribe(event => {
        if (event.type === "message_update" && event.assistantMessageEvent?.type === "text_delta") {
          send({ type: "token", text: event.assistantMessageEvent.delta });
        }
      });
      kind = "model";
      if (cancelled) return;
      // Persisted product turns are context, never additional prompts or a second session store.
      const history = start.history.map(turn => turn.role === "user"
        ? { role: "user", content: turn.content, timestamp: Date.now() }
        : { role: "assistant", content: [{ type: "text", text: turn.content }],
            api: model.api, provider: model.provider, model: model.id,
            usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
              cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
            stopReason: "stop", timestamp: Date.now() });
      for (const message of history) session.sessionManager.appendMessage(message);
      session.agent.state.messages = [...session.agent.state.messages, ...history];
      if (start.sources?.length) {
        const context = { role: "user", content: "Prior source catalogue. Use tools.read_source({ref}) inside codemode and return only filtered results:\n" + JSON.stringify(start.sources.map(sourceSummary)), timestamp: Date.now() };
        session.sessionManager.appendMessage(context);
        session.agent.state.messages.push(context);
      }
      await session.prompt(start.q);
      if (cancelled) return;
      const last = session.messages.filter(m => m.role === "assistant").at(-1);
      if (!last || ["error", "aborted"].includes(last.stopReason)) throw new Error("Model failed");
      const text = last.content.filter(c => c.type === "text").map(c => c.text).join("");
      if (!text.trim()) throw new Error("Model returned no answer");
      send({ type: "answer", text });
    } catch {
      if (!cancelled) send({ type: "failure", kind, message: `Dime ${kind} failed.` });
    } finally {
      try { await session?.abort(); }
      finally {
        session?.dispose();
        await bridge?.close();
        send({ type: "closed", pid: bridgePid });
        lines.close();
        process.stdin.pause();
      }
    }
  }
  lines.on("line", line => {
    try {
      const message = JSON.parse(line);
      if (message.type === "cancel") cancel();
      else if (!pending && message.type === "start") pending = run(message);
      else cancel();
    } catch { cancel(); lines.close(); }
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await serve();

import { McpClient, StdioTransport } from "@earendil-works/pi-mcp";
import { randomUUID } from "node:crypto";
import { isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";

// One explicit Python process per owner; no MCP config or inherited environment.
export async function connectPythonTools({ python, cwd, env }) {
  if (!isAbsolute(python) || !isAbsolute(cwd) || !isAbsolute(env?.DIME_WAREHOUSE ?? "")) {
    throw new TypeError("Absolute python, private cwd and explicit DIME_WAREHOUSE are required");
  }
  const transport = new StdioTransport({ command: python,
    args: ["-B", fileURLToPath(new URL("./python_tools.py", import.meta.url))],
    cwd, env, inheritEnv: false, maxStderrBytes: 65536 });
  const client = new McpClient({ name: "dime-analyst", version: "1", requestTimeoutMs: 15000 });
  const results = new Map();
  try {
    await client.connect(transport);
    const catalogue = await client.listTools();
    const allowed = new Set(["sql_exec", "warehouse_schema"]);
    if (catalogue.length !== allowed.size || catalogue.some(t => !allowed.has(t.name))) {
      throw new Error("Unexpected Python tool catalogue");
    }
    const tools = catalogue.map(tool => ({ name: tool.name, label: tool.name,
      description: tool.description, parameters: tool.inputSchema,
      async execute(callId, args, signal) {
        const response = await client.callTool(tool.name, args, { signal });
        const ref = randomUUID();
        // Retain even domain failures and MCP errors; scripts may filter their output.
        const record = { ref, callId, tool: tool.name, response };
        results.set(ref, record);
        return { content: [{ type: "text", text: JSON.stringify(record) }] };
      },
    }));
    return { tools, results, get pid() { return transport.pid; },
      close: () => client.close() };
  } catch (error) {
    await client.close();
    throw new Error(`Python tool connection failed: ${error.message}\n${transport.stderr}`, { cause: error });
  }
}

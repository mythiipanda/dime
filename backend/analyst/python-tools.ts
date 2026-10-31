import { McpClient, StdioTransport, type CallToolResult, type StdioTransportOptions } from "@earendil-works/pi-mcp";
import { randomUUID } from "node:crypto";
import { isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import type { JsonValue } from "@earendil-works/pi-ai";
import { defineTool } from "@earendil-works/pi-coding-agent";
export const sourceRecordSchema = Type.Object({
    ref: Type.String(), callId: Type.String(),
    tool: Type.Union([Type.Literal("sql_exec"), Type.Literal("warehouse_schema")]),
    response: Type.Object({
        content: Type.Array(Type.Unknown()),
        structuredContent: Type.Optional(Type.Unknown()), isError: Type.Optional(Type.Boolean())
    }, { additionalProperties: true }),
}, { additionalProperties: false });
export type SourceRecord = Static<typeof sourceRecordSchema>;
export const sourceOutputSchema = Type.Object({ ref: Type.String(), tool: Type.String(), result: Type.Unknown(), isError: Type.Boolean() }, { additionalProperties: false });
const objectSchema = Type.Record(Type.String(), Type.Unknown());
export function objectValue(value: unknown) {
    return Value.Check(objectSchema, value) ? value : undefined;
}
function jsonValue(value: unknown): JsonValue {
    if (value === null || typeof value === "string" || typeof value === "boolean")
        return value;
    if (typeof value === "number" && Number.isFinite(value))
        return value;
    if (Array.isArray(value))
        return value.map(jsonValue);
    const object = objectValue(value);
    if (object)
        return Object.fromEntries(Object.entries(object).map(([key, item]) => [key, jsonValue(item)]));
    throw new TypeError("Tool returned a non-JSON value");
}
export function sourceResult(record: SourceRecord) {
    const response = record.response;
    const text = response.content.map(objectValue).filter(item => item?.type === "text").map(item => item?.text).join("\n");
    let result: unknown = response.structuredContent;
    if (result === undefined) {
        try {
            result = JSON.parse(text);
        }
        catch {
            result = text;
        }
    }
    const isError = response.isError === true || objectValue(result)?.ok === false;
    const content: {
        type: "text";
        text: string;
    }[] = isError ? [{ type: "text", text: typeof result === "string" ? result : JSON.stringify(result) }] : [];
    return { content, details: undefined, structuredContent: { ref: record.ref, tool: record.tool, result: jsonValue(result), isError }, isError };
}
export type PythonToolsOptions = {
    python: string;
    cwd: string;
    env: NonNullable<StdioTransportOptions["env"]>;
};
export async function connectPythonTools({ python, cwd, env }: PythonToolsOptions) {
    if (!isAbsolute(python) || !isAbsolute(cwd) || !isAbsolute(env.DIME_WAREHOUSE ?? "")) {
        throw new TypeError("Absolute python, private cwd and explicit DIME_WAREHOUSE are required");
    }
    const transport = new StdioTransport({
        command: python,
        args: ["-B", fileURLToPath(new URL("../python_tools.py", import.meta.url))],
        cwd, env, inheritEnv: false, maxStderrBytes: 65536
    });
    const client = new McpClient({ name: "dime-analyst", version: "1", requestTimeoutMs: 15000 });
    const results = new Map<string, SourceRecord>();
    try {
        await client.connect(transport);
        const catalogue = (await client.listTools()).filter(tool => ["sql_exec", "warehouse_schema"].includes(tool.name));
        if (catalogue.length !== 2 || !["sql_exec", "warehouse_schema"].every(name => catalogue.some(tool => tool.name === name))) {
            throw new Error("Unexpected Python tool catalogue");
        }
        // The Python catalogue remains the authority for arguments. Its JSON Schema is checked by Pi.
        const tools = catalogue.map(tool => {
            const name = tool.name;
            if (name !== "sql_exec" && name !== "warehouse_schema")
                throw new Error("Unexpected Python tool");
            return defineTool({
                name, label: name,
                description: tool.description + " Returns {ref, tool, result, isError}. Filter result before returning from codemode; retain ref.",
                parameters: Type.Unsafe<Record<string, unknown>>(tool.inputSchema), outputSchema: sourceOutputSchema,
                async execute(callId, args, signal) {
                    const response: CallToolResult = await client.callTool(name, args, { signal });
                    const record: SourceRecord = { ref: randomUUID(), callId, tool: name, response };
                    results.set(record.ref, record);
                    return sourceResult(record);
                }
            });
        });
        return { tools, results, get pid() { return transport.pid; }, close: () => client.close() };
    }
    catch (error) {
        await client.close();
        throw new Error(`Python tool connection failed: ${error instanceof Error ? error.message : String(error)}\n${transport.stderr}`, { cause: error });
    }
}

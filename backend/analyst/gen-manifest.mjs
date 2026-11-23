import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const dir = fileURLToPath(new URL(".", import.meta.url));
const manifest = JSON.parse(readFileSync(new URL("tools/manifest.json", import.meta.url), "utf8"));

const out = [];
out.push("export const TOOL_NAMES = [");
for (const tool of manifest.tools) out.push(`    ${JSON.stringify(tool.name)},`);
out.push("] as const;");
out.push("");
out.push("export const NAMESPACE_DESCRIPTIONS = {");
for (const [name, description] of Object.entries(manifest.namespaces)) {
    out.push(`    ${JSON.stringify(name)}: { name: ${JSON.stringify(name)}, description: ${JSON.stringify(description)} },`);
}
out.push("} as const;");
out.push("");
out.push("export const TOOL_NAMESPACES = {");
for (const tool of manifest.tools) {
    if (tool.namespace) out.push(`    ${JSON.stringify(tool.name)}: ${JSON.stringify(tool.namespace)},`);
}
out.push("} as const;");
out.push("");
out.push("export const TOOL_PROMPT_GUIDELINES: Partial<Record<string, string[]>> = {");
for (const tool of manifest.tools) {
    if (tool.guidelines?.length) {
        out.push(`    ${JSON.stringify(tool.name)}: [`);
        for (const g of tool.guidelines) out.push(`        ${JSON.stringify(g)},`);
        out.push("    ],");
    }
}
out.push("};");
out.push("");

writeFileSync(new URL("tool-manifest.generated.ts", import.meta.url), out.join("\n"));

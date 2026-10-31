import { createHash } from "node:crypto";
import { readdirSync, readFileSync, lstatSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import { execFileSync } from "node:child_process";
import { isDeepStrictEqual } from "node:util";
import { backendRoot } from "./analyst.js";
import type { DirectData } from "./direct-data.js";
const sha = (data: Uint8Array) => createHash("sha256").update(data).digest("hex");
function files(root: string): string[] {
    return readdirSync(root, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name)).flatMap(entry => {
        const path = join(root, entry.name);
        if (["node_modules", "__pycache__"].includes(entry.name))
            return [];
        if (lstatSync(path).isSymbolicLink())
            throw new Error("executable source tree cannot contain symlinks");
        return entry.isDirectory() ? files(path) : [path];
    });
}
const loadedModules = Object.fromEntries(files(join(backendRoot, "analyst/dist")).filter(path => path.endsWith(".js")).map(path => [relative(join(backendRoot, "analyst"), path).split(sep).join("/"), sha(readFileSync(path))]));
for (const name of ["package-lock.json", "python_tools.py", "direct_data.py", "dataset_engine.py", "http-assets/openapi.json", "http-assets/docs.html", "http-assets/redoc.html", "http-assets/oauth2-redirect.html"])
    loadedModules[name] = sha(readFileSync(join(backendRoot, "analyst", name)));
export async function runtimeManifest(data: DirectData, env: NodeJS.ProcessEnv) {
    const modules = { ...loadedModules };
    const digest = createHash("sha256");
    for (const root of ["v2", "analyst", "shared"]) {
        for (const path of files(join(backendRoot, root)).filter(path => /\.(py|md|mjs|js|ts|json)$/.test(path))) {
            digest.update(relative(backendRoot, path).split(sep).join("/"));
            digest.update("\0");
            digest.update(readFileSync(path));
            digest.update("\0");
        }
    }
    let revision = env.DIME_REVISION;
    if (!revision) {
        try {
            revision = execFileSync("git", ["rev-parse", "HEAD"], { cwd: backendRoot, timeout: 2000, stdio: ["ignore", "pipe", "ignore"], encoding: "utf8" }).trim();
        }
        catch {
            revision = "unknown";
        }
    }
    const assets = { provider_schema_manifest: "v2/schema_snapshots/manifest.json", behavior_losses: "v2/schema_snapshots/behavior_losses.json", capability_manifest: "v2/capability_snapshots/manifest.json", capability_source: "v2/capability_snapshots/catalog.source.json", capability_compiled: "v2/capability_snapshots/catalog.compiled.json" };
    const identity = await data.call("product_warehouse_identity", {});
    return deepFreeze({ revision, executable_sha256: digest.digest("hex"), module_sha256: modules, warehouse: identity.warehouse, semantic_baseline: identity.semantic_baseline, prompt_sha256: { pi_runtime: modules["dist/runtime.js"] }, typed_argument_assets: Object.fromEntries(Object.entries(assets).map(([name, path]) => [name, sha(readFileSync(join(backendRoot, path)))])) });
}
export function preflight(manifest: Awaited<ReturnType<typeof runtimeManifest>>, path: string | undefined) {
    if (!path)
        throw new Error("DIME_EXPECTED_ASSET_MANIFEST is required");
    const absolute = resolve(path);
    if (["app", "v2", "analyst", "shared"].some(root => absolute.startsWith(join(backendRoot, root) + sep)))
        throw new Error("expected asset manifest must be external to executable roots");
    const expected: unknown = JSON.parse(readFileSync(absolute, "utf8"));
    if (typeof expected !== "object" || expected === null || !("revision" in expected))
        throw new Error("expected asset manifest has wrong fields");
    const { revision, ...observed } = manifest;
    const { revision: expectedRevision, ...recorded } = expected;
    if (!isDeepStrictEqual(observed, recorded))
        throw new Error("startup asset manifest substantive mismatch");
    if (revision !== expectedRevision)
        process.stderr.write("startup asset revision label mismatch\n");
}
function deepFreeze<T>(value: T): T {
    if (value && typeof value === "object") {
        Object.freeze(value);
        for (const child of Object.values(value))
            deepFreeze(child);
    }
    return value;
}

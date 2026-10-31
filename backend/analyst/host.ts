import { execFileSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import { createAnalyst, dataEnvironment, productPaths } from "./analyst.js";
import { connectDirectData } from "./direct-data.js";
import { createProductServer } from "./http.js";
import { runtimeManifest, preflight } from "./manifest.js";
type ResolveModel = NonNullable<Parameters<typeof createAnalyst>[0]["resolveModel"]>;
export async function openProduct(env: NodeJS.ProcessEnv, resolveModel?: ResolveModel) {
    const python = env.DIME_PI_PYTHON ?? execFileSync("python", ["-c", "import sys; print(sys.executable)"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
    const paths = productPaths(env);
    await mkdir(paths.private, { recursive: true });
    const data = await connectDirectData({ python, cwd: paths.private, env: dataEnvironment(env, paths.private) });
    const analyst = createAnalyst({ env, python, resolveModel, saveChat: async (thread, role, content, owner) => { await data.call("product_save_chat", { thread, role, content, owner }); }, saveRun: async (thread, question, answer, owner, run_id) => { await data.call("product_save_run", { thread, question, answer, owner, run_id }); } });
    return { data, analyst };
}
export async function main(args: string[], env = process.env, resolveModel?: ResolveModel) {
    const product = await openProduct(env, resolveModel);
    let server: ReturnType<typeof createProductServer> | undefined;
    try {
        if (args[0] === "chat") {
            const { values, positionals } = parseArgs({ args: args.slice(1), options: { model: { type: "string" } }, allowPositionals: true });
            const question = positionals[0];
            if (positionals.length !== 1)
                throw new Error("Usage: node host.js chat <question> [--model provider:model]");
            const controller = new AbortController();
            const cancel = () => controller.abort();
            process.once("SIGINT", cancel);
            process.once("SIGTERM", cancel);
            try {
                let settled = false;
                for await (const event of product.analyst.stream({ q: question, ...(values.model ? { model: values.model } : {}) }, controller.signal)) {
                    if (event.type === "final_answer") {
                        settled = true;
                        process.stdout.write(String(event.data.text) + "\n");
                        const carry = event.data.carry;
                        if (carry && typeof carry === "object" && "source_refs" in carry && Array.isArray(carry.source_refs))
                            for (const ref of carry.source_refs)
                                process.stderr.write("source: " + String(ref) + "\n");
                    }
                    if (event.type === "work_log")
                        process.stderr.write("run: " + String(event.data.run_id) + "\n");
                    if (event.type === "failure")
                        throw new Error(String(event.data.message));
                }
                if (!settled)
                    throw new Error("Dime could not finish this run.");
            }
            finally {
                process.off("SIGINT", cancel);
                process.off("SIGTERM", cancel);
            }
            return;
        }
        const manifest = await runtimeManifest(product.data, env);
        if (args[0] === "manifest") {
            if (!args[1])
                throw new Error("Manifest output path required");
            const path = resolve(args[1]);
            await mkdir(dirname(path), { recursive: true });
            await writeFile(path, JSON.stringify(manifest, null, 2) + "\n");
            return;
        }
        preflight(manifest, env.DIME_EXPECTED_ASSET_MANIFEST);
        server = createProductServer({ ...product, env, manifest });
        await new Promise<void>(resolve => server?.listen(Number(env.PORT ?? 8000), "0.0.0.0", resolve));
        await new Promise<void>(resolve => { const stop = () => { server?.close(() => resolve()); server?.closeAllConnections(); }; process.once("SIGTERM", stop); process.once("SIGINT", stop); });
    }
    finally {
        await product.data.close();
    }
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
    main(process.argv.slice(2)).catch(() => { process.stderr.write("Dime host failed.\n"); process.exitCode = 1; });
}

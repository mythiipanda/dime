import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createAnalyst } from "./dist/analyst.js";
import { createProductServer } from "./dist/http.js";

const source = readFileSync(new URL("./http.ts", import.meta.url), "utf8");

function declaredRoutes(text) {
  const out = [];
  const re = /route\("(GET|POST|PATCH|DELETE|PUT)",\s*(\/(?:\\\/|\\\\|[^/\\\n])+\/)\s*,/g;
  let m;
  while ((m = re.exec(text))) out.push({ method: m[1], patternSource: m[2].slice(1, -1) });
  return out;
}

function probePath(patternSource) {
  let p = patternSource;
  assert.ok(p.startsWith("^"), `pattern must be anchored at start: ${patternSource}`);
  assert.ok(p.endsWith("$"), `pattern must be anchored at end: ${patternSource}`);
  p = p.slice(1, -1);
  p = p.replace(/\(\[\^\/\]\+\)/g, "x");
  p = p.replace(/\(([^()]+)\)/g, (_, inner) => inner.split("|")[0]);
  p = p.replaceAll("\\/", "/").replaceAll("\\.", ".");
  assert.ok(!/[()+?*\[\]\\^$]/.test(p), `probe path still carries regex syntax: ${p} from ${patternSource}`);
  return p;
}

function fixture() {
  const root = mkdtempSync(join(tmpdir(), "dime-routes-"));
  const env = { ...process.env, DIME_CONVERSATION_STORE: join(root, "chat.sqlite"), DIME_PROJECT_STORE: join(root, "projects.sqlite"), DIME_WORKSPACE_STORE: join(root, "workspaces.sqlite") };
  const data = { close: async () => {}, call: async () => ({ ok: true }) };
  const analyst = createAnalyst({ env, resolveModel: () => { throw new Error("No provider required"); }, saveChat: async () => {}, saveRun: async () => {} });
  const server = createProductServer({ env, data, analyst, manifest: {} });
  return { server, root };
}

test("every route declared in http.ts resolves at boot, not only after another handler runs", async () => {
  const declared = declaredRoutes(source);
  assert.ok(declared.length >= 40, `expected at least 40 route declarations in http.ts, found ${declared.length}`);
  const probes = declared.map(({ method, patternSource }) => ({ method, patternSource, path: probePath(patternSource) }));
  for (const docPath of ["/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"]) probes.push({ method: "GET", patternSource: "docs-assets-loop", path: docPath });
  const failures = [];
  for (const probe of probes) {
    const { server, root } = fixture();
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    const url = `http://127.0.0.1:${server.address().port}`;
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 3000);
      let status;
      try {
        const response = await fetch(url + probe.path, {
          method: probe.method,
          headers: { "content-type": "application/json" },
          ...(probe.method === "GET" ? {} : { body: "{}" }),
          signal: controller.signal,
        });
        status = response.status;
        await response.body?.cancel().catch(() => {});
      } catch (error) {
        status = error.name === "AbortError" ? "timeout" : String(error);
      } finally {
        clearTimeout(timer);
      }
      if (status === 404 || status === 405 || status === "timeout") failures.push(`${probe.method} ${probe.path} -> ${status} (pattern ${probe.patternSource})`);
    } finally {
      server.close();
      rmSync(root, { recursive: true, force: true });
    }
  }
  assert.deepEqual(failures, [], `${failures.length} declared routes did not resolve on a fresh boot:\n${failures.join("\n")}`);
  console.log(`Route table boot: ${probes.length} declared routes all resolve on fresh boots`);
});

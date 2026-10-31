import { createHash } from "node:crypto";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { join, basename } from "node:path";
import { Type, type TSchema, type Static } from "typebox";
import { Value } from "typebox/value";
import { validationDetails, validationDetail } from "./http-validation.js";
import { createAnalyst, analystRequestSchema, backendRoot, newRunId, encodeEvent } from "./analyst.js";
import { ProjectStore, WorkspaceStore } from "./catalog-stores.js";
import { providerPolicy } from "./providers.js";
import { objectValue } from "./python-tools.js";
import type { DirectData } from "./direct-data.js";
export class HttpError extends Error {
    constructor(readonly status: number, readonly detail: unknown, readonly headers: Record<string, string> = {}) { super(typeof detail === "string" ? detail : "Request failed"); }
}
const text = (max = 2000) => Type.String({ minLength: 1, maxLength: max, pattern: "\\S" });
const workspaceCreate = Type.Object({ name: Type.String({ minLength: 1, maxLength: 256 }), owner: Type.String({ minLength: 1, maxLength: 256 }) }, { additionalProperties: false });
const members = Type.Optional(Type.Union([Type.Array(Type.String(), { maxItems: 1024 }), Type.Null()]));
const workspaceUpdate = Type.Object({ name: Type.Optional(Type.Union([Type.String({ minLength: 1, maxLength: 256 }), Type.Null()])), add_thread_ids: members, remove_thread_ids: members, add_brief_ids: members, remove_brief_ids: members }, { additionalProperties: false });
const branchCreate = Type.Object({ thread: text(80), client: text(80), parent_sequence: Type.Integer({ minimum: 1 }), branch_id: Type.Optional(Type.Union([text(64), Type.Null()])) }, { additionalProperties: false });
const tradeSchema = Type.Object({ team_a: Type.Optional(Type.String()), team_b: Type.Optional(Type.String()), players_a: Type.Optional(Type.Union([Type.String(), Type.Array(Type.String())])), players_b: Type.Optional(Type.Union([Type.String(), Type.Array(Type.String())])), season: Type.Optional(Type.String()) }, { additionalProperties: false });
const watchSchema = Type.Object({ entity_type: Type.String(), entity_id: Type.String(), season: Type.Optional(Type.String()) });
const CORS_ALLOWED_METHODS = ["GET", "POST", "PATCH", "DELETE"];
const CORS_ALLOWED_METHODS_HEADER = CORS_ALLOWED_METHODS.join(", ");
export function parseBody<S extends TSchema>(schema: S, input: unknown): Static<S> {
    if (!Value.Check(schema, input))
        throw new HttpError(422, validationDetails(schema, input));
    return input;
}
async function body(req: IncomingMessage): Promise<unknown> {
    let value = "";
    for await (const chunk of req)
        value += String(chunk);
    try {
        return JSON.parse(value);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : "JSON decode error";
        const match = /position (\d+)/.exec(message);
        const loc: (string | number)[] = match ? ["body", Number(match[1])] : ["body"];
        throw new HttpError(422, [validationDetail("json_invalid", loc, "JSON decode error", {}, { error: message })]);
    }
}
function json(res: ServerResponse, value: unknown, status = 200) { res.writeHead(status, { "content-type": "application/json" }); res.end(JSON.stringify(value)); }
function identity(url: URL) {
    const owner = (url.searchParams.get("client") ?? "").trim().slice(0, 80), thread = (url.searchParams.get("thread") ?? "").trim().slice(0, 80);
    if (!owner || !thread)
        throw new HttpError(400, "thread and client required");
    return { owner, thread };
}
function integer(url: URL, name: string, fallback: number, min?: number, max?: number) {
    const raw = url.searchParams.get(name);
    if (raw === null)
        return fallback;
    const n = Number(raw);
    const fail = (type: string, msg: string, ctx?: Record<string, unknown>) => { throw new HttpError(422, [validationDetail(type, ["query", name], msg, raw, ctx)]); };
    if (!/^[+-]?\d+(?:\.0+)?$/.test(raw.trim()) || !Number.isInteger(n))
        fail("int_parsing", "Input should be a valid integer, unable to parse string as an integer");
    if (min !== undefined && n < min)
        fail("greater_than_equal", `Input should be greater than or equal to ${min}`, { ge: min });
    if (max !== undefined && n > max)
        fail("less_than_equal", `Input should be less than or equal to ${max}`, { le: max });
    return n;
}
function queryBoolean(url: URL, name: string) {
    const raw = url.searchParams.get(name);
    if (raw === null)
        return false;
    if (["1", "true", "on", "yes", "y", "t"].includes(raw.toLowerCase()))
        return true;
    if (["0", "false", "off", "no", "n", "f"].includes(raw.toLowerCase()))
        return false;
    throw new HttpError(422, [validationDetail("bool_parsing", ["query", name], "Input should be a valid boolean, unable to interpret input", raw)]);
}
function enabled(env: NodeJS.ProcessEnv) {
    const mode = (env.DIME_RUNTIME_V2 ?? "").trim().toLowerCase();
    if (!["", "on", "off", "shadow", "action_loop"].includes(mode))
        throw new Error("unknown DIME_RUNTIME_V2 value");
    return ["", "on", "action_loop"].includes(mode);
}
class RateWindow {
    private hits = new Map<string, number[]>();
    take(key: string, limit: number, seconds: number) {
        const now = Date.now() / 1000, active = (this.hits.get(key) ?? []).filter(t => now - t < seconds);
        this.hits.set(key, active);
        if (active.length >= limit)
            return Math.max(1, Math.ceil(active[0] + seconds - now));
        active.push(now);
        return 0;
    }
}
export function createProductServer(options: {
    env: NodeJS.ProcessEnv;
    data: DirectData;
    analyst: ReturnType<typeof createAnalyst>;
    manifest: Record<string, unknown>;
    cardsDir?: string;
}) {
    const { env, data, analyst } = options, policy = providerPolicy(env);
    const projects = new ProjectStore(env.DIME_PROJECT_STORE ?? join(backendRoot, "data/v2-projects.sqlite3"));
    const workspaces = new WorkspaceStore(env.DIME_WORKSPACE_STORE ?? join(backendRoot, "data/workspaces.sqlite3"));
    const chatRate = new RateWindow(), sqlRate = new RateWindow();
    const requireProjects = () => {
        if (!enabled(env))
            throw new HttpError(404, "not found");
    };
    type Context = {
        req: IncomingMessage;
        res: ServerResponse;
        url: URL;
        params: string[];
    };
    type Handler = (ctx: Context) => Promise<void>;
    const routes: {
        method: string;
        pattern: RegExp;
        run: Handler;
    }[] = [];
    const route = (method: string, pattern: RegExp, run: Handler) => routes.push({ method, pattern, run });
    for (const [path, file, contentType] of [["/openapi.json", "openapi.json", "application/json"], ["/docs", "docs.html", "text/html; charset=utf-8"], ["/redoc", "redoc.html", "text/html; charset=utf-8"], ["/docs/oauth2-redirect", "oauth2-redirect.html", "text/html; charset=utf-8"]]) {
        route("GET", new RegExp("^" + path.replaceAll(".", "\\.") + "$"), async ({ res }) => { res.writeHead(200, { "content-type": contentType }); res.end(await readFile(join(backendRoot, "analyst/http-assets", file))); });
    }
    route("GET", /^\/$/, async ({ res }) => json(res, { ok: true, docs: "/docs", runtime: "v2" }));
    route("GET", /^\/api\/revision$/, async ({ res }) => json(res, options.manifest));
    route("GET", /^\/api\/models$/, async ({ res }) => json(res, policy.catalog()));
    route("GET", /^\/api\/health$/, async ({ res }) => json(res, { ok: true, providers: policy.catalog().available }));
    route("GET", /^\/api\/healthz$/, async ({ res }) => { const result = await data.call("product_warehouse_health", {}); json(res, result, result.ok ? 200 : 503); });
    route("GET", /^\/api\/datasets\/freshness$/, async ({ res }) => json(res, await data.call("product_freshness", {})));
    route("GET", /^\/api\/datasets\/([^/]+)$/, async ({ res, url, params }) => {
        const q = (name: string, fallback = "") => url.searchParams.get(name) ?? fallback;
        const result = await data.call("product_dataset", { name: params[0], season: q("season", "2025-26"), player_id: integer(url, "player_id", 0), team_id: integer(url, "team_id", 0), game_id: q("game_id"), game_date: q("game_date"), stat: q("stat", "PTS"), ids: q("ids"), player_a: q("player_a"), player_b: q("player_b"), fmt: q("fmt", "json") });
        if (result.encoding === "base64" && typeof result.body === "string" && typeof result.media_type === "string") {
            res.writeHead(200, { "content-type": result.media_type + (result.media_type.startsWith("text/") ? "; charset=utf-8" : "") });
            res.end(Buffer.from(result.body, "base64"));
        }
        else
            json(res, result);
    });
    route("GET", /^\/api\/threads$/, async ({ res, url }) => json(res, await data.call("product_threads", { owner: (url.searchParams.get("client") ?? "").slice(0, 80) })));
    route("GET", /^\/api\/threads\/([^/]+)\/runs$/, async ({ res, url, params }) => json(res, await data.call("product_runs", { owner: (url.searchParams.get("client") ?? "").slice(0, 80), thread: params[0] })));
    route("GET", /^\/api\/threads\/([^/]+)\/export$/, async ({ res, url, params }) => {
        const result = await data.call("product_runs", { owner: (url.searchParams.get("client") ?? "").slice(0, 80), thread: params[0] });
        const runs = Array.isArray(result.runs) ? result.runs : [];
        const lines = [`# Dime analysis thread ${params[0]}`, ""];
        for (const raw of runs.reverse()) {
            const run = objectValue(raw);
            if (!run)
                throw new Error("Invalid run");
            lines.push(`## Q: ${run.question}`, "", String(run.answer ?? ""), "");
            for (const table of Array.isArray(run.tables) ? run.tables : []) {
                const value = objectValue(table);
                if (value)
                    lines.push(...exportTable(value));
            }
            lines.push("");
        }
        res.writeHead(200, { "content-type": "text/markdown; charset=utf-8" });
        res.end(lines.join("\n"));
    });
    route("POST", /^\/api\/v2\/branches$/, async ({ req, res }) => {
        requireProjects();
        const input = parseBody(branchCreate, await body(req));
        try {
            json(res, analyst.store.createBranch({ owner: input.client.trim(), thread: input.thread.trim() }, input.parent_sequence, input.branch_id), 201);
        }
        catch (error) {
            const message = error instanceof Error ? error.message : "Invalid branch";
            throw new HttpError(message.includes("duplicate branch") ? 409 : 400, message);
        }
    });
    route("GET", /^\/api\/v2\/branches$/, async ({ res, url }) => { requireProjects(); json(res, { branches: analyst.store.branches(identity(url)) }); });
    route("GET", /^\/api\/v2\/branches\/([^/]+)$/, async ({ res, url, params }) => {
        requireProjects();
        const owner = identity(url), branch = analyst.store.branches(owner).find(item => item.branch_id === params[0]);
        if (!branch)
            throw new HttpError(404, "branch not found");
        json(res, { branch, ...analyst.store.branchCounts(owner, params[0]) });
    });
    route("GET", /^\/api\/v2\/runs\/([^/]+)\/sources$/, async ({ res, url, params }) => {
        requireProjects();
        const owner = identity(url);
        try {
            json(res, analyst.store.readSources(owner, params[0]));
        }
        catch {
            throw new HttpError(404, "not found");
        }
    });
    route("POST", /^\/api\/projects$/, async ({ req, res }) => { requireProjects(); const input = parseBody(Type.Object({ goal: text() }, { additionalProperties: false }), await body(req)); json(res, projects.create(input.goal), 201); });
    route("GET", /^\/api\/projects$/, async ({ res }) => { requireProjects(); json(res, { projects: projects.list() }); });
    route("GET", /^\/api\/projects\/([^/]+)$/, async ({ res, params }) => {
        requireProjects();
        const result = projects.get(params[0]);
        if (!result)
            throw new HttpError(404, "project not found");
        json(res, result);
    });
    route("POST", /^\/api\/workspaces$/, async ({ req, res }) => {
        const input = parseBody(workspaceCreate, await body(req));
        if (!input.name.trim())
            throw new HttpError(422, "workspace name must be non-empty");
        if (!input.owner.trim())
            throw new HttpError(422, "workspace owner must be non-empty");
        const result = workspaces.create(input.name, input.owner);
        json(res, { ...workspaces.public(result.workspace), owner_token: result.token }, 201);
    });
    route("GET", /^\/api\/workspaces\/([^/]+)$/, async ({ res, params }) => {
        const value = workspaces.get(params[0]);
        if (!value)
            throw new HttpError(404, "workspace not found");
        json(res, workspaces.public(value));
    });
    const authorizedWorkspace = (req: IncomingMessage, id: string) => {
        const workspace = workspaces.get(id);
        if (!workspace)
            throw new HttpError(404, "workspace not found");
        const token = req.headers["x-owner-token"];
        if (token === undefined)
            throw new HttpError(401, "owner token required");
        if (typeof token !== "string" || !workspaces.verify(workspace, token))
            throw new HttpError(403, "owner token rejected");
        return workspace;
    };
    route("PATCH", /^\/api\/workspaces\/([^/]+)$/, async ({ req, res, params }) => {
        const input = parseBody(workspaceUpdate, await body(req));
        const workspace = authorizedWorkspace(req, params[0]);
        try {
            json(res, workspaces.public(workspaces.update(workspace, input)));
        }
        catch (error) {
            throw new HttpError(422, error instanceof Error ? error.message : "Invalid workspace");
        }
    });
    route("DELETE", /^\/api\/workspaces\/([^/]+)$/, async ({ req, res, params }) => { authorizedWorkspace(req, params[0]); workspaces.delete(params[0]); json(res, { ok: true, id: params[0] }); });
    route("POST", /^\/api\/sql\/rerun$/, async ({ req, res }) => {
        const input = parseBody(Type.Object({ sql: Type.Optional(Type.String()) }, { additionalProperties: false }), await body(req));
        const wait = sqlRate.take(req.socket.remoteAddress ?? "unknown", positive(env.DIME_SQL_RERUN_RATE_LIMIT, 30), positive(env.DIME_SQL_RERUN_RATE_WINDOW_S, 60));
        if (wait)
            throw new HttpError(429, "Too Many Requests", { "Retry-After": String(wait) });
        const sql = (input.sql ?? "").trim();
        if (!sql || sql.length > 8000) {
            json(res, { ok: false, error: sql ? "sql too long" : "sql required", rows: {} });
            return;
        }
        const out = await data.call("product_rerun", { sql });
        json(res, out.ok ? { ok: true, rows: { columns: out.columns, rows: out.rows, ms: out.ms ?? 0, capped: out.capped ?? false } } : { ok: false, error: out.error ?? "rerun failed", rows: {} });
    });
    route("GET", /^\/api\/resolve$/, async ({ res, url }) => json(res, await data.call("product_resolve", { query: (url.searchParams.get("q") ?? "").slice(0, 80) })));
    route("POST", /^\/api\/trade\/check$/, async ({ req, res }) => { const input = parseBody(tradeSchema, await body(req)); const players = (value: string | string[] | undefined) => Array.isArray(value) ? value.map(s => s.trim()).filter(Boolean).join(", ") : value ?? ""; json(res, await data.call("product_trade", { team_a: input.team_a ?? "", team_b: input.team_b ?? "", players_a: players(input.players_a), players_b: players(input.players_b), season: input.season ?? "2025-26" })); });
    route("GET", /^\/api\/debate-card$/, async ({ res, url }) => {
        const a = (url.searchParams.get("a") ?? "").trim().slice(0, 80), b = (url.searchParams.get("b") ?? "").trim().slice(0, 80);
        if (!a || !b) {
            json(res, { ok: false, error: "two player names required" });
            return;
        }
        const value = await data.call("product_debate", { a, b, season: url.searchParams.get("season") ?? "2025-26" });
        const result = objectValue(value.result);
        if (!result?.ok) {
            json(res, { ok: false, error: result?.error ?? value.error ?? "debate card failed" });
            return;
        }
        const rows = objectValue(result.rows), path = basename(String(rows?.path ?? "")), players = rows?.players ?? [a, b], link = `/api/debate-card/file?name=${path}`;
        json(res, { ok: true, path, players, url: link, rows: { path, players, url: link }, meta: { season: value.season } });
    });
    route("GET", /^\/api\/debate-card\/file$/, async ({ res, url }) => {
        const name = url.searchParams.get("name") ?? "";
        if (!/^debate_[A-Za-z0-9]+_vs_[A-Za-z0-9]+_[0-9]+\.html$/.test(name))
            throw new HttpError(400, "invalid file name");
        const path = join(options.cardsDir ?? join(backendRoot, "data/cards"), name);
        let info;
        try {
            info = await stat(path);
        }
        catch {
            throw new HttpError(404, "not found");
        }
        if (!info.isFile())
            throw new HttpError(404, "not found");
        res.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=3600", "content-length": info.size, "last-modified": info.mtime.toUTCString(), "etag": createHash("md5").update(String(info.mtimeMs / 1000) + "-" + info.size).digest("hex") });
        res.end(await readFile(path));
    });
    route("GET", /^\/api\/today$/, async ({ res, url }) => json(res, await data.call("product_today", { season: url.searchParams.get("season") ?? "2025-26" })));
    route("GET", /^\/api\/watchlist$/, async ({ res, url }) => json(res, await data.call("product_watchlist", { season: url.searchParams.get("season") ?? "2025-26" })));
    route("POST", /^\/api\/watchlist$/, async ({ req, res }) => { const input = parseBody(watchSchema, await body(req)); json(res, await data.call("product_watchlist_add", { ...input, season: input.season ?? "2025-26" })); });
    route("DELETE", /^\/api\/watchlist$/, async ({ res, url }) => {
        const entity_type = url.searchParams.get("entity_type"), entity_id = url.searchParams.get("entity_id");
        if (entity_type === null || entity_id === null)
            throw new HttpError(422, [["entity_type", entity_type], ["entity_id", entity_id]].filter(([, value]) => value === null).map(([name]) => validationDetail("missing", ["query", String(name)], "Field required", null)));
        json(res, await data.call("product_watchlist_remove", { entity_type, entity_id }));
    });
    route("GET", /^\/api\/movers$/, async ({ res, url }) => json(res, await data.call("product_movers", { season: url.searchParams.get("season") ?? "2025-26", days: integer(url, "days", 7, 1, 30) })));
    route("GET", /^\/api\/briefing$/, async ({ res, url }) => json(res, await data.call("product_briefing", { season: url.searchParams.get("season") ?? "2025-26" })));
    const chat: Handler = async ({ req, res, url }) => {
        const rawInput = req.method === "POST" ? await body(req) : { q: url.searchParams.get("q") ?? "", model: url.searchParams.get("model"), thread: url.searchParams.get("thread"), client: url.searchParams.get("client") ?? (url.searchParams.has("thread") ? req.headers["x-dime-client"] ?? null : null), diagnostics: queryBoolean(url, "diagnostics") };
        if (req.method === "GET" && !Value.Check(analystRequestSchema, rawInput))
            throw new Error("Invalid GET chat");
        const input = parseBody(analystRequestSchema, rawInput);
        if (input.thread && !input.client) {
            if (req.method === "GET")
                throw new Error("Invalid GET identity");
            throw new HttpError(422, [validationDetail("value_error", ["body"], "Value error, thread and client must be provided together", rawInput, { error: {} })]);
        }
        const limited = chatRate.take(req.socket.remoteAddress ?? "unknown", Number(env.CHAT_RATE_PER_MINUTE ?? 20), 60);
        if (limited) {
            res.writeHead(200, { "content-type": "text/event-stream; charset=utf-8" });
            res.end(encodeEvent({ type: "failure", data: { kind: "rate_limited", message: "rate limited, retry soon" } }) + encodeEvent({ type: "error", data: { message: "rate limited, retry soon" } }) + encodeEvent({ type: "graph_end", data: {} }));
            return;
        }
        requireProjects();
        const run = newRunId(), controller = new AbortController();
        const abort = () => controller.abort();
        res.on("close", abort);
        const timer = setTimeout(abort, positive(env.DIME_V2_RUN_TIMEOUT_S, 360) * 1000);
        let heartbeat: ReturnType<typeof setTimeout> | undefined;
        const resetHeartbeat = () => { clearTimeout(heartbeat); heartbeat = setTimeout(() => { res.write(encodeEvent({ type: "ping", data: { ok: true } })); resetHeartbeat(); }, 15000); };
        resetHeartbeat();
        res.writeHead(200, { "content-type": "text/event-stream; charset=utf-8", "x-dime-run-id": run });
        try {
            for await (const event of analyst.stream(input, controller.signal, run)) {
                res.write(encodeEvent(event));
                resetHeartbeat();
            }
            if (controller.signal.aborted && !res.destroyed) {
                res.write(encodeEvent({ type: "failure", data: { kind: "timeout", message: "The run timed out before finishing." } }));
                res.write(encodeEvent({ type: "graph_end", data: {} }));
            }
        }
        finally {
            clearTimeout(timer);
            clearTimeout(heartbeat);
            res.off("close", abort);
            res.end();
        }
    };
    route("GET", /^\/api\/v2\/chat\/stream$/, chat);
    route("POST", /^\/api\/v2\/chat\/stream$/, chat);
    const origins = (env.CORS_ALLOWED_ORIGINS ?? "http://localhost:3000,https://dime-fawn.vercel.app,http://127.0.0.1:3000").split(",").map(s => s.trim());
    return createServer((req, res) => {
        void (async () => {
            const origin = req.headers.origin;
            const wildcard = origins.includes("*");
            if (origin && wildcard)
                res.setHeader("access-control-allow-origin", "*");
            if (origin && ((!wildcard && origins.includes(origin)) || (wildcard && req.headers.cookie))) {
                res.setHeader("vary", "Origin");
                res.setHeader("access-control-allow-origin", origin);
            }
            if (origin && req.method === "OPTIONS" && req.headers["access-control-request-method"]) {
                if (!wildcard)
                    res.setHeader("vary", "Origin");
                else
                    res.removeHeader("vary");
                res.setHeader("access-control-allow-methods", CORS_ALLOWED_METHODS_HEADER);
                res.setHeader("access-control-max-age", "600");
                const requested = req.headers["access-control-request-headers"];
                if (requested)
                    res.setHeader("access-control-allow-headers", requested);
                const failures = [];
                if (!wildcard && !origins.includes(origin))
                    failures.push("origin");
                if (!CORS_ALLOWED_METHODS.includes(String(req.headers["access-control-request-method"])))
                    failures.push("method");
                res.writeHead(failures.length ? 400 : 200, { "content-type": "text/plain; charset=utf-8" });
                res.end(failures.length ? "Disallowed CORS " + failures.join(", ") : "OK");
                return;
            }
            const url = new URL(req.url ?? "/", "http://localhost");
            const found = routes.find(route => route.method === req.method && route.pattern.test(url.pathname));
            if (!found)
                throw new HttpError(routes.some(route => route.pattern.test(url.pathname)) ? 405 : 404, routes.some(route => route.pattern.test(url.pathname)) ? "Method Not Allowed" : "Not Found");
            const match = found.pattern.exec(url.pathname);
            await found.run({ req, res, url, params: match?.slice(1).map(decodeURIComponent) ?? [] });
        })().catch(error => {
            if (res.headersSent) {
                res.end();
                return;
            }
            if (error instanceof HttpError) {
                for (const [name, value] of Object.entries(error.headers))
                    res.setHeader(name, value);
                json(res, { detail: error.detail }, error.status);
            }
            else {
                res.writeHead(500, { "content-type": "text/plain; charset=utf-8" });
                res.end("Internal Server Error");
            }
        });
    });
}
function positive(value: string | undefined, fallback: number) { const n = Number(value); return Number.isFinite(n) && n > 0 ? n : fallback; }
function exportTable(table: Record<string, unknown>) {
    const lines = [`Source table: ${table.tool ?? "?"}`], meta = objectValue(table.meta) ?? {};
    const evidence = [meta.source ? `source ${meta.source}` : "", meta.season ? `season ${meta.season}` : "", meta.fetched_at ? `fetched ${String(meta.fetched_at).slice(0, 10)}` : ""].filter(Boolean);
    if (evidence.length)
        lines.push("Evidence: " + evidence.join(", "));
    const limits = [meta.qualification, meta.coverage, ...(Array.isArray(meta.warnings) ? meta.warnings.map(String) : [])];
    for (const limit of limits)
        if (typeof limit === "string" && limit.trim())
            lines.push("Limit: " + limit);
    return lines;
}

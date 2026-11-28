import { createHash } from "node:crypto";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { join, basename } from "node:path";
import { Type, type TSchema, type Static } from "typebox";
import { Value } from "typebox/value";
import { validationDetails, validationDetail } from "./http-validation.js";
import { createAnalyst, analystRequestSchema, backendRoot, newRunId, encodeEvent, runTimeoutMs } from "./analyst.js";
import { ProjectStore, WorkspaceStore } from "./catalog-stores.js";
import { ObjectStore, validateObjectPayload, capScenarioMoveSchema, signingExceptionStateSchema, type ObjectKind } from "./object-store.js";
import { providerPolicy } from "./providers.js";
import { objectValue, sourceResult } from "./python-tools.js";
import type { DirectData } from "./direct-data.js";
export class HttpError extends Error {
    constructor(readonly status: number, readonly detail: unknown, readonly headers: Record<string, string> = {}) { super(typeof detail === "string" ? detail : "Request failed"); }
}
const text = (max = 2000) => Type.String({ minLength: 1, maxLength: max, pattern: "\\S" });
const workspaceCreate = Type.Object({ name: Type.String({ minLength: 1, maxLength: 256 }), owner: Type.String({ minLength: 1, maxLength: 256 }) }, { additionalProperties: false });
const members = Type.Optional(Type.Union([Type.Array(Type.String(), { maxItems: 1024 }), Type.Null()]));
const workspaceUpdate = Type.Object({ name: Type.Optional(Type.Union([Type.String({ minLength: 1, maxLength: 256 }), Type.Null()])), add_thread_ids: members, remove_thread_ids: members, add_brief_ids: members, remove_brief_ids: members }, { additionalProperties: false });
const branchCreate = Type.Object({ thread: text(80), client: text(80), parent_sequence: Type.Integer({ minimum: 1 }), branch_id: Type.Optional(Type.Union([text(64), Type.Null()])) }, { additionalProperties: false });
const tradeLegsSchema = Type.Object({ legs: Type.Array(Type.Object({ from: Type.String({ minLength: 2, maxLength: 4 }), to: Type.String({ minLength: 2, maxLength: 4 }), players: Type.Optional(Type.Union([Type.String(), Type.Array(Type.String())])), picks: Type.Optional(Type.Array(Type.Record(Type.String(), Type.Unknown()), { maxItems: 12 })) }, { additionalProperties: true }), { minItems: 1, maxItems: 8 }), season: Type.Optional(Type.String()), tpes: Type.Optional(Type.Array(Type.Object({ team: Type.String({ minLength: 2, maxLength: 4 }), amount: Type.Integer({ minimum: 1 }), kind: Type.Optional(Type.String({ maxLength: 24 })), origin_year: Type.Optional(Type.Integer()), exactness: Type.Optional(Type.String({ maxLength: 32 })) }, { additionalProperties: false }), { maxItems: 30 })) }, { additionalProperties: false });
const tradeSchema = Type.Object({ team_a: Type.Optional(Type.String()), team_b: Type.Optional(Type.String()), players_a: Type.Optional(Type.Union([Type.String(), Type.Array(Type.String())])), players_b: Type.Optional(Type.Union([Type.String(), Type.Array(Type.String())])), season: Type.Optional(Type.String()) }, { additionalProperties: false });
const capScenarioSchema = Type.Object({ team: Type.Optional(Type.String()), season: Type.Optional(Type.String()), waiver_date: Type.Optional(Type.String()), exception_state: Type.Optional(signingExceptionStateSchema), moves: Type.Array(capScenarioMoveSchema, { minItems: 1, maxItems: 40 }) }, { additionalProperties: false });
const capProjectionMoveSchema = Type.Object({ kind: Type.String(), label: Type.Optional(Type.String()), amount: Type.Optional(Type.Number()), player: Type.Optional(Type.String()), exercise: Type.Optional(Type.Boolean()), stretch: Type.Optional(Type.Boolean()), season: Type.Optional(Type.String()), exception: Type.Optional(Type.String()), years: Type.Optional(Type.Integer({ minimum: 1, maximum: 5 })), first_year_amount: Type.Optional(Type.Number()), group: Type.Optional(Type.String({ maxLength: 48 })) }, { additionalProperties: false });
const capProjectionSchema = Type.Object({ team: Type.Optional(Type.String()), season: Type.Optional(Type.String()), waiver_date: Type.Optional(Type.String()), horizon: Type.Optional(Type.Integer({ minimum: 1, maximum: 3 })), moves: Type.Array(capProjectionMoveSchema, { minItems: 0, maxItems: 40 }), tpes: Type.Optional(Type.Array(Type.Object({ team: Type.String({ minLength: 2, maxLength: 4 }), amount: Type.Integer({ minimum: 1 }), kind: Type.Optional(Type.String({ maxLength: 24 })), origin_year: Type.Optional(Type.Integer()), exactness: Type.Optional(Type.String({ maxLength: 32 })) }, { additionalProperties: false }), { maxItems: 30 })) }, { additionalProperties: false });
const partnersSchema = Type.Object({ player: Type.Optional(Type.String()), season: Type.Optional(Type.String()), teams: Type.Optional(Type.Union([Type.String(), Type.Array(Type.String())])), max_packages: Type.Optional(Type.Integer({ minimum: 1, maximum: 10 })) }, { additionalProperties: false });
const watchSchema = Type.Object({ entity_type: Type.String(), entity_id: Type.String(), season: Type.Optional(Type.String()) });
const boardSeason = Type.Optional(Type.String({ pattern: "^\\d{4}-\\d{2}$" }));
const boardMetric = Type.String({ minLength: 1, maxLength: 80 });
const boardFill = Type.Object({ season: boardSeason, player_ids: Type.Array(Type.Integer({ minimum: 1, maximum: Number.MAX_SAFE_INTEGER }), { maxItems: 50 }), metric_ids: Type.Array(boardMetric, { maxItems: 30 }) }, { additionalProperties: false });
const boardSeed = Type.Object({ season: boardSeason, metric_id: boardMetric, n: Type.Optional(Type.Integer({ minimum: 1, maximum: 25 })), min_gp: Type.Optional(Type.Union([Type.Integer({ minimum: 0 }), Type.Null()])), min_mpg: Type.Optional(Type.Union([Type.Number({ minimum: 0 }), Type.Null()])) }, { additionalProperties: false });
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
    const objects = new ObjectStore(env.DIME_OBJECT_STORE ?? join(backendRoot, "data/v2-objects.sqlite3"));
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
    route("GET", /^\/api\/boards\/metrics$/, async ({ res }) => json(res, await data.call("product_board_metrics", {})));
    route("POST", /^\/api\/boards\/(fill|seed)$/, async ({ req, res, params }) => {
        const operation = params[0] === "fill" ? "product_board_fill" : "product_board_seed";
        const payload = parseBody(params[0] === "fill" ? boardFill : boardSeed, await body(req));
        const result = await data.call(operation, { payload });
        if (result.ok === false) throw new HttpError(result.status === 422 ? 422 : 503, result.error ?? "Boards warehouse unavailable");
        json(res, result);
    });
    route("GET", /^\/api\/healthz$/, async ({ res }) => { const result = await data.call("product_warehouse_health", {}); json(res, result, result.ok ? 200 : 503); });
    route("GET", /^\/api\/datasets\/freshness$/, async ({ res }) => json(res, await data.call("product_freshness", {})));
    route("GET", /^\/api\/home$/, async ({ res }) => json(res, await data.call("product_home", {})));
    route("GET", /^\/api\/warehouse\/tables\/([^/]+)$/, async ({ res, url, params }) => {
        if (!/^silver_[a-z0-9_]+$/.test(params[0])) { json(res, { ok: false, error: "Table not found" }, 404); return; }
        const result = await data.call("product_table_detail", { table: params[0], season: url.searchParams.get("season") ?? "" });
        json(res, result, result.ok ? 200 : 404);
    });
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
    const objectCreate = Type.Object({ kind: Type.String({ minLength: 1, maxLength: 40 }), title: Type.String({ minLength: 1, maxLength: 256 }), payload: Type.Unknown() }, { additionalProperties: false });
    const objectPatch = Type.Object({ title: Type.Optional(Type.String({ minLength: 1, maxLength: 256 })), payload: Type.Optional(Type.Unknown()), archived: Type.Optional(Type.Boolean()) }, { additionalProperties: false });
    const objectIdShape = /^obj-[a-f0-9]{32}$/;
    const readTokenShape = /^[A-Za-z0-9_-]{32,64}$/;
    const objectOwner = (req: IncomingMessage) => {
        const owner = req.headers["x-dime-owner"];
        if (typeof owner !== "string" || !owner.trim())
            throw new HttpError(401, "owner identity required");
        return owner.trim().slice(0, 80);
    };
    const ownerToken = (req: IncomingMessage) => {
        const token = req.headers["x-owner-token"];
        if (typeof token !== "string" || !token)
            throw new HttpError(401, "owner token required");
        return token;
    };
    const objectRate = new RateWindow();
    const objectWriteRate = (req: IncomingMessage) => {
        const wait = objectRate.take(req.socket.remoteAddress ?? "unknown", positive(env.DIME_OBJECT_WRITE_RATE_LIMIT, 60), 60);
        if (wait)
            throw new HttpError(429, "Too Many Requests", { "Retry-After": String(wait) });
    };
    const publicObject = (value: { kind: string; title: string; payload: unknown; schema_version: number; updated_at: string; archived: boolean }) => ({ kind: value.kind, title: value.title, payload: value.payload, schema_version: value.schema_version, updated_at: value.updated_at, archived: value.archived });
    const ownedObject = (value: { object_id: string; kind: string; title: string; payload: unknown; schema_version: number; created_at: string; updated_at: string; archived: boolean; read_token: string }) => ({ object_id: value.object_id, kind: value.kind, title: value.title, payload: value.payload, schema_version: value.schema_version, created_at: value.created_at, updated_at: value.updated_at, archived: value.archived, read_token: value.read_token });
    const authorizedObject = (req: IncomingMessage, id: string) => {
        if (!objectIdShape.test(id))
            throw new HttpError(422, [validationDetail("object_id_format", ["params", "object_id"], "Invalid object id", id)]);
        const token = ownerToken(req);
        const value = objects.get(id);
        if (!value)
            throw new HttpError(404, "object not found");
        if (!objects.verify(value, token))
            throw new HttpError(403, "owner token rejected");
        return value;
    };
    const stampThreadGrant = async (owner: string, payload: unknown) => {
        const shape = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
        const thread = typeof shape.thread === "string" ? shape.thread.trim().slice(0, 120) : "";
        if (!thread)
            throw new HttpError(422, [validationDetail("payload_invalid", ["body", "payload"], "thread grant payload requires a thread id", null)]);
        const runs = await data.call("product_runs", { thread, owner });
        if (!Array.isArray(runs.runs) || runs.runs.length === 0)
            throw new HttpError(422, [validationDetail("thread_not_owned", ["body", "payload", "thread"], "thread has no runs for this owner", null)]);
        return { thread, owner, granted_before: new Date().toISOString() };
    };
    const stampArtifactRef = (owner: string, payload: unknown) => {
        const shape = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
        const runId = typeof shape.run_id === "string" ? shape.run_id.trim().slice(0, 60) : "";
        const thread = typeof shape.thread === "string" ? shape.thread.trim().slice(0, 120) : "";
        const index = typeof shape.artifact_index === "number" && Number.isInteger(shape.artifact_index) ? shape.artifact_index : -1;
        if (!runId || !thread || index < 0)
            throw new HttpError(422, [validationDetail("payload_invalid", ["body", "payload"], "artifact ref payload requires run_id, thread and artifact_index", null)]);
        let resolved;
        try {
            resolved = analyst.store.readSources({ owner, thread }, runId);
        }
        catch {
            throw new HttpError(422, [validationDetail("run_not_owned", ["body", "payload", "run_id"], "run not found for this owner and thread", null)]);
        }
        const artifacts = resolved.submission && Array.isArray((resolved.submission as Record<string, unknown>).artifacts) ? (resolved.submission as Record<string, unknown>).artifacts as unknown[] : [];
        if (index >= artifacts.length)
            throw new HttpError(422, [validationDetail("artifact_index_out_of_range", ["body", "payload", "artifact_index"], "artifact index out of range for the run submission", null)]);
        return { run_id: runId, artifact_index: index, thread, owner };
    };
    const validateBoardPins = (store: ObjectStore, owner: string, payload: unknown): string | null => {
        const shape = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
        if (!Array.isArray(shape.pins))
            return null;
        for (const pin of shape.pins) {
            const p = pin && typeof pin === "object" ? pin as Record<string, unknown> : {};
            const target = typeof p.object_id === "string" ? store.get(p.object_id) : undefined;
            if (!target)
                return `pin target does not exist`;
            if (target.owner !== owner)
                return `pin target is owned by someone else — cross-owner pinning is not supported`;
            if (target.kind !== p.kind)
                return `pin kind does not match the referenced object`;
        }
        return null;
    };

    route("POST", /^\/api\/objects$/, async ({ req, res }) => {
        objectWriteRate(req);
        const owner = objectOwner(req);
        const input = parseBody(objectCreate, await body(req));
        const payload = input.kind === "thread_grant" ? await stampThreadGrant(owner, input.payload) : input.kind === "artifact_ref" ? stampArtifactRef(owner, input.payload) : input.payload;
        const invalid = validateObjectPayload(input.kind, payload);
        if (invalid)
            throw new HttpError(422, [validationDetail("payload_invalid", ["body", "payload"], invalid, null)]);
        const pinInvalid = input.kind === "board" ? validateBoardPins(objects, owner, payload) : null;
        if (pinInvalid)
            throw new HttpError(422, [validationDetail("payload_invalid", ["body", "payload"], pinInvalid, null)]);
        const created = objects.create({ kind: input.kind as ObjectKind, owner, title: input.title, payload });
        const value = objects.get(created.object_id);
        if (!value)
            throw new Error("object create lost");
        if (value.kind === "artifact_ref") {
            const resolvedRef = resolveArtifactRef(value.payload);
            if (!resolvedRef.unavailable && resolvedRef.artifact) {
                try {
                    objects.writeArtifactSnapshot(value.object_id, { artifact: resolvedRef.artifact, evidence: resolvedRef.evidence, captured_at: value.created_at });
                }
                catch (error) {
                    console.warn("artifact snapshot write failed; link falls back to live resolution", error);
                }
            }
        }
        json(res, { ...ownedObject(value), owner_token: created.owner_token }, 201);
    });
    route("GET", /^\/api\/objects$/, async ({ req, res, url }) => {
        const owner = objectOwner(req);
        const kind = url.searchParams.get("kind") ?? undefined;
        json(res, { objects: objects.list(owner, kind) });
    });
    route("GET", /^\/api\/objects\/([^/]+)$/, async ({ req, res, params }) => {
        json(res, ownedObject(authorizedObject(req, params[0])));
    });
    route("PATCH", /^\/api\/objects\/([^/]+)$/, async ({ req, res, params }) => {
        objectWriteRate(req);
        const value = authorizedObject(req, params[0]);
        const input = parseBody(objectPatch, await body(req));
        if (input.payload !== undefined) {
            if (value.kind === "thread_grant" || value.kind === "artifact_ref")
                throw new HttpError(422, [validationDetail("payload_immutable", ["body", "payload"], "grant and artifact ref payloads are immutable — archive and re-create instead", null)]);
            const invalid = validateObjectPayload(value.kind, input.payload);
            if (invalid)
                throw new HttpError(422, [validationDetail("payload_invalid", ["body", "payload"], invalid, null)]);
            const pinInvalid = value.kind === "board" ? validateBoardPins(objects, value.owner, input.payload) : null;
            if (pinInvalid)
                throw new HttpError(422, [validationDetail("payload_invalid", ["body", "payload"], pinInvalid, null)]);
        }
        objects.update(value, input);
        const updated = objects.get(value.object_id);
        if (!updated)
            throw new Error("object update lost");
        json(res, ownedObject(updated));
    });
    route("POST", /^\/api\/objects\/([^/]+)\/rotate-share$/, async ({ req, res, params }) => {
        objectWriteRate(req);
        const value = authorizedObject(req, params[0]);
        json(res, { object_id: value.object_id, read_token: objects.rotateShare(value) });
    });
    const resolveThreadTranscript = async (payload: unknown) => {
        const shape = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
        const thread = typeof shape.thread === "string" ? shape.thread : "";
        const owner = typeof shape.owner === "string" ? shape.owner : "";
        const grantedBefore = typeof shape.granted_before === "string" ? shape.granted_before : "";
        if (!thread || !owner || !grantedBefore)
            return [];
        const result = await data.call("product_runs", { thread, owner }).catch(() => null);
        const runs = result && Array.isArray(result.runs) ? result.runs : [];
        return runs
            .filter((run: unknown) => {
                const row = objectValue(run);
                return row && typeof row.created_at === "string" && row.created_at <= grantedBefore;
            })
            .slice(0, 50)
            .map((run: unknown) => {
                const row = objectValue(run);
                return {
                    question: typeof row?.question === "string" ? row.question : "",
                    answer: typeof row?.answer === "string" ? row.answer : "",
                    tables: Array.isArray(row?.tables) ? row.tables : [],
                    created_at: typeof row?.created_at === "string" ? row.created_at : ""
                };
            });
    };
    const resolveArtifactRef = (payload: unknown): { artifact: unknown; evidence: unknown[]; unavailable: boolean } => {
        const shape = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
        const runId = typeof shape.run_id === "string" ? shape.run_id : "";
        const thread = typeof shape.thread === "string" ? shape.thread : "";
        const owner = typeof shape.owner === "string" ? shape.owner : "";
        const index = typeof shape.artifact_index === "number" ? shape.artifact_index : -1;
        try {
            const resolved = analyst.store.readSources({ owner, thread }, runId);
            const artifacts = resolved.submission && Array.isArray((resolved.submission as Record<string, unknown>).artifacts) ? (resolved.submission as Record<string, unknown>).artifacts as unknown[] : [];
            const artifact = index >= 0 && index < artifacts.length ? artifacts[index] : null;
            if (!artifact)
                throw new Error("artifact missing");
            const selectors = artifact && typeof artifact === "object" && Array.isArray((artifact as Record<string, unknown>).sources) ? (artifact as Record<string, unknown>).sources as { ref?: string; rows?: number[]; columns?: string[] }[] : [];
            const records = new Map((resolved.sources ?? []).map(record => [record.ref, record]));
            const evidence = selectors.map(selector => {
                const record = selector.ref ? records.get(selector.ref) : undefined;
                if (!record)
                    return { ref: selector.ref ?? "", missing: true };
                const result = sourceResult(record);
                const data = objectValue(result.structuredContent.result) ?? {};
                const rows = Array.isArray(data.rows) ? data.rows as Record<string, unknown>[] : [];
                const picked = Array.isArray(selector.rows) ? selector.rows.map(i => rows[i]).filter((row): row is Record<string, unknown> => !!row) : rows;
                const meta = objectValue(data.meta);
                return {
                    ref: record.ref,
                    tool: record.tool,
                    ...(meta ? { meta } : {}),
                    rows: picked.slice(0, 200)
                };
            });
            return { artifact, evidence, unavailable: false };
        }
        catch {
            return { artifact: null, evidence: [], unavailable: true };
        }
    };

    route("GET", /^\/s\/([^/]+)$/, async ({ res, params }) => {
        if (!readTokenShape.test(params[0]))
            throw new HttpError(422, [validationDetail("read_token_format", ["params", "read_token"], "Invalid share token", params[0])]);
        const value = objects.getByReadToken(params[0]);
        if (!value)
            throw new HttpError(404, "not found");
        const shared = publicObject(value);
        if (value.kind === "board" && !value.archived) {
            const shape = value.payload && typeof value.payload === "object" ? value.payload as Record<string, unknown> : {};
            const pins = Array.isArray(shape.pins) ? shape.pins as { kind?: string; object_id?: string; note?: string }[] : [];
            const resolvedPins = pins.map(pin => {
                const target = typeof pin.object_id === "string" ? objects.get(pin.object_id) : undefined;
                if (!target)
                    return { kind: pin.kind, object_id: pin.object_id, ...(pin.note ? { note: pin.note } : {}), status: "missing" };
                if (target.archived)
                    return { kind: pin.kind, object_id: pin.object_id, ...(pin.note ? { note: pin.note } : {}), status: "archived" };
                const base = { kind: pin.kind, object_id: pin.object_id, ...(pin.note ? { note: pin.note } : {}), status: "ok", title: target.title, payload: target.payload };
                if (pin.kind === "artifact_ref") {
                    const snapshot = objects.readArtifactSnapshot(target.object_id);
                    if (snapshot)
                        return { ...base, artifact: snapshot.artifact, artifact_unavailable: false };
                    const resolvedRef = resolveArtifactRef(target.payload);
                    return { ...base, artifact: resolvedRef.artifact, artifact_unavailable: resolvedRef.unavailable };
                }
                return base;
            });
            json(res, { ...shared, pins: resolvedPins });
            return;
        }
        if (value.kind === "thread_grant" && !value.archived) {
            const transcript = await resolveThreadTranscript(value.payload);
            json(res, { ...shared, payload: { thread: true }, transcript });
            return;
        }
        if (value.kind === "artifact_ref" && !value.archived) {
            const shape = value.payload && typeof value.payload === "object" ? value.payload as Record<string, unknown> : {};
            const index = typeof shape.artifact_index === "number" ? shape.artifact_index : -1;
            const snapshot = objects.readArtifactSnapshot(value.object_id);
            if (snapshot) {
                json(res, {
                    ...shared,
                    payload: { artifact_index: index },
                    artifact: snapshot.artifact,
                    evidence: snapshot.evidence,
                    captured_at: snapshot.captured_at || value.created_at
                });
                return;
            }
            const resolvedRef = resolveArtifactRef(value.payload);
            if (resolvedRef.unavailable) {
                json(res, { ...shared, payload: { artifact_index: index }, artifact: null, evidence: [], unavailable: true });
                return;
            }
            json(res, {
                ...shared,
                payload: { artifact_index: index },
                artifact: resolvedRef.artifact,
                evidence: resolvedRef.evidence,
                captured_at: typeof shape.granted_before === "string" ? shape.granted_before : value.created_at
            });
            return;
        }
        json(res, shared);
    });
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
    route("POST", /^\/api\/trade\/check$/, async ({ req, res }) => { const input = parseBody(tradeSchema, await body(req)); const players = (value: string | string[] | undefined) => Array.isArray(value) ? value.map(s => s.trim()).filter(Boolean).join(", ") : value ?? ""; const result = await data.call("product_trade", { team_a: input.team_a ?? "", team_b: input.team_b ?? "", players_a: players(input.players_a), players_b: players(input.players_b), season: input.season ?? "2026-27" }); json(res, result, result.ok === false ? 422 : 200); });
    route("GET", /^\/api\/cap\/sheet$/, async ({ res, url }) => {
        const result = await data.call("product_cap_sheet", { team: (url.searchParams.get("team") ?? "").slice(0, 12), season: url.searchParams.get("season") ?? "2026-27" });
        json(res, result, result.ok === false ? 422 : 200);
    });
    route("POST", /^\/api\/cap\/projection$/, async ({ req, res }) => {
        const input = parseBody(capProjectionSchema, await body(req));
        const result = await data.call("product_cap_projection", { payload: { team: input.team ?? "", season: input.season ?? "2026-27", moves: input.moves ?? [], horizon: input.horizon, tpes: input.tpes } });
        json(res, result, result.ok === false ? 422 : 200);
    });
    route("POST", /^\/api\/cap\/scenario$/, async ({ req, res }) => {
        const input = parseBody(capScenarioSchema, await body(req));
        const result = await data.call("product_cap_scenario_eval", { payload: { team: input.team ?? "", season: input.season ?? "2026-27", waiver_date: input.waiver_date ?? "", exception_state: input.exception_state, moves: input.moves } });
        json(res, result, result.ok === false ? 422 : 200);
    });
    route("GET", /^\/api\/trade\/assets$/, async ({ res, url }) => {
        const result = await data.call("product_trade_assets", { team: (url.searchParams.get("team") ?? "").slice(0, 12), season: url.searchParams.get("season") ?? "2026-27" });
        json(res, result, result.ok === false ? 422 : 200);
    });
    route("POST", /^\/api\/trade\/partners$/, async ({ req, res }) => {
        const input = parseBody(partnersSchema, await body(req));
        const teams = (value: string | string[] | undefined) => Array.isArray(value) ? value.map(s => s.trim()).filter(Boolean).join(", ") : value ?? "";
        const result = await data.call("product_trade_partners", { player: input.player ?? "", season: input.season ?? "2026-27", teams: teams(input.teams), max_packages: input.max_packages ?? 3 });
        json(res, result, result.ok === false ? 422 : 200);
    });
    route("POST", /^\/api\/trade\/legs$/, async ({ req, res }) => { const input = parseBody(tradeLegsSchema, await body(req)); const result = await data.call("product_trade_legs", { legs: JSON.stringify(input.legs), season: input.season ?? "2026-27", tpes: input.tpes ? JSON.stringify(input.tpes) : "" }); json(res, result, result.ok === false ? 422 : 200); });
    route("GET", /^\/api\/history\/career$/, async ({ res, url }) => { const result = await data.call("product_history_career", { player: (url.searchParams.get("player") ?? "").slice(0, 80) }); json(res, result, result.ok === false ? 422 : 200); });
    route("GET", /^\/api\/history\/era-comps$/, async ({ res, url }) => { const result = await data.call("product_history_era_comps", { player_id: Number(url.searchParams.get("player_id") ?? 0), season: url.searchParams.get("season") ?? "", k: Number(url.searchParams.get("k") ?? 8), player: url.searchParams.get("player") ?? "", start_season: url.searchParams.get("start") ?? "", end_season: url.searchParams.get("end") ?? "" }); json(res, result, result.ok === false ? 422 : 200); });
    route("GET", /^\/api\/history\/leaders$/, async ({ res, url }) => { const result = await data.call("product_history_leaders", { season: url.searchParams.get("season") ?? "", category: url.searchParams.get("category") ?? "pts" }); json(res, result, result.ok === false ? 422 : 200); });
    route("GET", /^\/api\/morning$/, async ({ res, url }) => {
        const result = await data.call("product_morning", { team: (url.searchParams.get("team") ?? "").slice(0, 12), season: url.searchParams.get("season") ?? "" });
        json(res, result, result.ok === false ? 422 : 200);
    });
    route("GET", /^\/api\/draft$/, async ({ res, url }) => {
        const result = await data.call("product_draft", { team: (url.searchParams.get("team") ?? "").slice(0, 12), season: url.searchParams.get("season") ?? "" });
        json(res, result, result.ok === false ? 422 : 200);
    });
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
    route("GET", /^\/api\/matchups$/, async ({ res, url }) => json(res, await data.call("product_matchups", { season: url.searchParams.get("season") ?? "" })));
    route("GET", /^\/api\/awards$/, async ({ res, url }) => json(res, await data.call("product_awards", { season: url.searchParams.get("season") ?? "" })));
    route("GET", /^\/api\/scout-dossier$/, async ({ res, url }) => { const result = await data.call("product_scout_dossier", { team: (url.searchParams.get("team") ?? "").slice(0, 24), opponent: (url.searchParams.get("opponent") ?? "").slice(0, 24), season: url.searchParams.get("season") ?? "" }); json(res, result, result.ok === false ? 422 : 200); });
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
    route("GET", /^\/api\/compare$/, async ({ res, url }) => {
        const result = await data.call("product_compare", { players: url.searchParams.get("players") ?? "", season: url.searchParams.get("season") ?? "2025-26" });
        json(res, result, result.ok === false ? 422 : 200);
    });
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
        const timeoutMs = runTimeoutMs(env);
        const timer = setTimeout(abort, timeoutMs);
        let heartbeat: ReturnType<typeof setTimeout> | undefined;
        const resetHeartbeat = () => { clearTimeout(heartbeat); heartbeat = setTimeout(() => { res.write(encodeEvent({ type: "ping", data: { ok: true } })); resetHeartbeat(); }, 15000); };
        resetHeartbeat();
        res.writeHead(200, { "content-type": "text/event-stream; charset=utf-8", "x-dime-run-id": run, "x-dime-run-timeout-ms": String(timeoutMs) });
        try {
            for await (const event of analyst.stream(input, controller.signal, run, { runTimeoutMs: timeoutMs })) {
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

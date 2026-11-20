import { randomUUID, randomBytes, createHash, timingSafeEqual } from "node:crypto";
import { openProductDatabase } from "./product-store.js";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
const workspaceSchema = Type.Object({ id: Type.String(), name: Type.String(), owner: Type.String(), member_thread_ids: Type.Array(Type.String()), member_brief_ids: Type.Array(Type.String()), owner_token_hash: Type.String(), created_at: Type.String(), updated_at: Type.String() }, { additionalProperties: false });
const projectSchema = Type.Object({ id: Type.String(), goal: Type.String(), status: Type.Union([Type.Literal("pending"), Type.Literal("running"), Type.Literal("complete"), Type.Literal("failed")]), run_id: Type.String(), created_at: Type.String(), updated_at: Type.String(), result: Type.Union([Type.String(), Type.Null()]), error: Type.Union([Type.String(), Type.Null()]) }, { additionalProperties: false });
type Workspace = Static<typeof workspaceSchema>;
export type WorkspaceUpdate = {
    name?: string | null;
    add_thread_ids?: string[] | null;
    remove_thread_ids?: string[] | null;
    add_brief_ids?: string[] | null;
    remove_brief_ids?: string[] | null;
};
const tokenHash = (id: string, token: string) => createHash("sha256").update(id + ":" + token).digest("hex");
export class WorkspaceStore {
    constructor(readonly path: string) { }
    private connect() { const db = openProductDatabase(this.path, false); db.exec("CREATE TABLE IF NOT EXISTS workspaces (id TEXT PRIMARY KEY, data TEXT NOT NULL)"); return db; }
    get(id: string) {
        const db = this.connect();
        try {
            const row = db.prepare("SELECT data FROM workspaces WHERE id=?").get(id);
            if (!row)
                return undefined;
            if (typeof row.data !== "string")
                throw new Error("Invalid workspace");
            const value: unknown = JSON.parse(row.data);
            if (!Value.Check(workspaceSchema, value))
                throw new Error("Invalid workspace");
            return value;
        }
        finally {
            db.close();
        }
    }
    create(name: string, owner: string) {
        if (!name.trim())
            throw new Error("workspace name must be non-empty");
        if (!owner.trim())
            throw new Error("workspace owner must be non-empty");
        const id = randomUUID().replaceAll("-", ""), token = randomBytes(32).toString("hex"), now = new Date().toISOString();
        const workspace: Workspace = { id, name: name.trim(), owner: owner.trim(), member_thread_ids: [], member_brief_ids: [], owner_token_hash: tokenHash(id, token), created_at: now, updated_at: now };
        const db = this.connect();
        try {
            db.prepare("INSERT INTO workspaces VALUES(?,?)").run(id, JSON.stringify(workspace));
        }
        finally {
            db.close();
        }
        return { workspace, token };
    }
    verify(workspace: Workspace, token: string) { const expected = Buffer.from(workspace.owner_token_hash); const actual = Buffer.from(tokenHash(workspace.id, token)); return expected.length === actual.length && timingSafeEqual(expected, actual); }
    update(workspace: Workspace, input: WorkspaceUpdate) {
        if (input.name !== undefined && input.name !== null && !input.name.trim())
            throw new Error("workspace name must be non-empty");
        const members = (existing: string[], add: string[] | null | undefined, remove: string[] | null | undefined) => {
            if ([...(add ?? []), ...(remove ?? [])].some(value => !value.trim()))
                throw new Error("workspace members must be non-empty strings");
            return [...new Set([...existing.filter(id => !remove?.includes(id)), ...(add ?? [])])];
        };
        const updated = { ...workspace, name: input.name?.trim() ?? workspace.name, member_thread_ids: members(workspace.member_thread_ids, input.add_thread_ids, input.remove_thread_ids), member_brief_ids: members(workspace.member_brief_ids, input.add_brief_ids, input.remove_brief_ids), updated_at: new Date(Math.max(Date.now(), Date.parse(workspace.updated_at))).toISOString() };
        const db = this.connect();
        try {
            db.prepare("UPDATE workspaces SET data=? WHERE id=?").run(JSON.stringify(updated), workspace.id);
        }
        finally {
            db.close();
        }
        return updated;
    }
    delete(id: string) {
        const db = this.connect();
        try {
            db.prepare("DELETE FROM workspaces WHERE id=?").run(id);
        }
        finally {
            db.close();
        }
    }
    public(workspace: Workspace) { const { owner_token_hash, ...publicValue } = workspace; return publicValue; }
}
export class ProjectStore {
    constructor(readonly path: string) { }
    private connect() { const db = openProductDatabase(this.path); db.exec("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL)"); return db; }
    list() {
        const db = this.connect();
        try {
            return db.prepare("SELECT data FROM projects").all().map(row => {
                if (typeof row.data !== "string")
                    throw new Error("Invalid project");
                const value: unknown = JSON.parse(row.data);
                if (!Value.Check(projectSchema, value))
                    throw new Error("Invalid project");
                return value;
            }).sort((a, b) => b.created_at.localeCompare(a.created_at));
        }
        finally {
            db.close();
        }
    }
    get(id: string) { return this.list().find(project => project.id === id); }
    create(goal: string) {
        if (!goal.trim())
            throw new Error("project goal must be non-empty");
        const id = randomUUID().replaceAll("-", ""), now = new Date().toISOString();
        const project = { id, goal, status: "pending", run_id: "project-" + id, created_at: now, updated_at: now, result: null, error: null };
        const db = this.connect();
        try {
            db.prepare("INSERT INTO projects VALUES(?,?)").run(id, JSON.stringify(project));
        }
        finally {
            db.close();
        }
        return project;
    }
}

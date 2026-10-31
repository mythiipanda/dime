import { DatabaseSync } from "node:sqlite";
import { mkdirSync, readFileSync, existsSync, writeFileSync, lstatSync } from "node:fs";
import { dirname, resolve, parse } from "node:path";
import { randomUUID } from "node:crypto";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import { sourceRecordSchema, type SourceRecord } from "./python-tools.js";
const turnSchema = Type.Object({ role: Type.Union([Type.Literal("user"), Type.Literal("assistant")]), content: Type.String({ minLength: 1, maxLength: 2000, pattern: "\\S" }) });
const referenceSchema = Type.Object({ sequence: Type.Integer(), turn: Type.String(), run_id: Type.Union([Type.String(), Type.Null()]), turn_id: Type.Union([Type.String(), Type.Null()]) });
const artifactSchema = Type.Object({ run_id: Type.String(), sources: Type.Array(sourceRecordSchema), source_refs: Type.Optional(Type.Array(Type.String())) });
export type Turn = Static<typeof turnSchema>;
export type Identity = {
    owner: string;
    thread: string;
};
function identity({ owner, thread }: Identity): Identity {
    if (!owner.trim() || !thread.trim())
        throw new Error("conversation identity must be non-empty");
    return { owner: owner.slice(0, 80), thread: thread.slice(0, 80) };
}
function rejectSymlinks(path: string) {
    for (let current = resolve(path);; current = dirname(current)) {
        if (lstatSync(current, { throwIfNoEntry: false })?.isSymbolicLink())
            throw new Error("product store cannot be a symlink");
        if (current === parse(current).root)
            break;
    }
    for (const suffix of ["-journal", "-wal", "-shm"]) {
        if (lstatSync(path + suffix, { throwIfNoEntry: false })?.isSymbolicLink())
            throw new Error("product store auxiliary file cannot be a symlink");
    }
}
export function openProductDatabase(path: string, wal = true) {
    rejectSymlinks(path);
    mkdirSync(dirname(path), { recursive: true });
    const db = new DatabaseSync(path);
    db.exec("PRAGMA busy_timeout=10000");
    if (wal)
        db.exec("PRAGMA journal_mode=WAL");
    return db;
}
export class ProductStore {
    constructor(readonly path: string, readonly sources: string) { }
    private connect() {
        const db = openProductDatabase(this.path);
        db.exec(`CREATE TABLE IF NOT EXISTS conversations (owner TEXT NOT NULL, thread TEXT NOT NULL, sequence INTEGER NOT NULL, turn TEXT NOT NULL, run_id TEXT, turn_id TEXT, PRIMARY KEY(owner,thread,sequence));
            CREATE TABLE IF NOT EXISTS branches (owner TEXT NOT NULL, thread TEXT NOT NULL, branch_id TEXT NOT NULL, parent_sequence INTEGER NOT NULL, parent_run_id TEXT, parent_turn_id TEXT, PRIMARY KEY(owner,thread,branch_id));
            CREATE TABLE IF NOT EXISTS branch_evidence (owner TEXT NOT NULL,thread TEXT NOT NULL,branch_id TEXT NOT NULL,evidence_id TEXT NOT NULL,envelope TEXT NOT NULL,rows_hash TEXT NOT NULL,PRIMARY KEY(owner,thread,branch_id,evidence_id));
            CREATE TABLE IF NOT EXISTS branch_reuses (owner TEXT NOT NULL,thread TEXT NOT NULL,branch_id TEXT NOT NULL,evidence_id TEXT NOT NULL,parent_run_id TEXT,parent_turn_id TEXT,PRIMARY KEY(owner,thread,branch_id,evidence_id));
            CREATE TABLE IF NOT EXISTS turn_evidence (owner TEXT NOT NULL,thread TEXT NOT NULL,sequence INTEGER NOT NULL,evidence_id TEXT NOT NULL,envelope TEXT NOT NULL,rows_hash TEXT NOT NULL,PRIMARY KEY(owner,thread,sequence,evidence_id));`);
        const columns = db.prepare("PRAGMA table_info(conversations)").all();
        for (const name of ["run_id", "turn_id"])
            if (!columns.some(row => row.name === name))
                db.exec(`ALTER TABLE conversations ADD COLUMN ${name} TEXT`);
        return db;
    }
    references(input: Identity) {
        const { owner, thread } = identity(input), db = this.connect();
        try {
            return db.prepare("SELECT sequence,turn,run_id,turn_id FROM conversations WHERE owner=? AND thread=? ORDER BY sequence").all(owner, thread).map(row => {
                if (!Value.Check(referenceSchema, row))
                    throw new Error("Invalid conversation reference");
                const turn: unknown = JSON.parse(row.turn);
                if (!Value.Check(turnSchema, turn))
                    throw new Error("Invalid conversation turn");
                return row;
            });
        }
        finally {
            db.close();
        }
    }
    read(input: Identity): Turn[] {
        return this.references(input).slice(-8).map(row => {
            const turn: unknown = JSON.parse(row.turn);
            if (!Value.Check(turnSchema, turn))
                throw new Error("Invalid conversation turn");
            return turn;
        });
    }
    branches(input: Identity) {
        const { owner, thread } = identity(input), db = this.connect();
        try {
            return db.prepare("SELECT branch_id,parent_sequence,parent_run_id,parent_turn_id FROM branches WHERE owner=? AND thread=? ORDER BY rowid").all(owner, thread).map(row => ({ branch_id: row.branch_id, parent_sequence: row.parent_sequence, parent_run_id: row.parent_run_id, parent_turn_id: row.parent_turn_id, owner, thread }));
        }
        finally {
            db.close();
        }
    }
    branchCounts(input: Identity, branch: string) {
        const db = this.connect(), { owner, thread } = identity(input);
        try {
            const count = (table: string) => {
                if (!db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name=?").get(table))
                    return 0;
                return db.prepare(`SELECT COUNT(*) AS n FROM ${table} WHERE owner=? AND thread=? AND branch_id=?`).get(owner, thread, branch)?.n ?? 0;
            };
            return { evidence_count: count("branch_evidence"), reused_count: count("branch_reuses") };
        }
        finally {
            db.close();
        }
    }
    createBranch(input: Identity, sequence: number, branchId?: string | null) {
        const { owner, thread } = identity(input), db = this.connect();
        const branch = branchId?.trim().slice(0, 64) ?? "br-" + randomUUID().replaceAll("-", "").slice(0, 12);
        try {
            const parent = db.prepare("SELECT run_id,turn_id FROM conversations WHERE owner=? AND thread=? AND sequence=?").get(owner, thread, sequence);
            if (!parent)
                throw new Error(`branch parent sequence ${sequence} is missing for thread '${thread}'`);
            if (db.prepare("SELECT 1 FROM branches WHERE owner=? AND thread=? AND branch_id=?").get(owner, thread, branch))
                throw new Error(`duplicate branch id: ${branch}`);
            db.prepare("INSERT INTO branches VALUES(?,?,?,?,?,?)").run(owner, thread, branch, sequence, parent.run_id, parent.turn_id);
            return { branch_id: branch, owner, thread, parent_sequence: sequence, parent_run_id: parent.run_id, parent_turn_id: parent.turn_id };
        }
        finally {
            db.close();
        }
    }
    append(input: Identity, question: string, answer: string, run: string) {
        const { owner, thread } = identity(input), db = this.connect();
        try {
            db.exec("BEGIN IMMEDIATE");
            const last = db.prepare("SELECT sequence,run_id,turn_id FROM conversations WHERE owner=? AND thread=? ORDER BY sequence DESC LIMIT 1").get(owner, thread);
            const sequence = last?.sequence ?? 0;
            if (typeof sequence !== "number")
                throw new Error("Invalid sequence");
            const insert = db.prepare("INSERT INTO conversations(owner,thread,sequence,turn,run_id,turn_id) VALUES(?,?,?,?,?,?)");
            insert.run(owner, thread, sequence + 1, JSON.stringify({ role: "user", content: question.slice(0, 2000) }), run, run);
            insert.run(owner, thread, sequence + 2, JSON.stringify({ role: "assistant", content: answer.slice(0, 2000) }), run, run);
            if (last)
                db.prepare("INSERT INTO branches VALUES(?,?,?,?,?,?)").run(owner, thread, "br-" + randomUUID().replaceAll("-", "").slice(0, 12), sequence, last.run_id, last.turn_id);
            db.exec("COMMIT");
        }
        catch (error) {
            db.exec("ROLLBACK");
            throw error;
        }
        finally {
            db.close();
        }
    }
    private artifacts(input: Identity) {
        const artifacts = new Map<string, Static<typeof artifactSchema>>();
        for (const { run_id: run } of this.references(input)) {
            if (!run || !/^run-[a-f0-9]{32}$/.test(run) || artifacts.has(run))
                continue;
            const path = resolve(this.sources, run + ".json");
            if (!existsSync(path))
                continue;
            const data: unknown = JSON.parse(readFileSync(path, "utf8"));
            if (!Value.Check(artifactSchema, data) || data.run_id !== run)
                throw new Error("Source artifact identity mismatch");
            artifacts.set(run, data);
        }
        return artifacts;
    }
    priorSources(input: Identity) {
        return [...new Map([...this.artifacts(input).values()].flatMap(a => a.sources.map(record => [record.ref, record] satisfies [
                string,
                SourceRecord
            ]))).values()];
    }
    readSources(input: Identity, run: string) {
        const artifacts = this.artifacts(input), artifact = artifacts.get(run);
        if (!artifact)
            throw new Error("Source not found");
        const records = new Map([...artifacts.values()].flatMap(a => a.sources.map(r => [r.ref, r] satisfies [
            string,
            SourceRecord
        ])));
        return { run_id: run, sources: (artifact.source_refs ?? artifact.sources.map(r => r.ref)).map(ref => {
                const record = records.get(ref);
                if (!record)
                    throw new Error("Source not found");
                return record;
            }) };
    }
    saveSources(run: string, sources: SourceRecord[], records: SourceRecord[]) {
        mkdirSync(this.sources, { recursive: true });
        writeFileSync(resolve(this.sources, run + ".json"), JSON.stringify({ run_id: run, sources, source_refs: records.map(r => r.ref) }), { flag: "wx" });
    }
}

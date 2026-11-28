import { randomBytes, randomUUID, createHash, timingSafeEqual } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import { openProductDatabase } from "./product-store.js";
import { OBJECT_KINDS, artifactRefPayloadSchema, boardPayloadSchema, capScenarioPayloadSchema, threadGrantPayloadSchema, tradeScenarioPayloadSchema, type ObjectKind } from "./object-payloads.js";
export { OBJECT_KINDS, artifactRefPayloadSchema, boardPayloadSchema, boardPinSchema, capScenarioMoveSchema, capScenarioPayloadSchema, signingExceptionStateSchema, threadGrantPayloadSchema, tradeScenarioPayloadSchema, type ObjectKind } from "./object-payloads.js";


const payloadValidators: Record<ObjectKind, typeof capScenarioPayloadSchema | typeof tradeScenarioPayloadSchema | typeof threadGrantPayloadSchema | typeof artifactRefPayloadSchema | typeof boardPayloadSchema> = {
    cap_scenario: capScenarioPayloadSchema,
    trade_scenario: tradeScenarioPayloadSchema,
    thread_grant: threadGrantPayloadSchema,
    board: boardPayloadSchema,
    artifact_ref: artifactRefPayloadSchema
};

export function validateObjectPayload(kind: string, payload: unknown): string | null {
    if (!OBJECT_KINDS.includes(kind as ObjectKind))
        return "unknown object kind";
    const schema = payloadValidators[kind as ObjectKind];
    if (!Value.Check(schema, payload))
        return "invalid payload for kind";
    if (JSON.stringify(payload).length > 32768)
        return "payload too large";
    return null;
}

const rowSchema = Type.Object({
    object_id: Type.String(),
    kind: Type.String(),
    owner: Type.String(),
    owner_token_hash: Type.String(),
    read_token: Type.String(),
    title: Type.String(),
    payload: Type.String(),
    schema_version: Type.Integer(),
    created_at: Type.String(),
    updated_at: Type.String(),
    archived: Type.Integer()
});

type Row = Static<typeof rowSchema>;

export type StoredObject = Omit<Row, "payload" | "archived"> & { payload: unknown; archived: boolean };

const tokenHash = (objectId: string, token: string) => createHash("sha256").update(objectId + ":" + token).digest("hex");
const readToken = () => randomBytes(24).toString("base64url");

function materialize(row: Row): StoredObject {
    return { ...row, payload: JSON.parse(row.payload), archived: row.archived !== 0 };
}

export class ObjectStore {
    constructor(readonly path: string) { }
    private connect() {
        const db = openProductDatabase(this.path);
        db.exec(`CREATE TABLE IF NOT EXISTS objects (object_id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner TEXT NOT NULL, owner_token_hash TEXT NOT NULL, read_token TEXT NOT NULL UNIQUE, title TEXT NOT NULL, payload TEXT NOT NULL, schema_version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0)`);
        return db;
    }
    private row(db: ReturnType<ObjectStore["connect"]>, value: unknown): Row {
        if (!Value.Check(rowSchema, value))
            throw new Error("Invalid stored object");
        return value;
    }
    create(input: { kind: ObjectKind; owner: string; title: string; payload: unknown }) {
        const objectId = "obj-" + randomUUID().replaceAll("-", "");
        const ownerToken = randomBytes(32).toString("hex");
        const now = new Date().toISOString();
        const db = this.connect();
        try {
            db.prepare("INSERT INTO objects VALUES(?,?,?,?,?,?,?,?,?,?,0)").run(
                objectId, input.kind, input.owner.slice(0, 80), tokenHash(objectId, ownerToken), readToken(),
                input.title.trim().slice(0, 256), JSON.stringify(input.payload), 1, now, now);
        }
        finally {
            db.close();
        }
        return { object_id: objectId, owner_token: ownerToken };
    }
    get(objectId: string): StoredObject | undefined {
        const db = this.connect();
        try {
            const row = db.prepare("SELECT * FROM objects WHERE object_id=?").get(objectId);
            return row ? materialize(this.row(db, row)) : undefined;
        }
        finally {
            db.close();
        }
    }
    verify(object: StoredObject, token: string) {
        const expected = Buffer.from(object.owner_token_hash);
        const actual = Buffer.from(tokenHash(object.object_id, token));
        return expected.length === actual.length && timingSafeEqual(expected, actual);
    }
    list(owner: string, kind?: string): Omit<StoredObject, "payload" | "owner_token_hash" | "read_token">[] {
        const db = this.connect();
        try {
            const rows = kind
                ? db.prepare("SELECT * FROM objects WHERE owner=? AND kind=? ORDER BY updated_at DESC").all(owner.slice(0, 80), kind)
                : db.prepare("SELECT * FROM objects WHERE owner=? ORDER BY updated_at DESC").all(owner.slice(0, 80));
            return rows.map(row => {
                const value = materialize(this.row(db, row));
                const { payload: _payload, owner_token_hash: _hash, read_token: _read, ...metadata } = value;
                return metadata;
            });
        }
        finally {
            db.close();
        }
    }
    update(object: StoredObject, input: { title?: string; payload?: unknown; archived?: boolean }) {
        const updated = {
            title: input.title !== undefined ? input.title.trim().slice(0, 256) : object.title,
            payload: input.payload !== undefined ? JSON.stringify(input.payload) : JSON.stringify(object.payload),
            archived: input.archived !== undefined ? (input.archived ? 1 : 0) : (object.archived ? 1 : 0),
            updated_at: new Date(Math.max(Date.now(), Date.parse(object.updated_at) + 1)).toISOString()
        };
        const db = this.connect();
        try {
            db.prepare("UPDATE objects SET title=?, payload=?, archived=?, updated_at=? WHERE object_id=?").run(updated.title, updated.payload, updated.archived, updated.updated_at, object.object_id);
        }
        finally {
            db.close();
        }
        return updated;
    }
    rotateShare(object: StoredObject) {
        const token = readToken();
        const db = this.connect();
        try {
            db.prepare("UPDATE objects SET read_token=? WHERE object_id=?").run(token, object.object_id);
        }
        finally {
            db.close();
        }
        return token;
    }
    getByReadToken(token: string): StoredObject | undefined {
        const db = this.connect();
        try {
            const row = db.prepare("SELECT * FROM objects WHERE read_token=?").get(token);
            return row ? materialize(this.row(db, row)) : undefined;
        }
        finally {
            db.close();
        }
    }
    private snapshotDir() {
        return join(dirname(this.path), "artifact-snapshots");
    }
    writeArtifactSnapshot(objectId: string, snapshot: unknown) {
        if (!/^obj-[a-f0-9]{32}$/.test(objectId))
            throw new Error("invalid object id for artifact snapshot");
        const serialized = JSON.stringify(snapshot);
        if (serialized.length > 4 * 1024 * 1024)
            throw new Error("artifact snapshot too large");
        mkdirSync(this.snapshotDir(), { recursive: true });
        writeFileSync(join(this.snapshotDir(), objectId + ".json"), serialized, { flag: "wx" });
    }
    readArtifactSnapshot(objectId: string): { artifact: unknown; evidence: unknown[]; captured_at: string } | undefined {
        if (!/^obj-[a-f0-9]{32}$/.test(objectId))
            return undefined;
        const file = join(this.snapshotDir(), objectId + ".json");
        if (!existsSync(file))
            return undefined;
        try {
            const data = JSON.parse(readFileSync(file, "utf8")) as Record<string, unknown>;
            if (!data || typeof data !== "object" || !Array.isArray(data.evidence))
                return undefined;
            return { artifact: data.artifact ?? null, evidence: data.evidence, captured_at: typeof data.captured_at === "string" ? data.captured_at : "" };
        }
        catch {
            return undefined;
        }
    }
}

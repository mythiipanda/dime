import { Type } from "typebox";
import { Value } from "typebox/value";
import { objectValue, sourceResult, type SourceRecord } from "./python-tools.js";

const field = Type.String({ minLength: 1, maxLength: 160 });

export const playerCardSchema = Type.Object({
    kind: Type.Literal("player_card"),
    title: field,
    ref: field,
    row: Type.Integer({ minimum: 0 }),
    nameColumn: field,
    teamColumn: Type.Optional(field),
    metrics: Type.Array(Type.Object({ column: field, label: field }, { additionalProperties: false }), { minItems: 1, maxItems: 6 })
}, { additionalProperties: false });

export function resolvePlayerCard(artifact: Record<string, unknown>, getSource: (ref: string) => SourceRecord | undefined): Record<string, unknown> {
    if (!Value.Check(playerCardSchema, artifact))
        throw new Error("Invalid player_card: provide title, ref, row, nameColumn and 1-6 metrics with column/label selectors; do not provide values or units.");
    const source = getSource(artifact.ref);
    if (!source)
        throw new Error(`Unknown player_card source ref: ${artifact.ref}`);
    const result = sourceResult(source);
    const data = objectValue(result.structuredContent.result);
    const row = data && Array.isArray(data.rows) ? objectValue(data.rows[artifact.row]) : undefined;
    if (result.isError || !row)
        throw new Error("player_card requires a successful source with the selected row.");
    const playerName = row[artifact.nameColumn];
    const team = artifact.teamColumn ? row[artifact.teamColumn] : undefined;
    if (typeof playerName !== "string" || !playerName.trim() || (artifact.teamColumn && typeof team !== "string"))
        throw new Error("player_card nameColumn and teamColumn must select text fields.");
    const semantics = objectValue(data?.declared_column_semantics);
    const units = objectValue(data?.units);
    const metrics = artifact.metrics.map(metric => {
        const value = row[metric.column];
        if (!Object.hasOwn(row, metric.column) || (value !== null && (typeof value !== "number" || !Number.isFinite(value))))
            throw new Error(`player_card metric '${metric.column}' must select a finite number or null on the same row.`);
        const unit = objectValue(semantics?.[metric.column])?.unit ?? units?.[metric.column];
        return { ...metric, value, ...(typeof unit === "string" ? { unit } : {}) };
    });
    const meta = objectValue(data?.meta);
    return {
        kind: "player_card", title: artifact.title, playerName,
        ...(typeof team === "string" ? { team } : {}),
        sourceRef: artifact.ref, sourceRow: artifact.row,
        nameColumn: artifact.nameColumn, ...(artifact.teamColumn ? { teamColumn: artifact.teamColumn } : {}),
        metrics,
        provenance: {
            capability: source.tool, origin: "undeclared",
            ...(typeof meta?.season === "string" ? { season: meta.season } : {}),
            ...(typeof meta?.as_of === "string" ? { as_of: meta.as_of } : {}),
            ...(typeof meta?.sql === "string" ? { sql: meta.sql } : {})
        }
    };
}

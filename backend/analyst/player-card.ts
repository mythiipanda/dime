import { Type } from "typebox";
import { Value } from "typebox/value";
import { objectValue, sourceResult, type SourceRecord } from "./python-tools.js";

const field = Type.String({ minLength: 1, maxLength: 160 });

const selector = Type.Object({ column: field, label: field }, { additionalProperties: false });

const sectionSchema = Type.Object({
    label: field,
    ref: field,
    row: Type.Integer({ minimum: 0 }),
    metrics: Type.Optional(Type.Array(selector, { minItems: 1, maxItems: 6 })),
    fields: Type.Optional(Type.Array(selector, { minItems: 1, maxItems: 6 }))
}, { additionalProperties: false });

export const playerCardSchema = Type.Object({
    kind: Type.Literal("player_card"),
    title: field,
    ref: field,
    row: Type.Integer({ minimum: 0 }),
    nameColumn: field,
    teamColumn: Type.Optional(field),
    metrics: Type.Array(selector, { minItems: 1, maxItems: 6 }),
    sections: Type.Optional(Type.Array(sectionSchema, { minItems: 1, maxItems: 6 }))
}, { additionalProperties: false });

type SourceRow = { record: SourceRecord; row: Record<string, unknown>; data: Record<string, unknown> };

function resolveSourceRow(ref: string, rowIndex: number, getSource: (ref: string) => SourceRecord | undefined, kind: string): SourceRow {
    const record = getSource(ref);
    if (!record)
        throw new Error(`Unknown ${kind} source ref: ${ref}`);
    const result = sourceResult(record);
    const data = objectValue(result.structuredContent.result);
    const row = data && Array.isArray(data.rows) ? objectValue(data.rows[rowIndex]) : undefined;
    if (result.isError || !data || !row)
        throw new Error(`${kind} requires a successful source with the selected row.`);
    return { record, row, data };
}

function resolveMetrics(row: Record<string, unknown>, data: Record<string, unknown>, selectors: { column: string; label: string }[], kind: string) {
    const semantics = objectValue(data?.declared_column_semantics);
    const units = objectValue(data?.units);
    return selectors.map(metric => {
        const value = row[metric.column];
        if (!Object.hasOwn(row, metric.column) || (value !== null && (typeof value !== "number" || !Number.isFinite(value))))
            throw new Error(`${kind} metric '${metric.column}' must select a finite number or null on the same row.`);
        const unit = objectValue(semantics?.[metric.column])?.unit ?? units?.[metric.column];
        return { ...metric, value, ...(typeof unit === "string" ? { unit } : {}) };
    });
}

function resolveFields(row: Record<string, unknown>, selectors: { column: string; label: string }[], kind: string) {
    return selectors.map(item => {
        const value = row[item.column];
        if (!Object.hasOwn(row, item.column) || (value !== null && typeof value !== "string"))
            throw new Error(`${kind} field '${item.column}' must select a text value or null on the same row.`);
        return { ...item, value: value === null ? null : value };
    });
}

function resolveProvenance(record: SourceRecord, data: Record<string, unknown>) {
    const meta = objectValue(data?.meta);
    return {
        capability: record.tool, origin: "undeclared",
        ...(typeof meta?.source === "string" ? { dataset: meta.source } : {}),
        ...(typeof meta?.season === "string" ? { season: meta.season } : {}),
        ...(typeof meta?.as_of === "string" ? { as_of: meta.as_of } : {}),
        ...(typeof meta?.sql === "string" ? { sql: meta.sql } : {})
    };
}

export function resolvePlayerCard(artifact: Record<string, unknown>, getSource: (ref: string) => SourceRecord | undefined): Record<string, unknown> {
    if (!Value.Check(playerCardSchema, artifact))
        throw new Error("Invalid player_card: provide title, ref, row, nameColumn and 1-6 metrics with column/label selectors, plus optional sections of {label, ref, row, metrics, fields}; do not provide values or units.");
    const { record, row, data } = resolveSourceRow(artifact.ref, artifact.row, getSource, "player_card");
    const playerName = row[artifact.nameColumn];
    const team = artifact.teamColumn ? row[artifact.teamColumn] : undefined;
    if (typeof playerName !== "string" || !playerName.trim() || (artifact.teamColumn && typeof team !== "string"))
        throw new Error("player_card nameColumn and teamColumn must select text fields.");
    const metrics = resolveMetrics(row, data, artifact.metrics, "player_card");
    const sections = (artifact.sections ?? []).map(section => {
        if (!section.metrics && !section.fields)
            throw new Error(`player_card section '${section.label}' needs at least one metric or field.`);
        const resolved = resolveSourceRow(section.ref, section.row, getSource, "player_card section");
        return {
            label: section.label,
            sourceRef: section.ref, sourceRow: section.row,
            ...(section.metrics ? { metrics: resolveMetrics(resolved.row, resolved.data, section.metrics, "player_card section") } : {}),
            ...(section.fields ? { fields: resolveFields(resolved.row, section.fields, "player_card section") } : {}),
            provenance: resolveProvenance(resolved.record, resolved.data)
        };
    });
    return {
        kind: "player_card", title: artifact.title, playerName,
        ...(typeof team === "string" ? { team } : {}),
        sourceRef: artifact.ref, sourceRow: artifact.row,
        nameColumn: artifact.nameColumn, ...(artifact.teamColumn ? { teamColumn: artifact.teamColumn } : {}),
        metrics,
        ...(sections.length ? { sections } : {}),
        provenance: resolveProvenance(record, data)
    };
}

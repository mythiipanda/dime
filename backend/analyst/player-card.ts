import { Type } from "typebox";
import { Value } from "typebox/value";
import { objectValue, sourceResult, type SourceRecord } from "./python-tools.js";

export const field = Type.String({ minLength: 1, maxLength: 160 });

export const selector = Type.Object({ column: field, label: field }, { additionalProperties: false });

export const sectionSchema = Type.Object({
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

export function resolveSourceRow(ref: string, rowIndex: number, getSource: (ref: string) => SourceRecord | undefined, kind: string): SourceRow {
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

export function resolveMetrics(row: Record<string, unknown>, data: Record<string, unknown>, selectors: { column: string; label: string }[], kind: string) {
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

export function resolveFields(row: Record<string, unknown>, selectors: { column: string; label: string }[], kind: string) {
    return selectors.map(item => {
        const value = row[item.column];
        if (!Object.hasOwn(row, item.column) || (value !== null && typeof value !== "string"))
            throw new Error(`${kind} field '${item.column}' must select a text value or null on the same row.`);
        return { ...item, value: value === null ? null : value };
    });
}

function provenanceText(value: unknown) {
    return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function firstProvenanceText(...values: unknown[]) {
    for (const value of values) {
        const text = provenanceText(value);
        if (text)
            return text;
    }
    return undefined;
}

function liveProducerIds(value: string | undefined) {
    const normalized = value?.trim().toLowerCase().replace(/-/g, "_");
    if (!normalized)
        return [];
    const ids: string[] = [];
    if (normalized.includes("nba_api") || normalized.includes("pbpstats") || normalized.includes("stats.nba.com"))
        ids.push("nba_api");
    if (normalized.includes("basketball_reference") || normalized.includes("bbref") || normalized.startsWith("bref"))
        ids.push("basketball_reference");
    if (normalized.includes("espn"))
        ids.push("espn");
    return ids;
}

function contractLiveSources(meta: Record<string, unknown> | undefined, producer: string | undefined) {
    const declared = Array.isArray(meta?.live_sources) ? meta.live_sources : [];
    const sources: string[] = [];
    for (const candidate of [...declared, producer]) {
        const text = provenanceText(candidate);
        if (!text)
            continue;
        const candidates = /^https?:\/\/\S+$/i.test(text) ? [text] : liveProducerIds(text);
        for (const source of candidates)
            if (!sources.includes(source))
                sources.push(source);
    }
    return sources;
}

function compositeProducer(value: string | undefined) {
    const normalized = value?.trim().toLowerCase().replace(/-/g, "_");
    if (!normalized)
        return false;
    if (normalized.includes("+") || normalized.includes("mixed") || normalized.includes("composite"))
        return true;
    const producerCount = liveProducerIds(normalized).length;
    return producerCount > 1 || (producerCount > 0 && normalized.includes("warehouse"));
}

export function resolveProvenance(record: SourceRecord, data: Record<string, unknown>) {
    const meta = objectValue(data?.meta);
    const source = provenanceText(meta?.source);
    const warehouseId = provenanceText(meta?.warehouse_id);
    const fallback = objectValue(meta?.live_fallback);
    const fallbackOutcome = provenanceText(fallback?.outcome);
    const lineage = provenanceText(meta?.lineage_kind);
    const fetchedAt = provenanceText(meta?.fetched_at);
    const live = lineage === "live" || fallbackOutcome === "served" ||
        (meta?.cached === false && fetchedAt !== undefined && warehouseId === undefined);
    const declaresWarehouse = meta?.dataset === "warehouse" || source === "warehouse" || source?.startsWith("warehouse:") === true;
    const infersWarehouseIdentity = lineage === undefined && fallbackOutcome === undefined &&
        meta?.cached !== false && !compositeProducer(source);
    const warehouse = !live && warehouseId !== undefined &&
        (declaresWarehouse || meta?.cached === true || fallbackOutcome === "stale" || infersWarehouseIdentity);
    const origin = live ? "live" : warehouse ? "warehouse" : "undeclared";
    const producer = firstProvenanceText(fallback?.live_source, source);
    const asOf = firstProvenanceText(meta?.as_of, meta?.data_through, meta?.salary_date, meta?.fetched_at, meta?.last_fetch);
    const sql = firstProvenanceText(record.args?.sql, data?.sql, meta?.sql);
    return {
        capability: record.tool, origin,
        live_sources: origin === "live" ? contractLiveSources(meta, producer) : [],
        ...(origin === "warehouse" && warehouseId ? { warehouse_id: warehouseId } : {}),
        ...(source ? { dataset: source } : {}),
        ...(typeof meta?.season === "string" ? { season: meta.season } : {}),
        ...(asOf ? { as_of: asOf } : {}),
        ...(sql ? { sql } : {})
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

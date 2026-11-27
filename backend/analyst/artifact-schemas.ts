import { Type } from "typebox";
import { Value } from "typebox/value";
import { objectValue } from "./python-tools.js";

const label = Type.String({ minLength: 1 });
const optionalLabel = Type.Optional(Type.String({ minLength: 1 }));
const numberValue = Type.Number();
const nullableNumber = Type.Union([Type.Number(), Type.Null()]);

const tableColumnSchema = Type.Object({
    key: label,
    label: label,
    numeric: Type.Optional(Type.Boolean())
}, { additionalProperties: false });

const compareRowSchema = Type.Object({
    label: label,
    a: numberValue,
    b: numberValue
}, { additionalProperties: false });

const chartToneSchema = Type.Union([
    Type.Literal("ink"),
    Type.Literal("muted"),
    Type.Literal("accent"),
    Type.Literal("good"),
    Type.Literal("warn")
]);

const chartSeriesSchema = Type.Object({
    name: label,
    values: Type.Array(nullableNumber, { minItems: 1 }),
    tone: Type.Optional(chartToneSchema)
}, { additionalProperties: false });

const shotZoneSchema = Type.Object({
    x: numberValue,
    y: numberValue,
    att: Type.Number({ minimum: 0 }),
    pct: Type.Number({ minimum: 0 }),
    makes: Type.Optional(Type.Number({ minimum: 0 })),
    delta: Type.Optional(numberValue),
    label: optionalLabel
}, { additionalProperties: false });

const scatterPointSchema = Type.Object({
    label: label,
    x: numberValue,
    y: numberValue,
    highlight: Type.Optional(Type.Boolean())
}, { additionalProperties: false });

const chartMarkSchema = Type.Object({
    value: numberValue,
    label: label
}, { additionalProperties: false });

const chartAnnotationSchema = Type.Object({
    index: Type.Integer({ minimum: 0 }),
    text: label
}, { additionalProperties: false });

export const artifactSourceSelectorSchema = Type.Object({
    ref: Type.String({ minLength: 1 }),
    rows: Type.Optional(Type.Array(Type.Integer({ minimum: 0 }), { minItems: 1 })),
    columns: Type.Optional(Type.Array(Type.String({ minLength: 1 }), { minItems: 1 }))
}, { additionalProperties: false });

const optionalSources = Type.Optional(Type.Array(artifactSourceSelectorSchema, { minItems: 1 }));

const artifactSchemas = {
    table: Type.Object({
        kind: Type.Literal("table"),
        title: label,
        columns: Type.Array(tableColumnSchema, { minItems: 1 }),
        rows: Type.Array(Type.Unknown(), { minItems: 1 }),
        footnote: optionalLabel,
        sources: optionalSources
    }, { additionalProperties: false }),
    compare: Type.Object({
        kind: Type.Literal("compare"),
        title: label,
        aName: label,
        bName: label,
        rows: Type.Array(compareRowSchema, { minItems: 1 }),
        sources: optionalSources
    }, { additionalProperties: false }),
    chart: Type.Object({
        kind: Type.Literal("chart"),
        title: label,
        subtitle: optionalLabel,
        variant: Type.Optional(Type.Union([Type.Literal("line"), Type.Literal("bar")])),
        series: Type.Array(chartSeriesSchema, { minItems: 1 }),
        unit: optionalLabel,
        xLabels: Type.Optional(Type.Array(label)),
        xLabel: optionalLabel,
        yLabel: optionalLabel,
        marks: Type.Optional(Type.Array(chartMarkSchema)),
        annotations: Type.Optional(Type.Array(chartAnnotationSchema)),
        labelValues: Type.Optional(Type.Boolean()),
        footnote: optionalLabel,
        sources: optionalSources
    }, { additionalProperties: false }),
    shot_chart: Type.Object({
        kind: Type.Literal("shot_chart"),
        title: label,
        zones: Type.Array(shotZoneSchema, { minItems: 1 }),
        footnote: optionalLabel,
        sources: optionalSources
    }, { additionalProperties: false }),
    scatter: Type.Object({
        kind: Type.Literal("scatter"),
        title: label,
        xLabel: label,
        yLabel: label,
        xMid: Type.Optional(numberValue),
        yMid: Type.Optional(numberValue),
        points: Type.Array(scatterPointSchema, { minItems: 1 }),
        footnote: optionalLabel,
        sources: optionalSources
    }, { additionalProperties: false })
} as const;

type KnownArtifactKind = keyof typeof artifactSchemas;

function isKnownArtifactKind(kind: string): kind is KnownArtifactKind {
    return Object.hasOwn(artifactSchemas, kind);
}

function schemaProblems(schema: (typeof artifactSchemas)[KnownArtifactKind], artifact: unknown): string {
    const byPath = new Map<string, string[]>();
    for (const error of Value.Errors(schema, artifact)) {
        const path = error.instancePath || "/";
        const messages = byPath.get(path) ?? [];
        if (!messages.includes(error.message))
            messages.push(error.message);
        byPath.set(path, messages);
    }
    return [...byPath.entries()].slice(0, 6)
        .map(([path, messages]) => `${path}: ${messages.join(" or ")}`)
        .join("; ");
}

function retryHint(kind: string): string {
    return ` Load the visual-artifacts skill for the exact ${kind} schema and resubmit.`;
}

function isCell(value: unknown): value is string | number | null {
    return value === null || typeof value === "string" || typeof value === "number";
}

function validateTableRows(artifact: Record<string, unknown>, index: number) {
    const columns = (artifact.columns as { key: string }[]).map(column => column.key);
    const rows = artifact.rows as unknown[];
    rows.forEach((row, rowIndex) => {
        const at = `artifacts[${index}].rows[${rowIndex}]`;
        if (Array.isArray(row)) {
            if (row.length !== columns.length)
                throw new Error(`Invalid table artifact at ${at}: expected ${columns.length} cell(s) to match the declared columns, got ${row.length}.${retryHint("table")}`);
            if (!row.every(isCell))
                throw new Error(`Invalid table artifact at ${at}: array cells must be string, number or null.${retryHint("table")}`);
            return;
        }
        const record = objectValue(row);
        if (!record)
            throw new Error(`Invalid table artifact at ${at}: each row must be an array of cells or an object keyed by column.${retryHint("table")}`);
        for (const key of columns) {
            if (!Object.hasOwn(record, key))
                throw new Error(`Invalid table artifact at ${at}: missing column '${key}'. Object rows must provide every declared column; use null for a missing value.${retryHint("table")}`);
        }
        for (const [key, value] of Object.entries(record)) {
            if (!isCell(value))
                throw new Error(`Invalid table artifact at ${at}.${key}: cell values must be string, number or null.${retryHint("table")}`);
        }
    });
}

function validateChartValues(artifact: Record<string, unknown>, index: number) {
    const series = artifact.series as { values: (number | null)[] }[];
    if (!series.some(entry => entry.values.some(value => value !== null)))
        throw new Error(`Invalid chart artifact at artifacts[${index}]: every series value is null, so nothing would render. Include at least one numeric observation or omit the artifact.${retryHint("chart")}`);
}

function normalizeShotChart(artifact: Record<string, unknown>): Record<string, unknown> {
    if (artifact.kind !== "shot_chart" || !Array.isArray(artifact.zones) || artifact.zones.length === 0)
        return artifact;
    const zones = artifact.zones.map(objectValue);
    if (zones.some(z => !z || typeof z.pct !== "number" || z.pct <= 0 || z.pct > 1))
        return artifact;
    return {
        ...artifact,
        zones: zones.map(z => ({ ...z, pct: Math.round((z!.pct as number) * 1000) / 10 }))
    };
}

export function validateAnswerArtifact(artifact: Record<string, unknown>, index: number): Record<string, unknown> {
    const kind = typeof artifact.kind === "string" ? artifact.kind : "";
    if (!isKnownArtifactKind(kind))
        return artifact;
    const schema = artifactSchemas[kind];
    if (!Value.Check(schema, artifact)) {
        const problems = schemaProblems(schema, artifact);
        throw new Error(`Invalid ${kind} artifact at artifacts[${index}]: ${problems}. Load the visual-artifacts skill for the exact ${kind} schema and resubmit.`);
    }
    if (kind === "table")
        validateTableRows(artifact, index);
    if (kind === "chart")
        validateChartValues(artifact, index);
    return kind === "shot_chart" ? normalizeShotChart(artifact) : artifact;
}

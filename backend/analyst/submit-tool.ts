import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import { defineTool } from "@earendil-works/pi-coding-agent";
import { objectValue, sourceResult, sourceRecordSchema, type SourceRecord } from "./python-tools.js";
import { resolvePlayerCard } from "./player-card.js";

export { sourceRecordSchema, type SourceRecord } from "./python-tools.js";

export const anchorSelectorSchema = Type.Object({
    ref: Type.String({ minLength: 1 }),
    row: Type.Integer({ minimum: 0 }),
    columns: Type.Array(Type.String({ minLength: 1 }), { minItems: 1 })
}, { additionalProperties: false });

export type AnchorSelector = Static<typeof anchorSelectorSchema>;

export const answerBlockSchema = Type.Object({
    text: Type.String({ minLength: 1 }),
    anchors: Type.Optional(Type.Array(anchorSelectorSchema))
}, { additionalProperties: false });

export type AnswerBlock = Static<typeof answerBlockSchema>;

export const submitAnswerSchema = Type.Object({
    blocks: Type.Array(answerBlockSchema, { minItems: 1 }),
    artifacts: Type.Optional(Type.Array(Type.Record(Type.String(), Type.Unknown())))
}, { additionalProperties: false });

export type AnswerSubmission = Static<typeof submitAnswerSchema>;

function validateAnchor(
    anchor: AnchorSelector,
    getSource: (ref: string) => SourceRecord | undefined,
    availableRefs?: readonly string[]
) {
    const record = getSource(anchor.ref);
    if (!record) {
        const refHint = availableRefs && availableRefs.length > 0
            ? `. Available refs: [${availableRefs.slice(0, 20).join(", ")}]`
            : "";
        throw new Error(`Unknown source ref: ${anchor.ref}${refHint}`);
    }
    const res = sourceResult(record);
    if (res.isError)
        throw new Error(`Source ref is an error result: ${anchor.ref}`);
    const data = objectValue(res.structuredContent.result);
    if (!data)
        throw new Error(`Source ref has no object data: ${anchor.ref}`);
    const rows = Array.isArray(data.rows) ? data.rows : undefined;
    if (!rows)
        throw new Error(`Source ref has no rows array: ${anchor.ref}`);
    if (anchor.row >= rows.length)
        throw new Error(`Anchor row index ${anchor.row} out of bounds (length: ${rows.length}) for ref: ${anchor.ref}`);
    const rowData = objectValue(rows[anchor.row]);
    if (!rowData)
        throw new Error(`Anchor row ${anchor.row} is not an object for ref: ${anchor.ref}`);
    for (const col of anchor.columns) {
        if (!Object.hasOwn(rowData, col)) {
            const availableColumns = Object.keys(rowData).slice(0, 30).join(", ");
            throw new Error(`Column '${col}' does not exist on row ${anchor.row} for ref: ${anchor.ref}. Available columns: [${availableColumns}]. Fix the column name or omit anchors for derived values.`);
        }
    }
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

export function validateAnswerSubmission(
    input: unknown,
    getSource: (ref: string) => SourceRecord | undefined,
    availableRefs?: readonly string[]
): AnswerSubmission {
    if (!Value.Check(submitAnswerSchema, input)) {
        throw new Error("Invalid answer submission schema: blocks with non-empty text required");
    }
    const blocks = input.blocks.map(block => {
        const anchors = block.anchors ?? [];
        for (const anchor of anchors)
            validateAnchor(anchor, getSource, availableRefs);
        return { text: block.text, anchors };
    });
    const artifacts = input.artifacts ? structuredClone(input.artifacts).map(artifact =>
        artifact.kind === "player_card" ? resolvePlayerCard(artifact, getSource) : normalizeShotChart(artifact)
    ) : undefined;
    return artifacts !== undefined ? { blocks, artifacts } : { blocks };
}

export function createSubmitAnswerTool(
    getContextSources: () => SourceRecord[],
    onAccept: (submission: AnswerSubmission) => void
) {
    return defineTool({
        name: "submit_answer",
        label: "Submit answer",
        description: "Submit final prose blocks with optional source selectors and visual artifacts (table, compare, chart, shot_chart, scatter, player_card). Load visual-artifacts for schemas. player_card uses ref/row/nameColumn and metrics [{column,label}], with optional sections [{label, ref, row, metrics, fields}] each resolved from its own source row; the host resolves values, units and per-section provenance. Validates selector traceability, not semantic correctness.",
        parameters: submitAnswerSchema,
        async execute(_callId, args) {
            const sources = getContextSources();
            const sourceMap = new Map(sources.map(s => [s.ref, s]));
            const validated = validateAnswerSubmission(args, ref => sourceMap.get(ref), [...sourceMap.keys()]);
            onAccept(validated);
            return {
                content: [{ type: "text", text: `Answer submitted with ${validated.blocks.length} block(s).` }],
                details: undefined
            };
        }
    });
}

import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import { defineTool } from "@earendil-works/pi-coding-agent";
import { objectValue, sourceResult, type SourceRecord } from "./python-tools.js";

export const anchorSelectorSchema = Type.Object({
    ref: Type.String({ minLength: 1 }),
    row: Type.Integer({ minimum: 0 }),
    columns: Type.Array(Type.String({ minLength: 1 }), { minItems: 1 })
}, { additionalProperties: false });

export type AnchorSelector = Static<typeof anchorSelectorSchema>;

export const answerBlockSchema = Type.Object({
    text: Type.String({ minLength: 1 }),
    anchors: Type.Array(anchorSelectorSchema)
}, { additionalProperties: false });

export type AnswerBlock = Static<typeof answerBlockSchema>;

export const submitAnswerSchema = Type.Object({
    blocks: Type.Array(answerBlockSchema, { minItems: 1 })
}, { additionalProperties: false });

export type AnswerSubmission = Static<typeof submitAnswerSchema>;

export function validateAnswerSubmission(
    input: unknown,
    getSource: (ref: string) => SourceRecord | undefined
): AnswerSubmission {
    if (!Value.Check(submitAnswerSchema, input)) {
        throw new Error("Invalid answer submission schema: blocks with non-empty text required");
    }

    for (const block of input.blocks) {
        for (const anchor of block.anchors) {
            const record = getSource(anchor.ref);
            if (!record) {
                throw new Error(`Unknown source ref: ${anchor.ref}`);
            }
            const res = sourceResult(record);
            if (res.isError) {
                throw new Error(`Source ref is an error result: ${anchor.ref}`);
            }
            const structured = res.structuredContent;
            const data = objectValue(structured.result);
            if (!data) {
                throw new Error(`Source ref has no object data: ${anchor.ref}`);
            }
            const rows = Array.isArray(data.rows) ? data.rows : undefined;
            if (!rows) {
                throw new Error(`Source ref has no rows array: ${anchor.ref}`);
            }
            if (anchor.row >= rows.length) {
                throw new Error(`Anchor row index ${anchor.row} out of bounds (length: ${rows.length}) for ref: ${anchor.ref}`);
            }
            const rowData = objectValue(rows[anchor.row]);
            if (!rowData) {
                throw new Error(`Anchor row ${anchor.row} is not an object for ref: ${anchor.ref}`);
            }
            for (const col of anchor.columns) {
                if (!Object.hasOwn(rowData, col)) {
                    throw new Error(`Column '${col}' does not exist on row ${anchor.row} for ref: ${anchor.ref}`);
                }
            }
        }
    }
    return structuredClone(input);
}

export function createSubmitAnswerTool(
    getContextSources: () => SourceRecord[],
    onAccept: (submission: AnswerSubmission) => void
) {
    return defineTool({
        name: "submit_answer",
        label: "Submit answer",
        description: "Submit final prose blocks with optional source selectors. Validates selector traceability against actual rows and columns. Selectors do not verify truth.",
        parameters: submitAnswerSchema,
        async execute(_callId, args) {
            const sources = getContextSources();
            const sourceMap = new Map(sources.map(s => [s.ref, s]));
            const validated = validateAnswerSubmission(args, ref => sourceMap.get(ref));
            onAccept(validated);
            return {
                content: [{ type: "text", text: `Answer submitted with ${validated.blocks.length} block(s).` }],
                details: undefined
            };
        }
    });
}

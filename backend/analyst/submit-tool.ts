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
    artifacts: Type.Optional(Type.Array(Type.Record(Type.String(), Type.Unknown()))),
    omitted: Type.Optional(Type.Array(Type.String({ minLength: 1 })))
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

const KNOWN_ARTIFACT_KINDS: readonly string[] = ["table", "compare", "chart", "shot_chart", "scatter", "player_card", "memo"];

function nonEmptyArray(value: unknown): boolean {
    return Array.isArray(value) && value.length > 0;
}

function artifactRejectionReason(artifact: Record<string, unknown>): string | null {
    const kind = typeof artifact.kind === "string" ? artifact.kind : "";
    if (!KNOWN_ARTIFACT_KINDS.includes(kind))
        return kind ? `unknown artifact kind "${kind}"` : "artifact has no kind";
    if (typeof artifact.title !== "string" || !artifact.title)
        return `"${kind}" artifact has no title`;
    switch (kind) {
        case "table":
            return nonEmptyArray(artifact.columns) && nonEmptyArray(artifact.rows) ? null : `"table" artifact has no columns or rows`;
        case "compare":
            return nonEmptyArray(artifact.rows) ? null : `"compare" artifact has no rows`;
        case "chart":
            return nonEmptyArray(artifact.series) ? null : `"chart" artifact has no series`;
        case "scatter":
            return nonEmptyArray(artifact.points) ? null : `"scatter" artifact has no points`;
        case "shot_chart":
            return nonEmptyArray(artifact.zones) ? null : `"shot_chart" artifact has no zones`;
        case "memo":
            return nonEmptyArray(artifact.sections) &&
                (artifact.sections as unknown[]).some(s => {
                    const sec = objectValue(s);
                    return sec && typeof sec.heading === "string" && sec.heading !== "" &&
                        typeof sec.body === "string" && sec.body !== "";
                })
                ? null
                : `"memo" artifact has no sections with heading and body`;
        default:
            return null;
    }
}

export function validateAnswerSubmission(
    input: unknown,
    getSource: (ref: string) => SourceRecord | undefined,
    availableRefs?: readonly string[],
    artifactWarnings?: string[]
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
    const artifacts = input.artifacts ? structuredClone(input.artifacts).flatMap(artifact => {
        const reason = artifactRejectionReason(artifact);
        if (reason) {
            artifactWarnings?.push(`dropped artifact: ${reason}`);
            return [];
        }
        if (artifact.kind === "player_card") return [resolvePlayerCard(artifact, getSource)];
        if (artifact.kind === "memo") {
            for (const section of artifact.sections as unknown[]) {
                const anchors = objectValue(section)?.anchors;
                if (Array.isArray(anchors)) {
                    for (const anchor of anchors) {
                        if (!Value.Check(anchorSelectorSchema, anchor))
                            throw new Error("Invalid memo section anchor: ref, row and columns required");
                        validateAnchor(anchor, getSource, availableRefs);
                    }
                }
            }
        }
        return [normalizeShotChart(artifact)];
    }) : undefined;
||||||| 5eb4de42
    const artifacts = input.artifacts ? structuredClone(input.artifacts).map(artifact =>
        artifact.kind === "player_card" ? resolvePlayerCard(artifact, getSource) : normalizeShotChart(artifact)
    ) : undefined;
    const artifacts = input.artifacts ? structuredClone(input.artifacts).map(artifact => {
        if (artifact.kind === "player_card") return resolvePlayerCard(artifact, getSource);
        if (artifact.kind === "memo" && Array.isArray(artifact.sections)) {
            for (const section of artifact.sections) {
                const anchors = objectValue(section)?.anchors;
                if (Array.isArray(anchors)) {
                    for (const anchor of anchors) {
                        if (!Value.Check(anchorSelectorSchema, anchor))
                            throw new Error("Invalid memo section anchor: ref, row and columns required");
                        validateAnchor(anchor, getSource, availableRefs);
                    }
                }
            }
        }
        return normalizeShotChart(artifact);
    }) : undefined;    const omitted = input.omitted?.map(item => String(item));
    return {
        blocks,
        ...(artifacts !== undefined ? { artifacts } : {}),
        ...(omitted !== undefined ? { omitted } : {})
    };
}

export function createSubmitAnswerTool(
    getContextSources: () => SourceRecord[],
    onAccept: (submission: AnswerSubmission) => void
) {
    return defineTool({
        name: "submit_answer",
        label: "Submit answer",
        description: "Submit final prose blocks with optional source selectors and visual artifacts (table, compare, chart, shot_chart, scatter, player_card, memo). Load visual-artifacts for schemas. player_card uses ref/row/nameColumn and metrics [{column,label}]; the host resolves values and units from one source row. memo sections may carry anchors validated like block anchors. Artifacts with unknown kinds or no usable data are dropped and reported back as warnings. On a partial submission, pass omitted: string[] naming the requested sub-questions or checks left out. Validates selector traceability, not semantic correctness.",
||||||| 5eb4de42
        description: "Submit final prose blocks with optional source selectors and visual artifacts (table, compare, chart, shot_chart, scatter, player_card). Load visual-artifacts for schemas. player_card uses ref/row/nameColumn and metrics [{column,label}]; the host resolves values and units from one source row. On a partial submission, pass omitted: string[] naming the requested sub-questions or checks left out. Validates selector traceability, not semantic correctness.",
        description: "Submit final prose blocks with optional source selectors and visual artifacts (table, compare, chart, shot_chart, scatter, player_card, memo). Load visual-artifacts for schemas. player_card uses ref/row/nameColumn and metrics [{column,label}]; the host resolves values and units from one source row. memo sections may carry anchors validated like block anchors. On a partial submission, pass omitted: string[] naming the requested sub-questions or checks left out. Validates selector traceability, not semantic correctness.",        parameters: submitAnswerSchema,
        async execute(_callId, args) {
            const sources = getContextSources();
            const sourceMap = new Map(sources.map(s => [s.ref, s]));
            const warnings: string[] = [];
            const validated = validateAnswerSubmission(args, ref => sourceMap.get(ref), [...sourceMap.keys()], warnings);
            onAccept(validated);
            const omittedNote = validated.omitted && validated.omitted.length > 0
                ? ` ${validated.omitted.length} omitted part(s) recorded.`
                : "";
            const warningText = warnings.length > 0
                ? ` Warning: ${warnings.join("; ")}. Supported kinds: ${KNOWN_ARTIFACT_KINDS.join(", ")}. Resubmit with a corrected submission if the artifact matters.`
                : "";
            return {
                content: [{ type: "text", text: `Answer submitted with ${validated.blocks.length} block(s).${omittedNote}${warningText}` }],
                details: undefined
            };
        }
    });
}

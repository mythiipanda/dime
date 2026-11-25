import { Type, type Static } from "typebox";
import { Value } from "typebox/value";
import { defineTool } from "@earendil-works/pi-coding-agent";
import { objectValue, sourceResult, sourceRecordSchema, type SourceRecord } from "./python-tools.js";
import { resolvePlayerCard } from "./player-card.js";
import { validateAnswerArtifact } from "./artifact-schemas.js";
import { resolveTeamCard } from "./team-card.js";

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

const KNOWN_ARTIFACT_KINDS: readonly string[] = ["table", "compare", "chart", "shot_chart", "scatter", "player_card", "team_card", "memo"];

const MARKDOWN_TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
const MARKDOWN_TABLE_NULL_CELLS = new Set(["", "-", "—", "–", "n/a", "null"]);
const PROMOTED_TABLE_LIMIT = 3;
const PROMOTED_ROW_LIMIT = 100;

function splitMarkdownRow(line: string): string[] {
    return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim());
}

function isMarkdownSeparator(line: string): boolean {
    const cells = splitMarkdownRow(line);
    return cells.length > 0 && cells.every(cell => /^:?-+:?$/.test(cell));
}

function markdownCellValue(raw: string): string | number | null {
    const cleaned = raw.replace(/\*\*|__|`/g, "").trim();
    if (MARKDOWN_TABLE_NULL_CELLS.has(cleaned.toLowerCase()))
        return null;
    const numeric = cleaned.replace(/,/g, "").replace(/^\$/, "").replace(/%$/, "");
    if (/^-?\d+(?:\.\d+)?$/.test(numeric))
        return Number(numeric);
    return cleaned;
}

function markdownColumnKey(label: string, used: Set<string>): string {
    const base = label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "col";
    let key = base;
    let suffix = 2;
    while (used.has(key)) {
        key = `${base}_${suffix}`;
        suffix += 1;
    }
    used.add(key);
    return key;
}

function markdownTableTitle(lines: string[], tableStart: number): string {
    for (let i = tableStart - 1; i >= 0; i -= 1) {
        const line = lines[i].trim();
        if (!line)
            continue;
        if (MARKDOWN_TABLE_ROW_RE.test(line))
            break;
        const cleaned = line.replace(/^[#>\s*-]+/, "").replace(/\*\*/g, "").trim();
        return cleaned.length > 0 && cleaned.length <= 80 ? cleaned : "Table";
    }
    return "Table";
}

function markdownTableArtifacts(text: string): Record<string, unknown>[] {
    const lines = text.split("\n");
    const artifacts: Record<string, unknown>[] = [];
    let i = 0;
    while (i < lines.length - 1 && artifacts.length < PROMOTED_TABLE_LIMIT) {
        if (!(MARKDOWN_TABLE_ROW_RE.test(lines[i]) && isMarkdownSeparator(lines[i + 1]))) {
            i += 1;
            continue;
        }
        const start = i;
        const headers = splitMarkdownRow(lines[i]);
        const rawRows: string[][] = [];
        i += 2;
        while (i < lines.length && MARKDOWN_TABLE_ROW_RE.test(lines[i]) && !isMarkdownSeparator(lines[i])) {
            const cells = splitMarkdownRow(lines[i]);
            if (cells.length === headers.length)
                rawRows.push(cells);
            i += 1;
        }
        if (headers.length < 2 || rawRows.length === 0)
            continue;
        const used = new Set<string>();
        const columns = headers.map(header => {
            const key = markdownColumnKey(header, used);
            const label = header.replace(/\*\*/g, "").trim() || key;
            return { key, label };
        });
        const numeric = columns.map((_, index) => rawRows.some(cells => typeof markdownCellValue(cells[index]) === "number")
            && rawRows.every(cells => {
                const value = markdownCellValue(cells[index]);
                return value === null || typeof value === "number";
            }));
        artifacts.push({
            kind: "table",
            title: markdownTableTitle(lines, start),
            columns: columns.map((column, index) => ({ ...column, numeric: numeric[index] })),
            rows: rawRows.slice(0, PROMOTED_ROW_LIMIT).map(cells =>
                Object.fromEntries(columns.map((column, index) => [column.key, markdownCellValue(cells[index])])))
        });
    }
    return artifacts;
}

export function artifactRejectionReason(artifact: Record<string, unknown>): string | null {
    const kind = typeof artifact.kind === "string" ? artifact.kind : "";
    if (!KNOWN_ARTIFACT_KINDS.includes(kind))
        return kind ? `unknown artifact kind "${kind}"` : "artifact has no kind";
    switch (kind) {
        case "table":
            return !Array.isArray(artifact.rows) ? `"table" artifact has no columns or rows` : null;
        case "compare":
            return !Array.isArray(artifact.rows) ? `"compare" artifact has no rows` : null;
        case "chart":
            return !Array.isArray(artifact.series) ? `"chart" artifact has no series` : null;
        case "scatter":
            return !Array.isArray(artifact.points) ? `"scatter" artifact has no points` : null;
        case "shot_chart":
            return !Array.isArray(artifact.zones) ? `"shot_chart" artifact has no zones` : null;
        case "memo":
            return Array.isArray(artifact.sections) &&
                artifact.sections.some(s => {
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
    const submitted = input.artifacts ? structuredClone(input.artifacts) : [];
    if (!submitted.some(artifact => objectValue(artifact)?.kind === "table"))
        for (const block of blocks)
            submitted.push(...markdownTableArtifacts(block.text));
    const artifacts = (input.artifacts || submitted.length > 0) ? submitted.flatMap((artifact, index) => {
        const reason = artifactRejectionReason(artifact);
        if (reason) {
            artifactWarnings?.push(`dropped artifact: ${reason}`);
            return [];
        }
        const kind = artifact.kind as string;
        if (kind === "player_card") return [resolvePlayerCard(artifact, getSource)];
        if (kind === "team_card") return [resolveTeamCard(artifact, getSource)];
        if (kind === "memo") {
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
            return [artifact];
        }
        return [validateAnswerArtifact(artifact, index)];
    }) : undefined;
    const omitted = input.omitted?.map(item => String(item));
    return {
        blocks,
        ...(artifacts !== undefined ? { artifacts } : {}),
        ...(omitted !== undefined ? { omitted } : {})
    };
}

export function createSubmitAnswerTool(
    getContextSources: () => SourceRecord[],
    onAccept: (submission: AnswerSubmission) => void,
    onPreAudit?: (submission: AnswerSubmission) => string | null
) {
    return defineTool({
        name: "submit_answer",
        label: "Submit answer",
        description: "Submit final prose blocks with the visual artifacts the ask's shape calls for and optional source selectors. Ranked lists, leaderboards, top-N boards, rosters and multi-row results carry a 'table'; head-to-head asks a 'compare'; trends and season paths a 'chart'; court-location asks a 'shot_chart' — even when the ask names no artifact kind. Blocks carry the complete user-facing answer verbatim — the reader sees only what the submission holds, so write the full answer text into block text; never describe or announce the submission, name this tool call, or point to answer text that lives outside the submission. Kinds: (table, compare, chart, shot_chart, scatter, player_card, team_card, memo). Exact minimal shapes — table {kind,title,columns:[{key,label}],rows:[[cell,...] matching columns]}; compare {kind,title,aName,bName,rows:[{label,a,b}]}; chart {kind,title,series:[{name,values:[number|null,...]}],xLabels?} — series values align to xLabels by index; scatter {kind,title,xLabel,yLabel,points:[{label,x,y}]}; shot_chart {kind,title,zones:[{x,y,att,pct}]} with pct as a 0-1 fraction; memo {kind,title,sections:[{heading,body}]}. Extra keys are rejected — emit only listed fields plus an optional footnote. player_card/team_card use ref/row/nameColumn and metrics [{column,label}], with optional sections [{label, ref, row, metrics, fields}] each resolved from its own source row; the host resolves values, units and per-section provenance. memo sections may carry anchors validated like block anchors. Artifacts with unknown kinds or no usable data are dropped and reported back as warnings. Every figure the question requests must appear in the submission verbatim — exact computed values, never rounded-away approximations; a number shown only as prose commentary outside blocks does not count. A block that merely announces or confirms the analysis ('Submitted.', 'Done', 'see above') discards all of it — the reader never sees your tool results, so put the computed values and tables in the blocks even when you could not satisfy every check. On a partial submission, pass omitted: string[] naming the requested sub-questions or checks left out rather than silently dropping them. Validates selector traceability, not semantic correctness.",
        parameters: submitAnswerSchema,
        async execute(_callId, args) {
            const sources = getContextSources();
            const sourceMap = new Map(sources.map(s => [s.ref, s]));
            const warnings: string[] = [];
            const validated = validateAnswerSubmission(args, ref => sourceMap.get(ref), [...sourceMap.keys()], warnings);
            if (onPreAudit) {
                const rejection = onPreAudit(validated);
                if (rejection)
                    return {
                        content: [{ type: "text", text: rejection }],
                        details: undefined
                    };
            }
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

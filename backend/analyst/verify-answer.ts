import { defineTool } from "@earendil-works/pi-coding-agent";
import { sourceResult, type SourceRecord } from "./python-tools.js";
import { submitAnswerSchema, type AnswerSubmission } from "./submit-tool.js";

export type NumericClaim = {
    values: number[];
    raw: string;
    context: string;
};

export type NumericAudit = {
    checked: number;
    supported: number;
    unsupported: NumericClaim[];
    evidence_count: number;
};

const SEASON_RE = /\b(?:19|20)\d{2}\s*[-/–—]\s*\d{2,4}\b/g;
const MONEY_RE = /\$\s*([-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*([MBKmbk](?:illion|ILLION)?)?/g;
const PERCENT_RE = /([-+]?(?:\d{1,3}(?:,\d{3})+|\d+)?\.\d+|[-+]?\d+)\s*%/g;
const NUMBER_RE = /(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?!\w|\.\d)/g;
const NUMERIC_STRING_RE = /^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$/;
const ARTIFACT_SKIP_KEYS = new Set([
    "kind", "title", "subtitle", "description", "name", "label", "labels", "columns", "legend",
    "source", "units", "unit", "format", "encoding", "x_axis", "y_axis", "x_label", "y_label",
    "xLabel", "yLabel", "aName", "bName", "footnote", "tone", "row", "column", "index", "rank"
]);

function uniqueNumbers(values: number[]): number[] {
    return Array.from(new Set(values.filter(value => Number.isFinite(value))));
}

function pushClaim(claims: NumericClaim[], seen: Set<string>, values: number[], raw: string, context: string) {
    const clean = uniqueNumbers(values);
    if (clean.length === 0)
        return;
    const key = `${raw}\n${context}`;
    if (seen.has(key))
        return;
    seen.add(key);
    claims.push({ values: clean, raw, context });
}

function contextAround(text: string, index: number, length: number): string {
    const start = Math.max(0, index - 60);
    const end = Math.min(text.length, index + length + 60);
    return text.slice(start, end).replace(/\s+/g, " ").trim();
}

function expandMoney(num: number, suffix: string | undefined): number[] {
    const values = [num];
    const unit = (suffix ?? "").toLowerCase();
    if (unit.startsWith("b"))
        values.push(num * 1_000_000_000);
    else if (unit.startsWith("m"))
        values.push(num * 1_000_000);
    else if (unit.startsWith("k"))
        values.push(num * 1_000);
    else if (Math.abs(num) >= 100_000)
        values.push(num / 1_000_000);
    return values;
}

function addTextClaims(text: string, claims: NumericClaim[], seen: Set<string>) {
    const cleaned = text.replace(SEASON_RE, " ");
    for (const match of cleaned.matchAll(MONEY_RE)) {
        const num = Number(match[1].replace(/,/g, ""));
        if (!Number.isFinite(num))
            continue;
        pushClaim(claims, seen, expandMoney(num, match[2]), match[0], contextAround(cleaned, match.index ?? 0, match[0].length));
    }
    for (const match of cleaned.matchAll(PERCENT_RE)) {
        const num = Number(match[1].replace(/,/g, ""));
        if (!Number.isFinite(num))
            continue;
        pushClaim(claims, seen, [num, num / 100], match[0], contextAround(cleaned, match.index ?? 0, match[0].length));
    }
    for (const match of cleaned.matchAll(NUMBER_RE)) {
        const raw = match[0].replace(/,/g, "");
        if (raw === "" || raw === "+" || raw === "-" || raw === "." || raw === "+." || raw === "-.")
            continue;
        const num = Number(raw);
        if (!Number.isFinite(num))
            continue;
        const values = [num];
        if (!Number.isInteger(num) && num >= -100 && num <= 100)
            values.push(num / 100);
        pushClaim(claims, seen, values, match[0], contextAround(cleaned, match.index ?? 0, match[0].length));
    }
}

function addEvidenceValue(values: number[], value: unknown) {
    if (typeof value === "number") {
        if (Number.isFinite(value))
            values.push(value);
        return;
    }
    if (typeof value === "string" && NUMERIC_STRING_RE.test(value.trim())) {
        const num = Number(value.trim().replace(/,/g, ""));
        if (Number.isFinite(num))
            values.push(num);
    }
}

function walkEvidence(value: unknown, values: number[]) {
    if (value === null || value === undefined)
        return;
    if (Array.isArray(value)) {
        for (const item of value)
            walkEvidence(item, values);
        return;
    }
    if (typeof value === "object") {
        for (const item of Object.values(value as Record<string, unknown>))
            walkEvidence(item, values);
        return;
    }
    addEvidenceValue(values, value);
}

export function collectEvidenceNumbers(sources: readonly SourceRecord[]): number[] {
    const values: number[] = [];
    const seenRefs = new Set<string>();
    for (const record of sources) {
        if (seenRefs.has(record.ref))
            continue;
        seenRefs.add(record.ref);
        try {
            const result = sourceResult(record);
            if (result.isError)
                continue;
            walkEvidence(result.structuredContent.result, values);
        }
        catch {
        }
    }
    return values;
}

function collectArtifactClaims(value: unknown, claims: NumericClaim[], seen: Set<string>, path: string) {
    if (value === null || value === undefined)
        return;
    if (typeof value === "number") {
        if (Number.isFinite(value))
            pushClaim(claims, seen, [value], String(value), path);
        return;
    }
    if (typeof value === "string") {
        const trimmed = value.trim();
        if (NUMERIC_STRING_RE.test(trimmed)) {
            const num = Number(trimmed.replace(/,/g, ""));
            if (Number.isFinite(num))
                pushClaim(claims, seen, [num], value, path);
        }
        return;
    }
    if (Array.isArray(value)) {
        value.forEach((item, index) => collectArtifactClaims(item, claims, seen, `${path}[${index}]`));
        return;
    }
    if (typeof value === "object") {
        const record = value as Record<string, unknown>;
        const shotZone = typeof record.att === "number" && typeof record.pct === "number";
        for (const [key, item] of Object.entries(record)) {
            if (ARTIFACT_SKIP_KEYS.has(key))
                continue;
            if (shotZone && (key === "x" || key === "y"))
                continue;
            collectArtifactClaims(item, claims, seen, path ? `${path}.${key}` : key);
        }
    }
}

function numbersClose(a: number, b: number): boolean {
    const diff = Math.abs(a - b);
    if (diff <= 0.051)
        return true;
    return diff <= Math.max(Math.abs(a), Math.abs(b)) * 0.002;
}

export function auditAnswerNumbers(
    input: Pick<AnswerSubmission, "blocks" | "artifacts">,
    sources: readonly SourceRecord[]
): NumericAudit {
    const claims: NumericClaim[] = [];
    const seen = new Set<string>();
    for (const block of input.blocks)
        addTextClaims(block.text, claims, seen);
    (input.artifacts ?? []).forEach((artifact, index) => collectArtifactClaims(artifact, claims, seen, `artifacts[${index}]`));
    const evidence = collectEvidenceNumbers(sources);
    let supported = 0;
    const unsupported: NumericClaim[] = [];
    for (const claim of claims) {
        if (claim.values.some(value => evidence.some(evidenceValue => numbersClose(value, evidenceValue))))
            supported++;
        else
            unsupported.push(claim);
    }
    return { checked: claims.length, supported, unsupported, evidence_count: evidence.length };
}

export function createVerifyAnswerNumbersTool(getContextSources: () => SourceRecord[]) {
    return defineTool({
        name: "verify_answer_numbers",
        label: "Verify answer numbers",
        description: "Audit numeric literals in a draft submit_answer payload against successful tool results. Returns counts and unsupported literals with context; it does not submit the answer.",
        parameters: submitAnswerSchema,
        async execute(_callId, args) {
            const audit = auditAnswerNumbers(args, getContextSources());
            return {
                content: [{ type: "text", text: JSON.stringify(audit) }],
                details: audit
            };
        }
    });
}

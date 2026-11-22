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
    missing_in_artifacts: NumericClaim[];
    uncovered_asks: string[];
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

const ASK_ANCHOR_RE = /\b[A-Z][A-Z0-9]{1,}\b|\b[a-z]+[A-Z][\w%]*|\b\d+(?:[.,]\d+)*%?\b|\b[A-Z][a-z]{2,}\b/g;
const ASK_STOPWORDS = new Set([
    "the", "and", "for", "with", "which", "what", "each", "both", "using", "across",
    "compare", "show", "include", "provide", "compute", "analyze", "analyse", "summarize",
    "report", "build", "create", "give", "list", "make", "then", "also", "use",
    "submit", "hang", "answer",
    "who", "when", "where", "why", "how", "did", "does", "do", "is", "are",
    "was", "were", "has", "have", "had", "many", "much", "most", "least",
    "best", "worst", "first", "last", "all", "any", "every", "from", "into",
    "over", "under", "between", "against", "versus", "vs", "per", "during"
]);
const ASK_SKIP_RE = /\b(?:cite|source|verify_answer|submit_answer|footnote|provenance)\b/i;

export function auditAskCoverage(
    question: string,
    input: Pick<AnswerSubmission, "blocks" | "artifacts">
): string[] {
    const haystack = (
        input.blocks.map(block => block.text).join(" ") + " " +
        JSON.stringify(input.artifacts ?? [])
    ).toLowerCase();
    const clauses = question
        .split(/[?;!\n]+|(?<=\.)\s+(?=[A-Z])/)
        .map(clause => clause.trim())
        .filter(clause => clause.length >= 12 && !ASK_SKIP_RE.test(clause));
    const uncovered: string[] = [];
    for (const clause of clauses) {
        const anchors = new Set(
            (clause.match(ASK_ANCHOR_RE) ?? []).map(token => token.toLowerCase()).filter(token => !ASK_STOPWORDS.has(token))
        );
        if (anchors.size === 0)
            continue;
        const covered = [...anchors].some(token => haystack.includes(token));
        if (!covered)
            uncovered.push(clause);
    }
    return uncovered;
}

export function auditAnswerNumbers(
    input: Pick<AnswerSubmission, "blocks" | "artifacts">,
    sources: readonly SourceRecord[],
    question?: string
): NumericAudit {
    const proseClaims: NumericClaim[] = [];
    const proseSeen = new Set<string>();
    for (const block of input.blocks)
        addTextClaims(block.text, proseClaims, proseSeen);
    const artifactClaims: NumericClaim[] = [];
    const artifactSeen = new Set<string>();
    (input.artifacts ?? []).forEach((artifact, index) => collectArtifactClaims(artifact, artifactClaims, artifactSeen, `artifacts[${index}]`));
    const evidence = collectEvidenceNumbers(sources);
    const claims = [...proseClaims, ...artifactClaims];
    const supportedBy = (claim: NumericClaim, values: number[]) =>
        claim.values.some(value => values.some(other => numbersClose(value, other)));
    const artifactValues = artifactClaims.flatMap(claim => claim.values);
    const isSupported = (claim: NumericClaim) => supportedBy(claim, evidence);
    let supported = 0;
    const unsupported: NumericClaim[] = [];
    for (const claim of claims) {
        if (isSupported(claim))
            supported++;
        else
            unsupported.push(claim);
    }
    const missing_in_artifacts = (input.artifacts ?? []).length > 0
        ? proseClaims.filter(claim => isSupported(claim) && !supportedBy(claim, artifactValues))
        : [];
    const uncovered_asks = question ? auditAskCoverage(question, input) : [];
    return { checked: claims.length, supported, unsupported, evidence_count: evidence.length, missing_in_artifacts, uncovered_asks };
}

export function createVerifyAnswerNumbersTool(getContextSources: () => SourceRecord[], question?: string) {
    return defineTool({
        name: "verify_answer_numbers",
        label: "Verify answer numbers",
        description: "Audit a draft submit_answer payload: numeric literals vs successful tool results, prose figures missing from artifact payloads, and question clauses with no matching terms in the answer; it does not submit the answer.",
        parameters: submitAnswerSchema,
        async execute(_callId, args) {
            const audit = auditAnswerNumbers(args, getContextSources(), question);
            return {
                content: [{ type: "text", text: JSON.stringify(audit) }],
                details: audit
            };
        }
    });
}

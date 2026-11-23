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
    no_artifacts_on_artifact_ask: string[];
    metric_value_gaps: string[];
    unsupported_claims: string[];
    unevidenced_asks: string[];
};

const SEASON_RE = /\b(?:19|20)\d{2}\s*[-/–—]\s*\d{2,4}\b/g;
const MONEY_RE = /\$\s*([-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*([MBKmbk](?:illion|ILLION)?)?/g;
const PERCENT_RE = /([-+]?(?:\d{1,3}(?:,\d{3})+|\d+)?\.\d+|[-+]?\d+)\s*%/g;
const NUMBER_RE = /(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?!\w|\.\d)/g;
const NUMERIC_STRING_RE = /^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$/;
const META_CONTEXT_RE = /\b(?:budget|timed out|timeout|retr(?:y|ies|ied)|backoff|rate[ -]?limit|latency|429|exhaustion)\b/i;
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
    if (typeof value === "string") {
        for (const match of value.replace(SEASON_RE, " ").matchAll(NUMBER_RE)) {
            const num = Number(match[0].replace(/,/g, ""));
            if (Number.isFinite(num))
                values.push(num);
        }
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
const ARTIFACT_ASK_RE = /\b(?:tables?|compare|comparison|charts?|graphs?)\b/gi;
export const WAREHOUSE_TABLE_RE = /\b(?:silver|gold|bronze)_[a-z0-9_]+\b/gi;

export function missingRequiredTables(question: string | undefined, consulted: ReadonlySet<string>): string[] {
    if (!question)
        return [];
    const required = new Set((question.match(WAREHOUSE_TABLE_RE) ?? []).map(token => token.toLowerCase()));
    return [...required].filter(table => !consulted.has(table)).sort();
}

type StatTerm = { ask: string[]; present: string[] };

const STATS_VOCABULARY: Record<string, StatTerm> = {
    pts: { ask: ["points", "ppg", "pts", "scoring"], present: ["points", "pts", "ppg"] },
    reb: { ask: ["rebounds", "rebounding", "rpg", "reb"], present: ["rebounds", "reb", "oreb", "dreb"] },
    ast: { ask: ["assists", "apg", "ast"], present: ["assists", "ast", "apg"] },
    stl: { ask: ["steals", "spg", "stl"], present: ["steals", "stl", "spg"] },
    blk: { ask: ["blocks", "bpg", "blk"], present: ["blocks", "blk", "bpg"] },
    tov: { ask: ["turnovers", "tov"], present: ["turnovers", "tov"] },
    min: { ask: ["minutes", "mpg", "min per game", "minutes per game"], present: ["minutes", "min", "mpg"] },
    gp: { ask: ["games played", "games"], present: ["games", "gp"] },
    fgm: { ask: ["field goals made", "fgm"], present: ["fgm", "field goals made"] },
    fga: { ask: ["field goals attempted", "field goal attempts", "fga"], present: ["fga", "field goal attempts", "field goals attempted"] },
    fg_pct: { ask: ["field goal percentage", "field goal pct", "fg%", "fg pct", "shooting percentage", "shooting"], present: ["fg%", "fg pct", "fg_pct", "field goal percentage", "field goal pct"] },
    fg3a: { ask: ["threes attempted", "three pointers attempted", "3pa", "three point attempts"], present: ["3pa", "fg3a", "three point attempts"] },
    fg3_pct: { ask: ["three point percentage", "three point pct", "3p%", "3pt%", "3p pct", "three-point shooting"], present: ["3p%", "3p pct", "fg3_pct", "three point percentage", "three point pct"] },
    ft_pct: { ask: ["free throw percentage", "free throw pct", "ft%", "ft pct"], present: ["ft%", "ft pct", "ft_pct", "free throw percentage"] },
    efg_pct: { ask: ["effective field goal", "efg%", "efg"], present: ["efg%", "efg", "efg_pct", "effective field goal"] },
    ts_pct: { ask: ["true shooting", "ts%", "ts pct"], present: ["ts%", "ts pct", "ts_pct", "true shooting"] },
    usg_pct: { ask: ["usage rate", "usage", "usg%", "usg"], present: ["usg%", "usg", "usage", "usg_pct"] },
    tov_pct: { ask: ["turnover percentage", "turnover rate", "tov%"], present: ["tov%", "tov_pct", "turnover percentage", "turnover rate"] },
    orb_pct: { ask: ["offensive rebound percentage", "orb%", "oreb%"], present: ["orb%", "orb_pct", "oreb%", "offensive rebound"] },
    drb_pct: { ask: ["defensive rebound percentage", "drb%", "dreb%"], present: ["drb%", "drb_pct", "dreb%", "defensive rebound"] },
    off_rating: { ask: ["offensive rating", "ortg", "offensive rtg"], present: ["offensive rating", "ortg", "off_rating", "off rtg"] },
    def_rating: { ask: ["defensive rating", "drtg", "defensive rtg"], present: ["defensive rating", "drtg", "def_rating", "def rtg"] },
    net_rating: { ask: ["net rating", "net rtg", "netrtg"], present: ["net rating", "net rtg", "net_rating", "netrtg"] },
    pw_net: { ask: ["pythagorean", "pw_net", "pyth net", "pythagorean net"], present: ["pw_net", "pythagorean"] },
    pace: { ask: ["pace"], present: ["pace"] },
    pie: { ask: ["pie"], present: ["pie"] },
    per: { ask: ["player efficiency rating", "per rating"], present: ["per", "player efficiency rating"] },
    ws: { ask: ["win shares", "ws"], present: ["win shares", "ws"] },
    bpm: { ask: ["box plus minus", "bpm"], present: ["bpm", "box plus minus"] },
    vorp: { ask: ["vorp"], present: ["vorp"] },
    wins: { ask: ["wins", "win total"], present: ["wins", "win"] },
    win_pct: { ask: ["win percentage", "win pct", "win%", "winning percentage"], present: ["win%", "win pct", "win_pct", "winning percentage", "win percentage"] },
    plus_minus: { ask: ["plus minus", "plus-minus", "+/-", "on off", "on-off"], present: ["plus minus", "plus-minus", "+/-", "plus_minus", "on off", "on-off"] },
    salary: { ask: ["salary", "salaries", "cap hit", "contract value"], present: ["salary", "salaries", "cap hit", "contract"] },
    cap_hold: { ask: ["cap hold", "cap holds"], present: ["cap hold", "cap_hold"] },
    roster_names: { ask: ["roster", "roster names", "players on", "rotation", "lineup", "depth chart"], present: ["roster", "player", "players", "player_name", "lineup", "rotation"] },
    draft_picks: { ask: ["draft picks", "draft capital", "first round pick", "second round pick"], present: ["pick", "draft", "round"] },
};

const STAT_TERM_BOUNDARY = (term: string) =>
    new RegExp(`(?<![\\w%+/-])${term.replace(/[.*+?^${}()|[\]\\%]/g, "\\$&")}(?![\\w%+/-])`, "i");

const CAP_ASK_VOCABULARY: string[] = [
    "salary cap", "cap space", "cap room", "cap sheet", "cap hold", "cap table",
    "apron", "first apron", "second apron", "hard cap", "hard-capped", "hardcapped",
    "luxury tax", "tax line", "taxpayer", "tax bill", "tax club",
    "salary match", "matching band", "matching bands", "salary matching",
    "trade legality", "legality check", "trade machine",
    "sign-and-trade", "sign and trade", "trade exception", "tpe",
    "stepien", "draft capital", "draft-capital", "pick swap", "swap rights",
    "unprotected first", "protected pick", "pick protections", "consecutive first",
    "mid-level", "midlevel", "mle", "bi-annual exception", "bae",
    "bird rights", "max slot", "max offer", "max contract",
    "extension-eligible", "extension eligible", "cap flexibility", "dead money",
    "trade kicker", "aggregating", "aggregation", "free-agent class", "fa class",
    "seven-year rule", "seven year rule", "committed salary", "projected room",
];

export function isCapAsk(question: string | undefined): boolean {
    if (!question)
        return false;
    const normalized = question.toLowerCase().replace(/_/g, " ");
    return CAP_ASK_VOCABULARY.some(form => STAT_TERM_BOUNDARY(form).test(normalized));
}

export function isDataAsk(question: string | undefined): boolean {
    if (!question)
        return false;
    if ((question.match(WAREHOUSE_TABLE_RE) ?? []).length > 0)
        return true;
    if ((question.match(EVIDENCE_ANCHOR_RE) ?? []).some(token => !ASK_STOPWORDS.has(token.toLowerCase())))
        return true;
    for (const term of Object.values(STATS_VOCABULARY))
        if (term.ask.some(form => STAT_TERM_BOUNDARY(form).test(question)))
            return true;
    return false;
}

export function auditMetricCoverage(
    question: string,
    input: Pick<AnswerSubmission, "blocks" | "artifacts">
): string[] {
    const haystack = (
        input.blocks.map(block => block.text).join(" ") + " " +
        JSON.stringify(input.artifacts ?? [])
    ).toLowerCase();
    const gaps: string[] = [];
    for (const [metric, term] of Object.entries(STATS_VOCABULARY)) {
        const asked = term.ask.find(form => STAT_TERM_BOUNDARY(form).test(question));
        if (!asked)
            continue;
        const present = [...term.ask, ...term.present]
            .some(form => STAT_TERM_BOUNDARY(form).test(haystack));
        if (!present)
            gaps.push(`${metric} (asked via "${asked}")`);
    }
    return gaps;
}

export function collectEvidenceText(sources: readonly SourceRecord[]): string {
    const parts: string[] = [];
    const seenRefs = new Set<string>();
    for (const record of sources) {
        if (seenRefs.has(record.ref))
            continue;
        seenRefs.add(record.ref);
        try {
            const result = sourceResult(record);
            if (result.isError)
                continue;
            parts.push(JSON.stringify(result.structuredContent.result ?? ""));
        }
        catch {
        }
    }
    return parts.join(" ").toLowerCase();
}

function askClauses(question: string): string[] {
    return question
        .split(/[?;!\n]+|(?<=\.)\s+(?=[A-Z])/)
        .map(clause => clause.trim())
        .filter(clause => clause.length >= 12 && !ASK_SKIP_RE.test(clause));
}

function askAnchors(clause: string): Set<string> {
    return new Set(
        (clause.match(ASK_ANCHOR_RE) ?? [])
            .map(token => token.toLowerCase())
            .filter(token => !ASK_STOPWORDS.has(token))
    );
}

const EVIDENCE_ANCHOR_RE = /\b[A-Z][A-Z0-9]{1,}\b|\b\d+(?:[.,]\d+)*%?\b/g;

function evidenceAnchors(clause: string): Set<string> {
    return new Set(
        (clause.match(EVIDENCE_ANCHOR_RE) ?? [])
            .map(token => token.toLowerCase())
            .filter(token => !ASK_STOPWORDS.has(token))
    );
}

export function auditEvidenceCoverage(
    question: string,
    input: Pick<AnswerSubmission, "blocks" | "artifacts">,
    evidenceText: string
): string[] {
    const haystack = (
        input.blocks.map(block => block.text).join(" ") + " " +
        JSON.stringify(input.artifacts ?? [])
    ).toLowerCase();
    const unevidenced: string[] = [];
    for (const clause of askClauses(question)) {
        const anchors = evidenceAnchors(clause);
        if (anchors.size === 0)
            continue;
        if (![...anchors].some(token => haystack.includes(token)))
            continue;
        if (![...anchors].some(token => evidenceText.includes(token)))
            unevidenced.push(clause);
    }
    return unevidenced;
}

export function auditAskCoverage(
    question: string,
    input: Pick<AnswerSubmission, "blocks" | "artifacts">
): string[] {
    const haystack = (
        input.blocks.map(block => block.text).join(" ") + " " +
        JSON.stringify(input.artifacts ?? [])
    ).toLowerCase();
    const uncovered: string[] = [];
    for (const clause of askClauses(question)) {
        const anchors = askAnchors(clause);
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
    question?: string,
    extraEvidenceText?: string
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
    const metric_value_gaps = question ? auditMetricCoverage(question, input) : [];
    const no_artifacts_on_artifact_ask = question && (input.artifacts ?? []).length === 0
        ? [...new Set((question.match(ARTIFACT_ASK_RE) ?? []).map(token => token.toLowerCase()))]
        : [];
    const questionValues = (() => {
        const questionClaims: NumericClaim[] = [];
        addTextClaims(question ?? "", questionClaims, new Set<string>());
        return questionClaims.flatMap(claim => claim.values);
    })();
    const unsupported_claims = unsupported
        .filter(claim => !META_CONTEXT_RE.test(claim.context))
        .filter(claim => !claim.values.every(value => questionValues.some(asked => numbersClose(value, asked))))
        .filter(claim => /%|\$/.test(claim.raw) || claim.values.some(value => !Number.isInteger(value) || Math.abs(value) >= 100))
        .slice(0, 8)
        .map(claim => `${claim.raw} (near "${claim.context.slice(0, 80)}")`);
    const unevidenced_asks = question
        ? auditEvidenceCoverage(question, input, (collectEvidenceText(sources) + " " + (extraEvidenceText ?? "")).toLowerCase()).slice(0, 10)
        : [];
    return { checked: claims.length, supported, unsupported, evidence_count: evidence.length, missing_in_artifacts, uncovered_asks, no_artifacts_on_artifact_ask, metric_value_gaps, unsupported_claims, unevidenced_asks };
}

export function createVerifyAnswerNumbersTool(getContextSources: () => SourceRecord[], question?: string) {
    return defineTool({
        name: "verify_answer_numbers",
        label: "Verify answer numbers",
        description: "Audit a draft submit_answer payload: numeric literals vs successful tool results, prose figures missing from artifact payloads, question clauses with no matching terms in the answer, required stat/metric terms from the question absent from both prose and payloads, asks for tables/compares/charts with zero artifacts, stat-shaped figures tracing to no tool output (unsupported_claims), and ask facets narrated in the answer but absent from every tool result and call (unevidenced_asks); it does not submit the answer.",
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

export const ZERO_EVIDENCE_DATA_ASK_FLAG = "zero data tool calls and no evidence sources before submitting a data-grounded answer";

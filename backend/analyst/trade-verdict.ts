import { Type } from "typebox";
import { Value } from "typebox/value";
import { objectValue, sourceResult, type SourceRecord } from "./python-tools.js";
import { field, resolveProvenance } from "./player-card.js";

export const tradeVerdictSchema = Type.Object({
    kind: Type.Literal("trade_verdict"),
    title: field,
    ref: field
}, { additionalProperties: false });

const EVALUATION_TOOLS = new Set(["get_trade_check", "get_trade_legality"]);

function textOrNull(value: unknown): string | null {
    return typeof value === "string" && value.trim() ? value : null;
}

function numOrNull(value: unknown): number | null {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringList(value: unknown): string[] {
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function resolveTpeCreation(value: unknown) {
    const tpe = objectValue(value);
    if (!tpe) return undefined;
    const amount = numOrNull(tpe.amount);
    if (amount === null) return undefined;
    return {
        amount,
        ...(textOrNull(tpe.condition) ? { condition: tpe.condition } : {})
    };
}

type VerdictTeam = Record<string, unknown> & { team: string };

function teamFromTradeCheck(side: Record<string, unknown>, other: Record<string, unknown>): VerdictTeam {
    const team: VerdictTeam = {
        team: String(side.team ?? ""),
        playersOut: stringList(side.players),
        playersIn: stringList(other.players)
    };
    const outgoing = numOrNull(side.out);
    const incoming = numOrNull(other.out);
    if (outgoing !== null) team.outgoing = outgoing;
    if (incoming !== null) team.incoming = incoming;
    const payroll = numOrNull(side.payroll);
    if (payroll !== null) team.payrollBefore = payroll;
    const allowedIn = numOrNull(side.allowed_in);
    if (allowedIn !== null) team.allowedIncoming = allowedIn;
    const matchRule = textOrNull(side.match_rule);
    if (matchRule) team.matchRule = matchRule;
    const hardCap = textOrNull(side.hard_cap);
    if (hardCap) team.hardCap = hardCap;
    if (side.over_apron1 === true) team.overApron1 = true;
    if (side.over_apron2 === true) team.overApron2 = true;
    const tpe = resolveTpeCreation(side.tpe_creation);
    if (tpe) team.tpeCreation = tpe;
    return team;
}

function teamFromTradeLegality(row: Record<string, unknown>): VerdictTeam {
    const team: VerdictTeam = {
        team: String(row.team ?? ""),
        playersOut: stringList(row.players_out),
        playersIn: stringList(row.players_in)
    };
    const outgoing = numOrNull(row.outgoing);
    if (outgoing !== null) team.outgoing = outgoing;
    const incoming = numOrNull(row.incoming);
    if (incoming !== null) team.incoming = incoming;
    const payrollBefore = numOrNull(row.payroll_before);
    if (payrollBefore !== null) team.payrollBefore = payrollBefore;
    const payrollAfter = numOrNull(row.payroll_after);
    if (payrollAfter !== null) team.payrollAfter = payrollAfter;
    const allowedIn = numOrNull(row.allowed_incoming);
    if (allowedIn !== null) team.allowedIncoming = allowedIn;
    const matchRule = textOrNull(row.match_rule);
    if (matchRule) team.matchRule = matchRule;
    const hardCap = textOrNull(row.hard_cap);
    if (hardCap) team.hardCap = hardCap;
    if (row.matching_ok === false) team.matchingFailed = true;
    if (row.aggregates === true) team.aggregates = true;
    const tpe = resolveTpeCreation(row.tpe_creation);
    if (tpe) team.tpeCreation = tpe;
    return team;
}

function resolveChecks(value: unknown): { rule: string; note?: string }[] {
    if (!Array.isArray(value)) return [];
    const checks: { rule: string; note?: string }[] = [];
    for (const entry of value) {
        const check = objectValue(entry);
        if (!check) continue;
        const rule = textOrNull(check.rule);
        if (!rule) continue;
        const note = textOrNull(check.note);
        checks.push({ rule, ...(note ? { note } : {}) });
        if (checks.length >= 8) break;
    }
    return checks;
}

export function resolveTradeVerdict(artifact: Record<string, unknown>, getSource: (ref: string) => SourceRecord | undefined): Record<string, unknown> {
    if (!Value.Check(tradeVerdictSchema, artifact))
        throw new Error("Invalid trade_verdict: provide exactly title and ref — the ref of this run's get_trade_check or get_trade_legality result. The host resolves the verdict; never write outcomes, salaries or issues yourself.");
    const record = getSource(artifact.ref as string);
    if (!record)
        throw new Error(`trade_verdict source ref '${artifact.ref}' is not part of this run — emit it only after a trade evaluation tool actually ran.`);
    if (!EVALUATION_TOOLS.has(record.tool))
        throw new Error(`trade_verdict ref must come from get_trade_check or get_trade_legality — '${record.tool}' is not a trade evaluation. The verdict must be the evaluator's, never a paraphrase of other data.`);
    const result = sourceResult(record);
    if (result.isError)
        throw new Error("trade_verdict source evaluation errored — there is no verdict to show.");
    const data = objectValue(result.structuredContent.result);
    if (!data)
        throw new Error("trade_verdict source has no structured result.");

    let legal: boolean | undefined;
    let issues: string[] = [];
    let teams: VerdictTeam[] = [];
    let checksRaw: unknown;

    if (record.tool === "get_trade_check") {
        const rows = objectValue(data.rows);
        const sideA = objectValue(rows?.team_a);
        const sideB = objectValue(rows?.team_b);
        legal = rows?.legal === true ? true : rows?.legal === false ? false : undefined;
        if (!sideA || !sideB || legal === undefined)
            throw new Error("trade_verdict source is missing the verdict structure — rerun the evaluation instead of substituting.");
        issues = stringList(rows?.issues);
        teams = [teamFromTradeCheck(sideA, sideB), teamFromTradeCheck(sideB, sideA)];
        checksRaw = rows?.checks;
    } else {
        legal = data.legal === true ? true : data.legal === false ? false : undefined;
        const rowsList = Array.isArray(data.rows) ? data.rows : [];
        if (legal === undefined || rowsList.length === 0)
            throw new Error("trade_verdict source is missing the verdict structure — rerun the evaluation instead of substituting.");
        issues = stringList(data.issues);
        teams = rowsList.map(row => {
            const entry = objectValue(row);
            if (!entry) throw new Error("trade_verdict source has a malformed team row.");
            return teamFromTradeLegality(entry);
        });
        checksRaw = data.checks;
    }

    if (teams.some(team => !team.team))
        throw new Error("trade_verdict source has a team row without a team abbreviation.");

    return {
        kind: "trade_verdict",
        title: artifact.title,
        legal,
        ...(issues.length ? { issues } : {}),
        teams,
        checks: resolveChecks(checksRaw),
        evaluationTool: record.tool,
        sourceRef: artifact.ref,
        provenance: resolveProvenance(record, data)
    };
}

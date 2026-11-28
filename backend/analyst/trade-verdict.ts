import { Type } from "typebox";
import { Value } from "typebox/value";
import { objectValue, sourceResult, type SourceRecord } from "./python-tools.js";
import { field, resolveProvenance } from "./player-card.js";
import { constructionSeasonEcho, tradeConstructionFromArgs } from "./construction.js";

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


function resolvePicks(value: unknown): { year: number; round: number; swap?: boolean; protection?: string }[] {
    if (!Array.isArray(value)) return [];
    const picks: { year: number; round: number; swap?: boolean; protection?: string }[] = [];
    for (const entry of value) {
        const pick = objectValue(entry);
        const year = numOrNull(pick?.year);
        if (!pick || year === null) continue;
        const round = numOrNull(pick.round) ?? 1;
        const protection = textOrNull(pick.protection);
        picks.push({
            year, round,
            ...(pick.swap === true ? { swap: true } : {}),
            ...(protection ? { protection } : {})
        });
        if (picks.length >= 8) break;
    }
    return picks;
}

type VerdictTeam = Record<string, unknown> & { team: string };

function teamFromTradeCheck(side: Record<string, unknown>, other: Record<string, unknown>): VerdictTeam {
    const team: VerdictTeam = {
        team: String(side.team ?? ""),
        playersOut: stringList(side.players),
        playersIn: stringList(other.players)
    };
    const outgoing = numOrNull(side.outgoing) ?? numOrNull(side.out);
    const incoming = numOrNull(other.outgoing) ?? numOrNull(other.out);
    if (outgoing !== null) team.outgoing = outgoing;
    if (incoming !== null) team.incoming = incoming;
    const payroll = numOrNull(side.payroll);
    if (payroll !== null) {
        team.payrollBefore = payroll;
        if (outgoing !== null && incoming !== null) team.payrollAfter = payroll - outgoing + incoming;
    }
    const allowedIn = numOrNull(side.allowed_incoming) ?? numOrNull(side.allowed_in);
    if (allowedIn !== null) {
        team.allowedIncoming = allowedIn;
        if (incoming !== null && incoming > allowedIn) team.matchingFailed = true;
    }
    const matchRule = textOrNull(side.match_rule);
    if (matchRule) team.matchRule = matchRule;
    const hardCap = textOrNull(side.hard_cap);
    if (hardCap) team.hardCap = hardCap;
    if (side.over_apron1 === true) team.overApron1 = true;
    if (side.over_apron2 === true) team.overApron2 = true;
    if ((team.playersOut as string[]).length > 1) team.aggregates = true;
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
    const picksOut = resolvePicks(row.picks_out);
    if (picksOut.length) team.picksOut = picksOut;
    const picksIn = resolvePicks(row.picks_in);
    if (picksIn.length) team.picksIn = picksIn;
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
        const rowsDict = objectValue(data.rows);
        let sideA: Record<string, unknown> | null = null;
        let sideB: Record<string, unknown> | null = null;
        if (rowsDict) {
            sideA = objectValue(rowsDict.team_a) ?? null;
            sideB = objectValue(rowsDict.team_b) ?? null;
            legal = rowsDict.legal === true ? true : rowsDict.legal === false ? false : undefined;
            issues = stringList(rowsDict.issues);
            checksRaw = rowsDict.checks;
        } else if (Array.isArray(data.rows)) {
            const entries = data.rows.map(row => objectValue(row)).filter((entry): entry is Record<string, unknown> => entry !== null);
            sideA = entries.find(entry => entry.side === "team_a") ?? null;
            sideB = entries.find(entry => entry.side === "team_b") ?? null;
            if (!sideA && !sideB && entries.length >= 2) {
                sideA = entries[0];
                sideB = entries[1];
            }
            legal = data.legal === true ? true : data.legal === false ? false : undefined;
            if (legal === undefined && sideA)
                legal = sideA.legal === true ? true : sideA.legal === false ? false : undefined;
            issues = stringList(data.issues);
            if (!issues.length && sideA) issues = stringList(sideA.issues);
            checksRaw = data.checks;
        }
        if (!sideA || !sideB || legal === undefined)
            throw new Error("trade_verdict source is missing the verdict structure — rerun the evaluation instead of substituting.");
        teams = [teamFromTradeCheck(sideA, sideB), teamFromTradeCheck(sideB, sideA)];
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

    const construction = tradeConstructionFromArgs(record.args, constructionSeasonEcho(data));

    return {
        kind: "trade_verdict",
        title: artifact.title,
        legal,
        ...(issues.length ? { issues } : {}),
        teams,
        checks: resolveChecks(checksRaw),
        evaluationTool: record.tool,
        sourceRef: artifact.ref,
        provenance: resolveProvenance(record, data),
        ...(construction ? { construction } : {})
    };
}

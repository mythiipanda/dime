import { Type } from "typebox";
import { Value } from "typebox/value";
import { objectValue, sourceResult, type SourceRecord } from "./python-tools.js";
import { field, resolveProvenance } from "./player-card.js";

export const capSummarySchema = Type.Object({
    kind: Type.Literal("cap_summary"),
    title: field,
    ref: field
}, { additionalProperties: false });

const EVALUATION_TOOLS = new Set(["get_cap_scenario"]);

function textOrNull(value: unknown): string | null {
    return typeof value === "string" && value.trim() ? value : null;
}

function numOrNull(value: unknown): number | null {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringList(value: unknown): string[] {
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function resolveSteps(value: unknown): { kind: string; detail: string; delta?: number; payroll?: number }[] {
    if (!Array.isArray(value)) return [];
    const steps: { kind: string; detail: string; delta?: number; payroll?: number }[] = [];
    for (const entry of value) {
        const step = objectValue(entry);
        if (!step) continue;
        const detail = textOrNull(step.detail);
        if (!detail) continue;
        const kind = textOrNull(step.kind) ?? "step";
        const delta = numOrNull(step.delta);
        const payroll = numOrNull(step.payroll);
        steps.push({
            kind,
            detail,
            ...(delta !== null ? { delta } : {}),
            ...(payroll !== null ? { payroll } : {})
        });
        if (steps.length >= 12) break;
    }
    return steps;
}

function resolveRestrictions(value: unknown): { threshold: string; rule: string }[] {
    if (!Array.isArray(value)) return [];
    const restrictions: { threshold: string; rule: string }[] = [];
    for (const entry of value) {
        const restriction = objectValue(entry);
        if (!restriction) continue;
        const threshold = textOrNull(restriction.threshold);
        const rule = textOrNull(restriction.rule);
        if (!threshold || !rule) continue;
        restrictions.push({ threshold, rule });
        if (restrictions.length >= 6) break;
    }
    return restrictions;
}

export function resolveCapSummary(artifact: Record<string, unknown>, getSource: (ref: string) => SourceRecord | undefined): Record<string, unknown> {
    if (!Value.Check(capSummarySchema, artifact))
        throw new Error("Invalid cap_summary: provide exactly title and ref — the ref of this run's get_cap_scenario result. The host resolves the cap position; never write payrolls, cap room, apron distances or flags yourself.");
    const record = getSource(artifact.ref as string);
    if (!record)
        throw new Error(`cap_summary source ref '${artifact.ref}' is not part of this run — emit it only after a cap scenario evaluation actually ran.`);
    if (!EVALUATION_TOOLS.has(record.tool))
        throw new Error(`cap_summary ref must come from get_cap_scenario — '${record.tool}' is not a cap scenario evaluation. The numbers must be the evaluator's, never a paraphrase of other data.`);
    const result = sourceResult(record);
    if (result.isError)
        throw new Error("cap_summary source evaluation errored — there is no cap position to show.");
    const data = objectValue(result.structuredContent.result);
    if (!data)
        throw new Error("cap_summary source has no structured result.");
    const summary = objectValue(data.summary);
    if (!summary)
        throw new Error("cap_summary source is missing the summary structure — rerun the evaluation instead of substituting.");
    const team = textOrNull(summary.team);
    const payrollBefore = numOrNull(summary.payroll_before);
    const payrollAfter = numOrNull(summary.payroll_after);
    if (!team || payrollBefore === null || payrollAfter === null)
        throw new Error("cap_summary source is missing the verdict structure — rerun the evaluation instead of substituting.");

    const out: Record<string, unknown> = {
        kind: "cap_summary",
        title: artifact.title,
        team,
        payrollBefore,
        payrollAfter,
        evaluationTool: record.tool,
        sourceRef: artifact.ref,
        provenance: resolveProvenance(record, data)
    };
    const season = textOrNull(summary.season);
    if (season) out.season = season;
    const delta = numOrNull(summary.delta);
    if (delta !== null) out.delta = delta;
    for (const [wire, key] of [
        ["cap_room", "capRoom"],
        ["cap_room_before", "capRoomBefore"],
        ["tax_room", "taxRoom"],
        ["room_apron1", "roomApron1"],
        ["room_apron2", "roomApron2"],
        ["team_salary_before", "teamSalaryBefore"],
        ["team_salary_after", "teamSalaryAfter"],
        ["cap_holds_after", "capHoldsAfter"],
        ["roster_charges_after", "rosterChargesAfter"]
    ] as const) {
        const value = numOrNull(summary[wire]);
        if (value !== null) out[key] = value;
    }
    const rosterBefore = numOrNull(summary.roster_before);
    if (rosterBefore !== null) out.rosterBefore = rosterBefore;
    const rosterAfter = numOrNull(summary.roster_after);
    if (rosterAfter !== null) out.rosterAfter = rosterAfter;
    if (summary.over_tax === true) out.overTax = true;
    if (summary.over_apron1 === true) out.overApron1 = true;
    if (summary.over_apron2 === true) out.overApron2 = true;
    const hardCap = textOrNull(summary.hard_cap);
    if (hardCap) out.hardCap = hardCap;
    const issues = stringList(data.issues);
    if (issues.length) out.issues = issues;
    const steps = resolveSteps(data.rows);
    if (steps.length) out.steps = steps;
    const restrictions = resolveRestrictions(data.restrictions);
    if (restrictions.length) out.restrictions = restrictions;
    return out;
}

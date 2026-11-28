import { Value } from "typebox/value";
import { capScenarioPayloadSchema, tradeScenarioPayloadSchema } from "./object-payloads.js";
import { objectValue } from "./python-tools.js";

function textOrNull(value: unknown): string | null {
    return typeof value === "string" && value.trim() ? value.trim() : null;
}

function parseJsonText(value: unknown): unknown {
    const text = textOrNull(value);
    if (!text) return undefined;
    try {
        return JSON.parse(text);
    } catch {
        return undefined;
    }
}

function parseAmount(raw: string): number | null {
    const cleaned = raw.replace(/[$,\s]/g, "");
    const millions = /^(\d+(?:\.\d+)?)m$/i.exec(cleaned);
    if (millions) return Math.round(parseFloat(millions[1]) * 1_000_000);
    if (/^\d+(?:\.\d+)?$/.test(cleaned)) {
        const value = parseFloat(cleaned);
        if (value > 0 && value < 1000) return Math.round(value * 1_000_000);
        return Math.round(value);
    }
    return null;
}

function splitNames(value: unknown): string[] {
    const text = textOrNull(value);
    if (!text) return [];
    return text.split(",").map((entry) => entry.trim()).filter((entry) => entry.length > 0);
}

export function tradeConstructionFromArgs(args: Record<string, unknown> | undefined, resultSeason?: string): Record<string, unknown> | undefined {
    if (!args) return undefined;
    const legs = parseJsonText(args.legs);
    if (!Array.isArray(legs) || legs.length === 0) return undefined;
    const season = textOrNull(args.season) ?? resultSeason;
    if (!season) return undefined;
    const payload = { legs, season, ...(args.tpe && typeof args.tpe === "string" && args.tpe.trim() ? {} : {}) };
    if (!Value.Check(tradeScenarioPayloadSchema, payload)) return undefined;
    return payload;
}

export function capConstructionFromArgs(args: Record<string, unknown> | undefined, resultSeason?: string): Record<string, unknown> | undefined {
    if (!args) return undefined;
    const team = textOrNull(args.team);
    if (!team) return undefined;
    const season = textOrNull(args.season) ?? resultSeason;
    if (!season) return undefined;
    const moves: Record<string, unknown>[] = [];
    const signingsText = textOrNull(args.signings);
    if (signingsText) {
        for (const entry of signingsText.split(",").map((part) => part.trim()).filter(Boolean)) {
            const named = /^(.+?)=(.+)$/.exec(entry);
            const label = named ? named[1].trim() : null;
            const amount = parseAmount(named ? named[2] : entry);
            if (amount === null) continue;
            moves.push({ kind: "signing", label: label ?? "Signing", amount });
        }
    }
    for (const player of splitNames(args.in_players))
        moves.push({ kind: "trade_in", player });
    for (const player of splitNames(args.trade_out_players))
        moves.push({ kind: "trade_out", player });
    for (const player of splitNames(args.waive_players)) {
        const move: Record<string, unknown> = { kind: "waive", player };
        if (args.stretch === true) move.stretch = true;
        moves.push(move);
    }
    if (moves.length === 0) return undefined;
    const payload: Record<string, unknown> = { team, season, moves };
    const waiverDate = textOrNull(args.waiver_date);
    if (waiverDate) payload.waiver_date = waiverDate;
    if (!Value.Check(capScenarioPayloadSchema, payload)) return undefined;
    return payload;
}

export function constructionSeasonEcho(data: unknown): string | undefined {
    const root = objectValue(data);
    const summary = objectValue(root?.summary);
    return textOrNull(summary?.season) ?? textOrNull(root?.season) ?? undefined;
}

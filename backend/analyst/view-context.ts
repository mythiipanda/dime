import { Type, type Static } from "typebox";

export const viewContextSchema = Type.Object({
    kind: Type.String({ minLength: 1, maxLength: 40, pattern: "^[a-z0-9_]+$" }),
    summary: Type.String({ minLength: 1, maxLength: 2000 }),
    entities: Type.Record(Type.String({ maxLength: 80 }), Type.Unknown()),
    refs: Type.Optional(Type.Object({
        object_id: Type.Optional(Type.String({ maxLength: 120 })),
        read_token: Type.Optional(Type.String({ maxLength: 120 })),
    }, { additionalProperties: false })),
}, { additionalProperties: false });
export type ViewContext = Static<typeof viewContextSchema>;

export function serializeViewContext(context: ViewContext, question: string): string {
    const payload = JSON.stringify({
        summary: context.summary,
        entities: context.entities,
        ...(context.refs ? { refs: context.refs } : {}),
    });
    return `<dime-context kind="${context.kind}">\n${payload}\n</dime-context>\n\n${question}`;
}

export function withViewContext(input: { q: string; context?: ViewContext | null }): string {
    if (!input.context)
        return input.q;
    if (serializeViewContext(input.context, "").length <= CONTEXT_ENVELOPE_MAX_CHARS)
        return serializeViewContext(input.context, input.q);
    let entities = input.context.entities;
    for (const key of CONTEXT_REDUCTION_KEYS) {
        entities = stripKeyDeep(entities, key) as Record<string, unknown>;
        const reduced: ViewContext = { ...input.context, entities };
        if (serializeViewContext(reduced, "").length <= CONTEXT_ENVELOPE_MAX_CHARS)
            return serializeViewContext(reduced, input.q);
    }
    return `${input.q}\n\n(the workbench context was too large to attach to this question)`;
}

export const CONTEXT_ENVELOPE_MAX_CHARS = 8192;
const CONTEXT_REDUCTION_KEYS = ["picks", "issues", "cap_hold_details", "payroll_after"];

function stripKeyDeep(value: unknown, key: string): unknown {
    if (Array.isArray(value))
        return value.map((item) => stripKeyDeep(item, key));
    if (value && typeof value === "object") {
        const out: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
            if (k === key)
                continue;
            out[k] = stripKeyDeep(v, key);
        }
        return out;
    }
    return value;
}

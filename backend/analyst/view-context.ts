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
    const serialized = serializeViewContext(input.context, input.q);
    return serialized.length <= 8000 ? serialized : input.q;
}

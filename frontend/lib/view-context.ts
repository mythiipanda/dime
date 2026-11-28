export type ViewContext = {
  kind: string;
  summary: string;
  entities: Record<string, unknown>;
  refs?: { object_id?: string; read_token?: string };
};

const OPEN = /^<dime-context kind="([a-z0-9_]+)">\n/;
const CLOSE = "\n</dime-context>\n\n";

export function serializeViewContext(context: ViewContext, question: string): string {
  const payload = JSON.stringify({ summary: context.summary, entities: context.entities, ...(context.refs ? { refs: context.refs } : {}) });
  return `<dime-context kind="${context.kind}">\n${payload}${CLOSE}${question}`;
}

export function splitViewContext(wire: string): { context: ViewContext | null; text: string } {
  const open = wire.match(OPEN);
  if (!open) return { context: null, text: wire };
  const closeAt = wire.indexOf(CLOSE, open[0].length);
  if (closeAt === -1) return { context: null, text: wire };
  try {
    const payload = JSON.parse(wire.slice(open[0].length, closeAt)) as { summary?: unknown; entities?: unknown; refs?: unknown };
    if (typeof payload.summary !== "string" || typeof payload.entities !== "object" || payload.entities === null)
      return { context: null, text: wire };
    return {
      context: { kind: open[1], summary: payload.summary, entities: payload.entities as Record<string, unknown>, ...(payload.refs && typeof payload.refs === "object" ? { refs: payload.refs as ViewContext["refs"] } : {}) },
      text: wire.slice(closeAt + CLOSE.length),
    };
  } catch {
    return { context: null, text: wire };
  }
}

import type { ToolCall } from "./chat";

const callSeq = new WeakMap<object, number>();
let nextCallSeq = 1;

export function callKey(c: ToolCall): string {
  if (c.id) return c.id;
  let n = callSeq.get(c);
  if (n === undefined) {
    n = nextCallSeq++;
    callSeq.set(c, n);
  }
  return `${c.name}@${c.startedAt ?? "?"}#${n}`;
}

export function groupKey(name: string, agent: string | undefined, first: ToolCall): string {
  return `${name}@${agent ?? ""}:${callKey(first)}`;
}

import { postChatStream } from "../api";
import { asResolvedArtifacts, deriveArtifacts } from "./artifacts";
import {
  failureCopy,
  publishableArgumentLines,
  thinkingLabelFor,
  toolLabelFor,
} from "./labels";
import { parseCarry } from "./provenance";
import {
  asNumber,
  asRecord,
  asString,
  type DimeStreamCallbacks,
  type DimeStreamEvent,
  type FailureEvent,
  type StreamSnapshot,
  type ToolActivityEvent,
  type ToolActivityStatus,
} from "./types";

function emptySnapshot(): StreamSnapshot {
  return {
    text: "",
    thinking: [],
    tools: [],
    artifacts: [],
    suggestions: [],
    carry: null,
    failed: null,
    done: false,
  };
}

const MAX_THINKING_ROWS = 12;
const MAX_TOOLS = 24;

type EventReducer = (d: Record<string, unknown>) => DimeStreamEvent[];

const EVENT_REDUCERS: Record<string, EventReducer> = {
  token: (d) => {
    const text = asString(d.text);
    return text ? [{ type: "text_delta", text }] : [];
  },
  status: (d) => {
    const label = asString(d.text);
    return label ? [{ type: "thinking", label }] : [];
  },
  thought_stream: (d) => [{ type: "thinking", label: thinkingLabelFor(d.node) }],
  node_update: (d) =>
    d.status === "running" ? [{ type: "thinking", label: thinkingLabelFor(d.node) }] : [],
  tool_call: (d) => {
    const name = asString(d.name) || "tool";
    return [
      {
        type: "tool_activity",
        id: asString(d.event_id) || null,
        name,
        label: toolLabelFor(name, "running"),
        status: "running",
        args: publishableArgumentLines(d.data),
      },
    ];
  },
  tool_result: (d) => {
    const name = asString(d.name) || "tool";
    const status: ToolActivityStatus = d.status === "fail" ? "fail" : "ok";
    return [
      {
        type: "tool_activity",
        id: asString(d.event_id) || null,
        name,
        label: toolLabelFor(name, status),
        status,
        rows: asNumber(d.rows),
        ms: asNumber(d.ms),
        error: status === "fail" ? asString(d.error) || "Tool failed" : undefined,
      },
    ];
  },
  custom_data: (d) => {
    const derived = deriveArtifacts(d.tables);
    const resolved = asResolvedArtifacts(d.artifacts);
    return [...derived, ...resolved].map((artifact) => ({
      type: "artifact",
      artifact,
    }));
  },
  final_answer: (d) => {
    const submission = asRecord(asRecord(d.carry).submission);
    return [{ type: "final", text: asString(d.text), carry: parseCarry(d.carry),
      ...(Array.isArray(submission.artifacts) ? { artifacts: asResolvedArtifacts(submission.artifacts) } : {}),
    }];
  },
  failure: (d) => {
    const kind = asString(d.kind) || "execution_failure";
    return [
      {
        type: "failure",
        kind,
        message: asString(d.message) || failureCopy(kind).body,
      },
    ];
  },
  error: (d) => {
    const message = asString(d.message);
    const kind = /rate limit/i.test(message) ? "rate_limited" : "execution_failure";
    return [{ type: "failure", kind, message: message || failureCopy(kind).body }];
  },
};

export function reduceBackendEvent(type: string, data: unknown): DimeStreamEvent[] {
  const reducer = EVENT_REDUCERS[type];
  return reducer ? reducer(asRecord(data)) : [];
}

type FailureAuthority = "typed" | "fallback";

function failureAuthorityFor(type: string): FailureAuthority | null {
  if (type === "failure") return "typed";
  if (type === "error") return "fallback";
  return null;
}

export class DimeStream {
  private snap = emptySnapshot();
  private seq = 0;
  private hasTypedFailure = false;

  snapshot(): StreamSnapshot {
    return {
      ...this.snap,
      thinking: [...this.snap.thinking],
      tools: this.snap.tools.map((t) => ({ ...t })),
      artifacts: [...this.snap.artifacts],
      suggestions: [...this.snap.suggestions],
      carry: this.snap.carry ? { ...this.snap.carry } : null,
      failed: this.snap.failed ? { ...this.snap.failed } : null,
    };
  }

  handle(type: string, data: unknown): void {
    const authority = failureAuthorityFor(type);
    for (const event of reduceBackendEvent(type, data)) {
      this.apply(event, authority);
    }
    if (type === "suggestions") {
      const items = asRecord(data).items;
      if (Array.isArray(items)) {
        this.snap.suggestions = items
          .filter((item): item is string => typeof item === "string" && item.trim() !== "")
          .slice(0, 8);
      }
    }
  }

  finish(): void {
    this.snap.done = true;
  }

  fail(kind: string, message: string): void {
    this.recordFailure({ type: "failure", kind, message }, "fallback");
  }

  private recordFailure(
    event: FailureEvent,
    authority: FailureAuthority | null,
  ): void {
    if (authority === "typed") {
      this.hasTypedFailure = true;
    } else if (this.hasTypedFailure) {
      return;
    }
    this.snap.failed = { kind: event.kind, message: event.message };
  }

  private applyToolActivity(event: ToolActivityEvent): void {
    const tools = this.snap.tools;
    let idx = event.id !== null ? tools.findIndex((t) => t.key === event.id) : -1;
    if (idx < 0 && event.id === null && event.status !== "running") {
      for (let i = tools.length - 1; i >= 0; i -= 1) {
        if (tools[i].status === "running" && tools[i].name === event.name) {
          idx = i;
          break;
        }
      }
    }
    if (idx >= 0) {
      const next = [...tools];
      next[idx] = {
        ...next[idx],
        label: event.label,
        status: event.status,
        rows: event.rows ?? next[idx].rows,
        ms: event.ms ?? next[idx].ms,
        args: event.args ?? next[idx].args,
        error: event.error ?? next[idx].error,
      };
      this.snap.tools = next;
      return;
    }
    this.seq += 1;
    this.snap.tools = [
      ...tools,
      {
        key: event.id ?? `local:${this.seq}`,
        name: event.name,
        label: event.label,
        status: event.status,
        rows: event.rows,
        ms: event.ms,
        args: event.args,
        error: event.error,
      },
    ].slice(-MAX_TOOLS);
  }

  private apply(
    event: DimeStreamEvent,
    authority: FailureAuthority | null,
  ): void {
    switch (event.type) {
      case "text_delta":
        this.snap.text += event.text;
        break;
      case "thinking": {
        const last = this.snap.thinking[this.snap.thinking.length - 1];
        if (!last || last.label !== event.label) {
          this.snap.thinking = [
            ...this.snap.thinking,
            { label: event.label, detail: event.detail },
          ].slice(-MAX_THINKING_ROWS);
        }
        break;
      }
      case "tool_activity":
        this.applyToolActivity(event);
        break;
      case "artifact":
        this.snap.artifacts = [...this.snap.artifacts, event.artifact];
        break;
      case "final":
        this.snap.text = event.text;
        this.snap.carry = event.carry;
        if (event.artifacts) this.snap.artifacts = event.artifacts;
        break;
      case "failure":
        this.recordFailure(event, authority);
        break;
    }
  }
}

export function streamDimeChat(
  q: string,
  callbacks: DimeStreamCallbacks,
  opts?: { signal?: AbortSignal; model?: string | null; thread?: string; replay?: string | null; context?: unknown; turn?: number },
): void {
  const stream = new DimeStream();
  let settled = false;
  const emit = () => callbacks.onUpdate(stream.snapshot());
  const handlers: Parameters<typeof postChatStream>[2] =
    {
      onEvent: (type, data) => {
        if (settled) return;
        stream.handle(type, data);
        emit();
      },
      onDone: () => {
        if (settled) return;
        settled = true;
        stream.finish();
        callbacks.onDone(stream.snapshot());
      },
      onError: (message) => {
        if (settled) return;
        settled = true;
        stream.fail("connection", message);
        stream.finish();
        callbacks.onError(stream.snapshot(), message);
      },
    };
  if (process.env.NODE_ENV === "development" && opts?.replay) {
    void import("../replay").then(({ replayStream }) => replayStream(opts.replay!, handlers, opts.signal, opts.turn ?? 0));
    return;
  }
  void postChatStream(
    q,
    opts?.model ?? null,
    handlers,
    opts?.signal,
    opts?.thread ?? null,
    opts?.context ? { context: opts.context } : undefined,
  );
}

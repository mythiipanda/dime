import { Type } from "typebox";
import { defineTool, type ToolDefinition } from "@earendil-works/pi-coding-agent";

export type RunStatusTracker = {
    startedAt: number;
    budgetMs?: number;
    toolCalls: number;
    sourceCount: () => number;
    submitted: boolean;
};

const runStatusSchema = Type.Object({
    ok: Type.Boolean(),
    elapsed_ms: Type.Integer({ minimum: 0 }),
    budget_ms: Type.Optional(Type.Number({ minimum: 1 })),
    budget_remaining_ms: Type.Optional(Type.Integer({ minimum: 0 })),
    tool_calls: Type.Integer({ minimum: 0 }),
    source_count: Type.Integer({ minimum: 0 }),
    submitted: Type.Boolean(),
}, { additionalProperties: false });

export function countToolCall<T extends ToolDefinition>(tool: T, tracker: RunStatusTracker): T {
    const execute = tool.execute as unknown as (...args: unknown[]) => Promise<unknown>;
    return {
        ...tool,
        execute: async (...args: unknown[]) => {
            tracker.toolCalls += 1;
            return execute(...args);
        },
    } as T;
}

export function createRunStatusTool(tracker: RunStatusTracker) {
    return defineTool({
        name: "run_status",
        label: "Run status",
        description: "Report elapsed time, remaining host budget, tool-call count, source count, and whether submit_answer has been called. Advisory only; use it to pace long analyses and checkpoint partial work.",
        parameters: Type.Object({}, { additionalProperties: false }),
        outputSchema: runStatusSchema,
        async execute() {
            const elapsedMs = Math.max(0, Math.round(Date.now() - tracker.startedAt));
            const budgetMs = tracker.budgetMs === undefined ? undefined : Math.max(1, Math.round(tracker.budgetMs));
            const status: {
                ok: boolean;
                elapsed_ms: number;
                budget_ms?: number;
                budget_remaining_ms?: number;
                tool_calls: number;
                source_count: number;
                submitted: boolean;
            } = {
                ok: true,
                elapsed_ms: elapsedMs,
                tool_calls: tracker.toolCalls,
                source_count: tracker.sourceCount(),
                submitted: tracker.submitted,
            };
            if (budgetMs !== undefined) {
                status.budget_ms = budgetMs;
                status.budget_remaining_ms = Math.max(0, Math.round(budgetMs - elapsedMs));
            }
            return {
                content: [{ type: "text", text: JSON.stringify(status) }],
                details: undefined,
                structuredContent: status,
            };
        },
    });
}

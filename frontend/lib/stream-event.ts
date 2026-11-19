import { type AiMessage, type NodeName, type ToolResult, emptyNode, isFailureFinal } from "./chat";
import type { RunInfo } from "./api";
import { activityRecordFromEvent, mergeActivityRecord } from "./activity";

export function applyEvent(ai: AiMessage, type: string, data: unknown): AiMessage {
  const d = data as Record<string, unknown>;
  const next: AiMessage = {
    ...ai,
    nodes: { ...ai.nodes },
  };
  const touch = (n: NodeName) => {
    if (!next.nodes[n]) next.nodes[n] = emptyNode();
    return next.nodes[n]!;
  };
  const activity = activityRecordFromEvent(type, d, next.activity?.length || 0);
  if (activity) next.activity = mergeActivityRecord(next.activity || [], activity);
  if (type === "node_update") {
    const node = d.node as NodeName;
    if (node === "entry") return next;
    const status = d.status;
    touch(node).status =
      status === "complete" || status === "error" ? status : "running";
  } else if (type === "thought_token") {
    if (!next.thoughtStarted) next.thoughtStarted = Date.now();
    const node = touch(d.node as NodeName);
    node.liveThought = (node.liveThought || "") + String(d.text || "");
    if (d.agent && !node.liveThoughtAgent) node.liveThoughtAgent = String(d.agent);
  } else if (type === "thought_stream") {
    if (!next.thoughtStarted) next.thoughtStarted = Date.now();
    touch(d.node as NodeName).thoughts.push(String(d.text || ""));
  } else if (type === "tool_call") {
    const node = touch(d.node as NodeName);
    const id =
      typeof d.correlation_id === "string"
        ? d.correlation_id
        : typeof d.event_id === "string"
          ? d.event_id
          : undefined;
    node.toolCalls.push({
      id,
      name: String(d.name || ""),
      args: (d.args as Record<string, unknown>) || {},
      label: d.label as string | undefined,
      summary: d.summary as string | undefined,
      agent: d.agent as string | undefined,
      status: "running",
      startedAt: Date.now(),
    });
  } else if (type === "tool_result") {
    const node = touch(d.node as NodeName);
    const name = String(d.name || "");
    const agent = d.agent as string | undefined;
    const id =
      typeof d.correlation_id === "string"
        ? d.correlation_id
        : typeof d.event_id === "string"
          ? d.event_id
          : undefined;
    for (let i = 0; i < node.toolCalls.length; i++) {
      const c = node.toolCalls[i];
      if (c.status !== "running") continue;
      if (id && c.id) {
        if (c.id !== id) continue;
      } else if (!(c.name === name && c.agent === agent)) {
        continue;
      }
        c.status = d.status === "ok" ? "ok" : "fail";
        c.endedAt = Date.now();
        if (typeof d.rows === "number") c.rows = d.rows;
        if (typeof d.ms === "number") c.ms = d.ms;
        if (d.error) c.error = String(d.error);
        if (d.summary) c.summary = String(d.summary);
        if (typeof d.sql === "string" && d.sql.trim()) c.sql = d.sql;
        break;
    }
  } else if (type === "custom_data") {
    const node = touch(d.node as NodeName);
    const tables = (d.tables as unknown[]) || [];
    node.tables.push(
      ...(tables as {
        tool: string;
        rows?: unknown;
        meta?: { source?: string; fetched_at?: string };
      }[]),
    );
    const unverified = d.unverified_numbers as string[] | undefined;
    if (unverified && unverified.length) {
      next.caution = [...(next.caution || []), ...unverified];
    }
  } else if (type === "token") {
    next.text = (next.text || "") + String(d.text || "");
    next.streaming = true;
  } else if (type === "final_answer") {
    next.text = String(d.text || "");
    next.streaming = false;
    if (d.carry && typeof d.carry === "object") {
      next.carry = d.carry as AiMessage["carry"];
    }
    
    
    
    
    
    
    







    if (!isFailureFinal(next.text, d.carry)) {
      next.error = undefined;
    }
  } else if (type === "suggestions") {
    const items = (d.items as string[]) || [];
    next.suggestions = items;
  } else if (type === "error") {
    next.error = String(d.message || "error");
  } else if (type === "graph_end") {
    next.done = true;
    next.streaming = false;
    if (next.thoughtStarted && !next.thoughtMs) {
      next.thoughtMs = Date.now() - next.thoughtStarted;
    }
    for (const n of Object.keys(next.nodes) as NodeName[]) {
      if (next.nodes[n]!.status === "running") next.nodes[n]!.status = "complete";
    }
  }
  return next;
}


export function aiFromRun(r: RunInfo): AiMessage {
  const tables: ToolResult[] = [];
  if (Array.isArray(r.tables)) {
    for (const t of r.tables) {
      if (
        typeof t === "object" &&
        t !== null &&
        
        


        (typeof (t as { tool?: unknown }).tool === "string" ||
          typeof (t as { kind?: unknown }).kind === "string" ||
          Array.isArray((t as { rows?: unknown }).rows))
      ) {
        tables.push(t as ToolResult);
      }
    }
  }
  return {
    text: typeof r.answer === "string" ? r.answer : "",
    nodes: tables.length
      ? {
          analytics: {
            status: "complete",
            thoughts: [],
            toolCalls: [],
            toolResults: [],
            tables,
          },
        }
      : {},
    done: true,
    suggestions: Array.isArray(r.suggestions) ? r.suggestions : [],
  };
}


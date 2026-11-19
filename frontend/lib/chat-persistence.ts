import { appendCachedRun, getClientId, getRuns, type RunInfo } from "./api";
import { BACKEND } from "./chat";
import { DimeStream, type StreamSnapshot } from "./dime-stream";

type PersistedRun = RunInfo & { snapshot?: StreamSnapshot };

export function cacheChatRun(thread: string, question: string, snapshot: StreamSnapshot): void {
  const run: PersistedRun = {
    id: snapshot.carry?.runId,
    question, answer: snapshot.text, tables: [], suggestions: snapshot.suggestions,
    created_at: new Date().toISOString(), snapshot,
  };
  appendCachedRun(thread, run);
}

export async function loadChatRuns(thread: string): Promise<{ question: string; snapshot: StreamSnapshot; createdAt: number }[]> {
  const runs = await getRuns(thread);
  return Promise.all(runs.map(async (run: PersistedRun) => {
    const createdAt = Date.parse(run.created_at);
    if (run.snapshot) return { question: run.question, snapshot: run.snapshot, createdAt };
    let carry: unknown;
    if (run.id) {
      try {
        const url = new URL(`${BACKEND}/api/v2/runs/${encodeURIComponent(run.id)}/sources`, window.location.origin);
        url.searchParams.set("client", getClientId());
        url.searchParams.set("thread", thread);
        const response = await fetch(url);
        if (response.ok) {
          const source = await response.json();
          carry = { run_id: run.id, source_refs: source.source_refs ?? source.sources?.map((item: { ref: string }) => item.ref), sources: source.sources, submission: source.submission };
        }
      } catch {  }
    }
    const stream = new DimeStream();
    stream.handle("custom_data", { tables: run.tables });
    stream.handle("final_answer", { text: run.answer, tables: run.tables, suggestions: run.suggestions, carry });
    stream.handle("suggestions", { items: run.suggestions });
    stream.finish();
    return { question: run.question, snapshot: stream.snapshot(), createdAt };
  }));
}

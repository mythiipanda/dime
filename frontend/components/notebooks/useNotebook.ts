"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { NotebookError, getNotebook, saveNotebook } from "../../lib/notebook-api";
import type { Notebook, SaveState } from "../../lib/notebooks";

export function useNotebook(id: string) {
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [state, setState] = useState<SaveState>("saved");
  const [error, setError] = useState("");
  const [generation, setGeneration] = useState(0);
  const [pulse, setPulse] = useState(0);
  const current = useRef<Notebook | null>(null), version = useRef(1), revision = useRef(0), saved = useRef(0);
  const busy = useRef<Promise<boolean> | null>(null), conflict = useRef(false), active = useRef(true);
  useEffect(() => { active.current = true; const controller = new AbortController(); getNotebook(id, controller.signal).then((doc) => { if (controller.signal.aborted) return; current.current = doc; version.current = doc.version; setNotebook(doc); }).catch((e) => { if (!controller.signal.aborted) setError(e.message); }); return () => { active.current = false; controller.abort(); }; }, [id]);
  const edit = useCallback((change: (doc: Notebook) => Notebook) => {
    if (!current.current || conflict.current) return;
    current.current = change(current.current); revision.current += 1; setNotebook(current.current); setGeneration(revision.current); setState("dirty");
  }, []);
  const persist = useCallback(async (): Promise<boolean> => {
    if (busy.current) { const ok = await busy.current; return ok && saved.current !== revision.current ? persist() : ok; }
    if (conflict.current || !current.current) return false;
    if (saved.current === revision.current) return true;
    const snapshot = { ...current.current, version: version.current }, at = revision.current;
    setState("saving");
    const operation = (async () => {
      try {
        const result = await saveNotebook(snapshot);
        version.current = result.version; saved.current = at;
        current.current = { ...current.current!, version: result.version, updated_at: result.updated_at };
        if (active.current) { setNotebook(current.current); setState(at === revision.current ? "saved" : "dirty"); setError(""); if (at !== revision.current) setPulse((n) => n + 1); }
        return true;
      } catch (e) {
        const failed = e as Error;
        conflict.current = failed instanceof NotebookError && failed.status === 409;
        if (active.current) { setState(conflict.current ? "conflict" : "error"); setError(failed.message); }
        return false;
      } finally { busy.current = null; }
    })();
    busy.current = operation; return operation;
  }, []);
  useEffect(() => { if (!generation) return; const timer = setTimeout(() => { void persist(); }, 650); return () => clearTimeout(timer); }, [generation, pulse, persist]);
  useEffect(() => { const warn = (event: BeforeUnloadEvent) => { if (revision.current !== saved.current) event.preventDefault(); }; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, []);
  return { notebook, state, error, edit, persist, current };
}

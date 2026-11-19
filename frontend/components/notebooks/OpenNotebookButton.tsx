"use client";

import { useState } from "react";
import { Book, Xmark } from "iconoir-react";
import { createNotebook } from "../../lib/notebook-api";
import type { NotebookDraft } from "../../lib/notebooks";
import { Button } from "../ds/Button";

export function OpenNotebookButton({ seed, onOpen, disabled = false }: { seed: () => NotebookDraft; onOpen: (id: string) => void; disabled?: boolean }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  return <>
    <Button size="xs" variant="quiet" disabled={busy || disabled} onClick={async () => {
      setBusy(true); setError("");
      try { const notebook = await createNotebook(seed()); onOpen(notebook.id); }
      catch (e) { setError(`Could not create notebook. ${e instanceof TypeError ? "The backend is unavailable. Check that it is running and try again." : e instanceof Error ? e.message : "Please try again."}`); }
      finally { setBusy(false); }
    }}><Book width={13} />{busy ? "Creating notebook…" : "Open as notebook"}</Button>
    {error && <div role="alert" className="fixed bottom-6 right-6 z-50 flex max-w-sm items-start gap-4 rounded-xl border border-line bg-surface p-4 text-[12px] leading-relaxed text-ink shadow-overlay"><div><strong className="block text-red">Notebook not created</strong><p className="mt-1 text-ink-2">{error}</p></div><button className="icon-button shrink-0" aria-label="Dismiss notebook error" onClick={() => setError("")}><Xmark width={14} /></button></div>}
  </>;
}

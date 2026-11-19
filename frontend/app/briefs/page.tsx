"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import MatchupPreviewView, { parsePreview } from "../../components/MatchupPreviewView";
import { getRevision } from "../../lib/api";
import { Book } from "iconoir-react";
import { Button } from "../../components/ds/Button";
import { Chip } from "../../components/ds/Chip";
import { PageHeader, Panel } from "../../components/ds/Panel";
import EmptyState from "../../components/EmptyState";
import { SavedBoards } from "../../components/SavedBoards";
import {
  briefStale,
  getBrief,
  listBriefs,
  packHashOf,
  removeBrief,
  rerunBrief,
  type BriefDoc,
} from "../../lib/briefs";

function briefTitle(doc: BriefDoc): string {
  return doc.title || doc.question.slice(0, 80);
}

export default function BriefsPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<BriefDoc[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [packHash, setPackHash] = useState<string | null>(null);

  useEffect(() => {
    setDocs(listBriefs());
    let live = true;
    getRevision()
      .then((data) => {
        if (live) setPackHash(packHashOf(data));
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  const refresh = () => setDocs(listBriefs());
  const active = activeId ? getBrief(activeId) : null;

  const remove = (id: string) => {
    removeBrief(id);
    if (activeId === id) setActiveId(null);
    refresh();
  };

  const rerun = (doc: BriefDoc) => {
    window.location.assign(rerunBrief(doc));
  };


  return <div className="mx-auto max-w-6xl px-6 py-10 lg:px-10">
    <PageHeader eyebrow="Your working library" title="Library" description="Your boards and cited briefs, kept close. Return to a shortlist, revisit its evidence, or start a new line of inquiry." actions={<Chip>{docs.length} {docs.length === 1 ? "brief" : "briefs"}</Chip>} />
    <div className="mb-8"><SavedBoards onOpen={(id) => router.push(`/?tab=boards&board=${encodeURIComponent(id)}`)} /></div>
    {!docs.length ? <Panel title="Build a library of decisions"><EmptyState icon={<Book width={28} height={28} />} title="No briefs yet" description="Save one from a matchup answer in chat. Your saved analysis and its source context will appear here." actionLabel="Ask Dime" onAction={() => window.location.assign("/?tab=chat")} /></Panel> : <div className="grid items-start gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="space-y-3" aria-label="Saved briefs">{docs.map((doc) => <div key={doc.id} className="rounded-xl border border-line bg-surface p-3">
        <button type="button" onClick={() => setActiveId(doc.id)} aria-pressed={activeId === doc.id} className={"w-full rounded-lg p-2 text-left transition-colors hover:bg-hover " + (activeId === doc.id ? "bg-hover-2" : "")}><p className="text-[13px] font-medium leading-relaxed">{briefTitle(doc)}</p><p className="mt-2 text-[11px] text-ink-3">{doc.createdAt.slice(0, 10)}</p></button>
        <div className="mt-2 flex gap-1 border-t border-line pt-2"><Button size="xs" variant="quiet" onClick={() => rerun(doc)}>Re-run</Button><Button size="xs" variant="quiet" className="text-ink-3 hover:text-red" onClick={() => remove(doc.id)}>Delete</Button></div>
      </div>)}</aside>
      <Panel title={active ? briefTitle(active) : "Reading room"} description={active ? "Saved evidence · " + active.createdAt.slice(0, 10) : "Your brief, its sources, and the details behind the decision."}>
        {!active ? <EmptyState icon={<Book width={24} height={24} />} title="Pick a brief to read it." description="Select a saved brief from your library." /> : parsePreview(active.rows) ? <>{briefStale(active.packHash, packHash) && <p role="status" className="mb-4 rounded-lg border border-line bg-orange-tint px-3 py-2 text-[12px] text-orange">This brief may be out of date.</p>}<MatchupPreviewView rows={active.rows} meta={active.meta ?? undefined} /></> : <EmptyState title="This brief did not load." description="The saved content is unavailable. Re-run the brief to refresh it." />}
      </Panel>
    </div>}
  </div>;
}

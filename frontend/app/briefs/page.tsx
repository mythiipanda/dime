"use client";

import { useEffect, useRef, useState } from "react";
import MatchupPreviewView, { parsePreview } from "../../components/MatchupPreviewView";
import { getRevision } from "../../lib/api";
import {
  briefStale,
  docRev,
  getBrief,
  listBriefs,
  packHashOf,
  removeBrief,
  rerunBrief,
  updateBrief,
  type BriefDoc,
} from "../../lib/briefs";

function briefTitle(doc: BriefDoc): string {
  return doc.title || doc.question.slice(0, 80);
}

function BriefEditor({ doc, onSaved }: { doc: BriefDoc; onSaved: () => void }) {
  const [title, setTitle] = useState(doc.title);
  const [question, setQuestion] = useState(doc.question);
  const [conflict, setConflict] = useState(false);
  const saved = useRef({ title: doc.title, question: doc.question, rev: docRev(doc) });

  useEffect(() => {
    if (title === saved.current.title && question === saved.current.question) return;
    const id = setTimeout(() => {
      const result = updateBrief(doc.id, { title, question }, saved.current.rev);
      if (result.ok) {
        saved.current = { title, question, rev: docRev(result.doc) };
        setConflict(false);
        onSaved();
      } else {
        setConflict(true);
      }
    }, 600);
    return () => clearTimeout(id);
  }, [title, question, doc.id, onSaved]);

  const reload = () => {
    const current = getBrief(doc.id);
    if (!current) return;
    setTitle(current.title);
    setQuestion(current.question);
    saved.current = { title: current.title, question: current.question, rev: docRev(current) };
    setConflict(false);
    onSaved();
  };

  const field = {
    display: "block",
    width: "100%",
    border: "1px solid var(--color-stone-border)",
    borderRadius: 8,
    padding: "6px 10px",
    fontSize: 13,
    color: "var(--color-ink-black)",
    background: "var(--color-pure-white)",
    marginBottom: 8,
  } as const;

  return (
    <div style={{ marginBottom: 12 }}>
      <input
        className="field"
        style={field}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        aria-label="Brief title"
      />
      <input
        className="field"
        style={field}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        aria-label="Brief question"
      />
      {conflict ? (
        <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 4 }}>
          Brief changed elsewhere. Your edits kept.{" "}
          <button
            type="button"
            onClick={reload}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--color-warm-gray)",
              textDecoration: "underline",
            }}
          >
            Reload saved
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default function BriefsPage() {
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

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 20px 80px" }}>
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: ".08em",
          textTransform: "uppercase",
          color: "var(--color-ash-gray)",
        }}
      >
        Briefs
      </div>
      <h1 className="display" style={{ fontSize: 24, margin: "4px 0 6px" }}>
        Saved briefs
      </h1>
      <div style={{ fontSize: 13, color: "var(--color-warm-gray)", marginBottom: 16 }}>
        Cited matchup briefs, kept where you can find them.
      </div>
      {!docs.length ? (
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
          No briefs yet. Save one from a matchup answer in chat.
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 20 }}>
          <div>
            {docs.map((doc) => (
              <div key={doc.id} style={{ marginBottom: 4 }}>
                <button
                  type="button"
                  onClick={() => setActiveId(doc.id)}
                  aria-pressed={activeId === doc.id}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    background:
                      activeId === doc.id
                        ? "var(--color-bg-selected)"
                        : "transparent",
                    border: "1px solid var(--color-stone-border)",
                    borderRadius: 10,
                    padding: "8px 12px",
                    cursor: "pointer",
                  }}
                >
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 500,
                      color: "var(--color-ink-black)",
                    }}
                  >
                    {briefTitle(doc)}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--color-ash-gray)" }}>
                    {doc.createdAt.slice(0, 10)}
                  </div>
                </button>
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  <button
                    type="button"
                    onClick={() => rerun(doc)}
                    style={{
                      background: "none",
                      border: "none",
                      padding: 0,
                      cursor: "pointer",
                      fontSize: 12,
                      fontWeight: 500,
                      color: "var(--color-warm-gray)",
                    }}
                  >
                    Re-run
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(doc.id)}
                    style={{
                      background: "none",
                      border: "none",
                      padding: 0,
                      cursor: "pointer",
                      fontSize: 12,
                      fontWeight: 500,
                      color: "var(--color-warm-gray)",
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div>
            {!active ? (
              <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
                Pick a brief to read it.
              </div>
            ) : parsePreview(active.rows) ? (
              <>
                {briefStale(active.packHash, packHash) ? (
                  <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginBottom: 8 }}>
                    This brief may be out of date.
                  </div>
                ) : null}
                <BriefEditor key={active.id} doc={active} onSaved={refresh} />
                <MatchupPreviewView rows={active.rows} meta={active.meta ?? undefined} />
              </>
            ) : (
              <div style={{ fontSize: 13, color: "var(--color-warm-gray)" }}>
                This brief did not load.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

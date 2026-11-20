"use client";

import { useEffect, useState } from "react";
import { ViewGrid, ArrowUpRight } from "iconoir-react";
import { Button } from "./ds/Button";
import { TextField } from "./ds/TextField";
import { listBoards, saveBoard, deleteBoard, boardsArePersistent, type Board } from "../lib/boards";

export function SavedBoards({ onOpen }: { onOpen: (id: string) => void }) {
  const [boards, setBoards] = useState<Board[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  useEffect(() => { const refresh = () => setBoards(listBoards()); refresh(); window.addEventListener("storage", refresh); window.addEventListener("dime:boards", refresh); return () => { window.removeEventListener("storage", refresh); window.removeEventListener("dime:boards", refresh); }; }, []);
  return <section aria-label="Saved boards">
    <div className="mb-4 flex items-center justify-between"><h2 className="text-[13px] font-medium">Your boards <span className="ml-2 text-[11px] font-normal text-ink-3">{boards.length}</span></h2><span className="text-[11px] text-ink-3">{boardsArePersistent() ? "Saved on this device" : "Session only · storage unavailable"}</span></div>
    {!boards.length ? <div className="rounded-xl border border-dashed border-line-strong px-6 py-8 text-center"><ViewGrid width={22} height={22} className="mx-auto mb-3 text-ink-3" /><p className="text-[12px] text-ink-2">Your next shortlist starts here.</p><p className="mt-1.5 text-[11px] text-ink-3">Choose a template or start with a blank board. Changes save automatically.</p></div> : <div className="space-y-2">{boards.map((board) => <article key={board.id} className="flex flex-wrap items-center gap-4 rounded-xl border border-line bg-surface px-4 py-3">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-line bg-inset text-ink-3"><ViewGrid width={16} height={16} /></span>
      <div className="min-w-0 flex-1">{editing === board.id ? <form onSubmit={(e) => { e.preventDefault(); saveBoard({ ...board, title }); setEditing(null); }} className="flex gap-2"><TextField autoFocus aria-label="Board name" value={title} maxLength={160} onChange={(e) => setTitle(e.target.value)} /><Button size="sm" type="submit">Save</Button><Button size="sm" variant="quiet" onClick={() => setEditing(null)}>Cancel</Button></form> : <button className="max-w-full truncate text-left text-[13px] font-medium hover:underline" onClick={() => onOpen(board.id)}>{board.title}</button>}<p className="mt-1 text-[11px] text-ink-3">{board.rows.length} players <span className="mx-1.5">·</span>{board.columns.length} metrics <span className="mx-1.5">·</span>{board.season}<span className="mx-1.5">·</span>Updated {board.updated_at.slice(0, 10)}</p></div>
      {deleting === board.id ? <div className="flex items-center gap-1 text-[11px]"><span className="mr-2 text-ink-2">Delete this board?</span><Button size="xs" onClick={() => { deleteBoard(board.id); setDeleting(null); }}>Delete</Button><Button variant="quiet" size="xs" onClick={() => setDeleting(null)}>Cancel</Button></div> : <div className="flex items-center gap-1"><Button size="xs" variant="quiet" onClick={() => { setEditing(board.id); setTitle(board.title); }}>Rename</Button><Button size="xs" variant="quiet" className="text-ink-3" onClick={() => setDeleting(board.id)}>Delete</Button><Button size="xs" variant="secondary" onClick={() => onOpen(board.id)}>Open <ArrowUpRight width={12} /></Button></div>}
    </article>)}</div>}
  </section>;
}
=======
"use client";

import { useEffect, useState } from "react";
import { deleteBoard, listBoards, type Board } from "../lib/boards";
import { Button } from "./ds/Button";
import { Panel } from "./ds/Panel";

export function SavedBoards({ onOpen }: { onOpen: (id: string) => void }) {
  const [boards, setBoards] = useState<Board[]>([]);
  useEffect(() => {
    const update = () => setBoards(listBoards());
    update(); window.addEventListener("dime:boards", update); window.addEventListener("storage", update);
    return () => { window.removeEventListener("dime:boards", update); window.removeEventListener("storage", update); };
  }, []);
  return <section aria-label="Saved boards" className="mt-8"><h2 className="mb-4 text-sm font-medium">Saved boards <span className="ml-2 text-ink-3">{boards.length}</span></h2>{boards.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{boards.map(board => <Panel key={board.id} title={board.title} description={`${board.season} · ${board.rows.length} players · ${board.columns.length} metrics`}><div className="flex gap-2"><Button size="sm" onClick={() => onOpen(board.id)}>Open board<span className="sr-only"> {board.title}</span></Button><Button size="sm" variant="quiet" onClick={() => deleteBoard(board.id)}>Delete<span className="sr-only"> {board.title}</span></Button></div></Panel>)}</div> : <p className="text-xs text-ink-3">Boards you create will appear here. They stay in this browser.</p>}</section>;
}
>>>>>>> origin/dev

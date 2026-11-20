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

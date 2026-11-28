"use client";

import { useState } from "react";
import { Check, Pin } from "iconoir-react";
import { Button } from "@/components/ds/Button";
import { TextField } from "@/components/ds/TextField";
import { Popover, PopoverContent, PopoverDescription, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { getBoard, listBoards, newBoard, pinArtifact, saveBoard, type Board } from "@/lib/boards";
import type { DimeArtifact } from "@/lib/dime-stream";

export default function PinButton({ artifact }: { artifact: DimeArtifact }) {
  const [open, setOpen] = useState(false);
  const [boards, setBoards] = useState<Board[]>([]);
  const [title, setTitle] = useState("");
  const [pinned, setPinned] = useState("");
  const [failed, setFailed] = useState(false);

  function pinTo(board: Board) {
    try {
      saveBoard(pinArtifact(board, artifact));
      setPinned(board.title);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }

  function createBoard() {
    const name = title.trim();
    if (!name) return;
    const board = { ...newBoard(), title: name };
    pinTo(board);
    setTitle("");
  }

  return <Popover open={open} onOpenChange={next => { setOpen(next); if (next) { setBoards(listBoards()); setPinned(""); setFailed(false); } }}>
    <PopoverTrigger asChild>
      <Button size="icon" variant="quiet" aria-label="Pin to board" title="Pin to board"><Pin width={14} height={14} aria-hidden="true" /></Button>
    </PopoverTrigger>
    <PopoverContent align="end" aria-label="Pin artifact to a board" className="w-72 bg-surface text-ink">
      <PopoverTitle>Pin to board</PopoverTitle>
      <PopoverDescription>The artifact is stored with its provenance on a local board.</PopoverDescription>
      {pinned ? <p role="status" className="mt-3 flex items-center gap-2 text-xs text-ink-2"><Check width={13} height={13} aria-hidden="true" />Pinned to {pinned}.</p> : null}
      {failed ? <p role="alert" className="mt-3 text-xs text-red">This board is full or could not be saved.</p> : null}
      <div className="mt-3 max-h-48 space-y-1 overflow-auto">
        {boards.length ? boards.map(board => <button key={board.id} type="button" onClick={() => pinTo(board)} className="w-full rounded-md px-2 py-2 text-left text-xs hover:bg-inset">
          <span className="block truncate font-medium text-ink">{board.title}</span>
          <span className="block text-[11px] text-ink-3">{board.season} · {board.pins?.length ?? 0} pinned</span>
        </button>) : <p className="px-2 py-2 text-xs text-ink-3">No boards yet. Name one below to create it.</p>}
      </div>
      <div className="mt-3 flex gap-2 border-t border-line pt-3">
        <TextField aria-label="New board name" placeholder="New board name" value={title} maxLength={160} onChange={event => setTitle(event.target.value)} onKeyDown={event => { if (event.key === "Enter") createBoard(); }} />
        <Button size="sm" onClick={createBoard} disabled={!title.trim()}>Create</Button>
      </div>
    </PopoverContent>
  </Popover>;
}

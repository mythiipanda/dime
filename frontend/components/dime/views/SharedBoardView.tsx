"use client";

import type { SharedBoardObject } from "@/lib/shared";
import type { Board, BoardMetric } from "@/lib/boards";
import { BoardsTable } from "@/components/BoardsTable";
import { SharedFrame } from "./SharedScenarioView";

function sharedDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(date);
}

export function SharedBoardView({ object, board, metrics }: { object: SharedBoardObject; board: Board | null; metrics: BoardMetric[] }) {
  return (
    <SharedFrame label="shared board">
      <section className="mt-8">
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{object.title}</h1>
        <p className="mt-1.5 text-[12.5px] text-ink-3">
          {object.payload.rows.length} players · {object.payload.columns.length} metrics · {object.payload.season} season · live-evaluated from the warehouse · last edited {sharedDate(object.updated_at)}
        </p>
        {board ? (
          <div className="mt-6">
            <BoardsTable
              board={board}
              metrics={metrics}
              loading={false}
              sort={null}
              readOnly
              onSort={() => {}}
              onRemoveRow={() => {}}
              onRemoveColumn={() => {}}
              onMoveRow={() => {}}
              onMoveColumn={() => {}}
            />
            <p className="mt-4 max-w-lg text-[12px] leading-[1.6] text-ink-3">
              Click a value to inspect its warehouse evidence. Values recompute at open time, so this board reflects the data as it stands now.
            </p>
          </div>
        ) : (
          <div className="mt-6 rounded-[10px] bg-surface p-6 shadow-hairline">
            <h2 className="text-[15px] font-medium text-ink">This board can't be evaluated right now</h2>
            <p className="mt-2 max-w-[520px] text-[13px] leading-[1.6] text-ink-2">
              The shared board is intact, but the warehouse evaluation didn't complete. This is usually temporary — reload in a moment.
            </p>
          </div>
        )}
      </section>
    </SharedFrame>
  );
}

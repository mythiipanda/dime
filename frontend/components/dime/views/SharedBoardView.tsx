"use client";

import type { SharedBoardObject, SharedBoardPin } from "@/lib/shared";
import type { Board, BoardMetric } from "@/lib/boards";
import { BoardsTable } from "@/components/BoardsTable";
import { SharedFrame } from "./SharedScenarioView";
import { ArtifactBody } from "@/components/site/harness/ArtifactsView";
import { asResolvedArtifacts } from "@/lib/stream/artifacts";

const PIN_KIND_LABEL: Record<string, string> = {
  cap_scenario: "cap scenario",
  trade_scenario: "trade construction",
  artifact_ref: "artifact",
};

function PinCard({ pin }: { pin: SharedBoardPin }) {
  const label = PIN_KIND_LABEL[pin.kind] ?? pin.kind;
  if (pin.status !== "ok") {
    return (
      <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
        <p className="text-[11px] font-medium uppercase tracking-wide text-ink-3">{label}</p>
        <h3 className="mt-1 text-[13px] font-semibold text-ink">{pin.status === "archived" ? "This pin was removed by its owner" : "This pin can't be resolved"}</h3>
        <p className="mt-1 text-[12px] leading-[1.55] text-ink-3">
          {pin.status === "archived"
            ? "The pinned object still exists in archived form; its contents are no longer shared."
            : "The pinned object no longer exists. The rest of the board is unaffected."}
        </p>
      </section>
    );
  }
  return (
    <section className="rounded-[10px] bg-surface p-4 shadow-hairline">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-ink-3">{label}</p>
        <h3 className="text-[13px] font-semibold text-ink">{pin.title}</h3>
        {pin.note && <span className="text-[11.5px] text-ink-3">{pin.note}</span>}
      </div>

      {pin.kind === "cap_scenario" && pin.payload && (
        <div className="mt-2 text-[12.5px] text-ink-2">
          <p>
            <span className="font-medium text-ink">{String(pin.payload.team ?? "")}</span>
            <span className="text-ink-3"> · {String(pin.payload.season ?? "")} · </span>
            {Array.isArray(pin.payload.moves) ? pin.payload.moves.length : 0} moves
          </p>
          {!pin.capEvaluation && (
            <p className="mt-1.5 text-[12px] leading-[1.55] text-ink-3">Could not be evaluated live. The stored moves are shown without recomputed cap impact.</p>
          )}
          {pin.capEvaluation && pin.capEvaluation.errors.length > 0 && (
            <p className="mt-1.5 text-[12px] leading-[1.55] text-red">{typeof pin.capEvaluation.errors[0] === "string" ? pin.capEvaluation.errors[0] : pin.capEvaluation.errors[0].error}</p>
          )}
        </div>
      )}

      {pin.kind === "trade_scenario" && pin.payload && Array.isArray(pin.payload.legs) && (
        <div className="mt-2">
          <ol className="space-y-1">
            {(pin.payload.legs as { from?: string; to?: string; players?: string[] | string }[]).map((leg, i) => (
              <li key={i} className="text-[12.5px] text-ink-2">
                <span className="font-medium text-ink">{leg.from}</span>
                <span className="text-ink-3"> → </span>
                <span className="font-medium text-ink">{leg.to}</span>
                {leg.players && (
                  <span className="text-ink-3"> · {Array.isArray(leg.players) ? leg.players.join(", ") : leg.players}</span>
                )}
              </li>
            ))}
          </ol>
          {!pin.tradeEvaluation && (
            <p className="mt-1.5 text-[12px] leading-[1.55] text-ink-3">Could not be evaluated live. The stored legs are shown without a legality verdict.</p>
          )}
          {pin.tradeEvaluation && pin.tradeEvaluation.rows && pin.tradeEvaluation.rows.length > 0 && (
            <p className="mt-1.5 text-[12.5px] font-medium text-ink">
              {pin.tradeEvaluation.rows.every(row => row.matching_ok !== false) ? "Legal under current salary-matching rules" : "Not legal as constructed"}
            </p>
          )}
        </div>
      )}

      {pin.kind === "artifact_ref" && (
        <div className="mt-2">
          {pin.artifact_unavailable || !pin.artifact ? (
            <p className="text-[12px] leading-[1.55] text-ink-3">This artifact&apos;s underlying run is no longer available. The pin can&apos;t be rendered.</p>
          ) : (
            (() => {
              const resolved = asResolvedArtifacts([pin.artifact]);
              if (resolved.length === 0)
                return <p className="text-[12px] leading-[1.55] text-ink-3">This artifact&apos;s shape is no longer recognized. It can&apos;t be rendered.</p>;
              return <ArtifactBody artifact={resolved[0]} />;
            })()
          )}
        </div>
      )}
    </section>
  );
}

export function BoardPinsSection({ pins }: { pins: SharedBoardPin[] }) {
  if (pins.length === 0) return null;
  return (
    <div className="mt-8">
      <h2 className="text-[13px] font-semibold text-ink">Pinned to this board</h2>
      <div className="mt-3 space-y-4">
        {pins.map(pin => <PinCard key={pin.object_id} pin={pin} />)}
      </div>
      <p className="mt-3 max-w-lg text-[12px] leading-[1.6] text-ink-3">
        Pins are references to separately shared objects. Scenarios recompute live at open time and archived pins no longer expose their contents.
      </p>
    </div>
  );
}

function sharedDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(date);
}

export function SharedBoardView({ object, board, metrics, pins = [] }: { object: SharedBoardObject; board: Board | null; metrics: BoardMetric[]; pins?: SharedBoardPin[] }) {
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
              The shared board is intact, but the warehouse evaluation didn't complete. This is usually temporary. Reload in a moment.
            </p>
          </div>
        )}
        <BoardPinsSection pins={pins} />
      </section>
    </SharedFrame>
  );
}

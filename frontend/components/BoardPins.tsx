"use client";

import { useState } from "react";
import { Pin, RefreshCw, X } from "lucide-react";
import { Button } from "./ds/Button";
import { StatusPill } from "./ds/StatusPill";
import { Surface } from "./ds/Panel";
import { ArtifactBody } from "./site/harness/ArtifactsView";
import { rerunSql } from "../lib/api";
import { applyPinRerun, cardRequeries, unpinArtifact, updatePin, type Board, type BoardPin, type PinRequery } from "../lib/boards";

function requeriesFor(artifact: BoardPin["artifact"]): PinRequery[] {
  return cardRequeries(artifact);
}

function PinCard({ pin, onChange, onRemove }: { pin: BoardPin; onChange: (pin: BoardPin) => void; onRemove: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const queries = requeriesFor(pin.artifact);
  const kindLabel = pin.artifact.kind.replace(/_/g, " ");

  async function refresh() {
    setBusy(true);
    setError("");
    try {
      const rows = new Map<PinRequery["key"], Record<string, unknown> | undefined>();
      for (const query of queries) {
        const result = await rerunSql(query.sql);
        rows.set(query.key, result.rows[query.row]);
      }
      const refreshed = applyPinRerun(pin.artifact, rows);
      onChange({ ...pin, artifact: refreshed });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Re-run failed. Pinned values unchanged.");
    } finally {
      setBusy(false);
    }
  }

  return <Surface className="min-w-0 overflow-hidden">
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
      <div className="min-w-0">
        <p className="break-words text-[13px] font-medium text-ink">{pin.artifact.title}</p>
        <p className="mt-1 break-words text-xs text-ink-3">
          {kindLabel} · pinned {new Date(pin.pinned_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
          {pin.refreshed_at ? ` · refreshed ${new Date(pin.refreshed_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}` : ""}
        </p>
      </div>
      <div className="flex items-center gap-1">
        {queries.length > 0 && <Button size="sm" variant="quiet" loading={busy} onClick={refresh}><RefreshCw size={13} />Re-run</Button>}
        <Button size="icon" variant="quiet" aria-label={`Remove pin ${pin.artifact.title}`} title="Remove pin" onClick={onRemove}><X size={14} aria-hidden="true" /></Button>
      </div>
    </div>
    <ArtifactBody artifact={pin.artifact} />
    {error && <p role="alert" className="px-4 pb-3 text-xs text-red">{error}</p>}
  </Surface>;
}

export default function BoardPins({ board, onCommit }: { board: Board; onCommit: (board: Board) => void }) {
  const pins = board.pins ?? [];
  if (!pins.length) return null;
  return <section className="mt-8">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h2 className="flex items-center gap-2 text-sm font-medium"><Pin size={14} className="text-ink-3" aria-hidden="true" />Pinned artifacts</h2>
      <StatusPill dot={false}>{pins.length} pinned</StatusPill>
    </div>
    <div className="grid items-start gap-4 xl:grid-cols-2">
      {pins.map(pin => <PinCard key={pin.id} pin={pin}
        onChange={next => onCommit(updatePin(board, pin.id, next.artifact))}
        onRemove={() => onCommit(unpinArtifact(board, pin.id))} />)}
    </div>
    <p className="mt-4 text-xs leading-relaxed text-ink-3">Pinned values keep the provenance they were saved with. Re-run replays the saved source query against the current warehouse; unavailable sources keep their pinned values.</p>
  </section>;
}

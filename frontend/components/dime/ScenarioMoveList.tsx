"use client";

import { motion, MotionConfig } from "motion/react";

import type { ScenarioMove } from "@/lib/capsheet-fixture";
import { describeScenarioMove } from "@/lib/capsheet-fixture";
import { unitizeMoves, removeUnitAt, ungroupAt, moveUnit, type MoveGroupsMap, type MoveUnit } from "@/lib/move-groups";

export type MoveListLabels = {
  describe: (move: ScenarioMove) => string;
  waiverBasis?: (move: ScenarioMove) => string | undefined;
};

const action = "text-[11px] text-ink-2 underline-offset-2 hover:underline";

export default function ScenarioMoveList({
  moves,
  groups,
  labels,
  onChange,
  reorderable = false,
  numbered = false,
  readOnly = false,
}: {
  moves: ScenarioMove[];
  groups: MoveGroupsMap;
  labels: MoveListLabels;
  onChange?: (next: ScenarioMove[]) => void;
  reorderable?: boolean;
  numbered?: boolean;
  readOnly?: boolean;
}) {
  const units = unitizeMoves(moves);
  const unitKeys = stableUnitKeys(units);
  return (
    <MotionConfig reducedMotion="user">
      {units.map((unit, unitIndex) => {
        const reorder = reorderable && (
          <span className="flex shrink-0 flex-col leading-none">
            <button
              aria-label="Move earlier"
              disabled={unitIndex === 0}
              className="text-[10px] text-ink-3 hover:text-ink disabled:opacity-30"
              onClick={() => onChange?.(moveUnit(moves, unitIndex, -1))}
            >
              ▲
            </button>
            <button
              aria-label="Move later"
              disabled={unitIndex === units.length - 1}
              className="text-[10px] text-ink-3 hover:text-ink disabled:opacity-30"
              onClick={() => onChange?.(moveUnit(moves, unitIndex, 1))}
            >
              ▼
            </button>
          </span>
        );
        if (unit.group) {
          const meta = groups[unit.group];
          const outCount = unit.entries.filter((entry) => entry.move.kind === "trade_out").length;
          const inCount = unit.entries.filter((entry) => entry.move.kind === "trade_in").length;
          return (
            <motion.div layout key={unitKeys[unitIndex]} className="rounded-[8px] border border-line px-2.5 py-2">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-ink-3">
                  {numbered && <span className="mr-1.5 font-mono normal-case tracking-normal">{unitIndex + 1}</span>}Trade{meta?.partner ? ` with ${meta.partner}` : ""} · {outCount} out / {inCount} in
                </span>
                {!readOnly && (
                  <span className="flex shrink-0 items-center gap-2">
                    {reorder}
                    <button
                      className={action}
                      title="The moves stay, but the result may no longer represent a legal trade"
                      onClick={() => onChange?.(ungroupAt(moves, unitIndex))}
                    >
                      split
                    </button>
                    <button className={action} onClick={() => onChange?.(removeUnitAt(moves, unitIndex))}>
                      remove
                    </button>
                  </span>
                )}
              </div>
              <div className="mt-1 space-y-1">
                {unit.entries.map((entry) => (
                  <p key={entry.index} className="text-[12px] text-ink-2">{labels.describe(entry.move)}</p>
                ))}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <span className="text-[10.5px] leading-[1.4] text-ink-3">One transaction; its legs move as a unit.</span>
                {meta?.verdict != null && (
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${meta.verdict ? "bg-green-tint text-green" : "bg-red/10 text-red"}`}
                    title={meta.evaluated_at ? `Both teams' states frozen at evaluation · ${meta.evaluated_at.slice(0, 10)}` : "Both teams' states frozen at evaluation"}
                  >
                    {meta.verdict ? "legal" : "illegal"} at import{meta.evaluated_at ? ` · ${meta.evaluated_at.slice(0, 10)}` : ""}
                  </span>
                )}
              </div>
            </motion.div>
          );
        }
        const entry = unit.entries[0];
        const basis = labels.waiverBasis?.(entry.move);
        return (
          <motion.div layout key={unitKeys[unitIndex]} className="flex items-baseline justify-between gap-2 text-[12px]">
            <div className="min-w-0">
              <span className="text-ink-2">{numbered && <span className="mr-2 font-mono text-[10.5px] text-ink-3">{unitIndex + 1}</span>}{labels.describe(entry.move)}</span>
              {basis && (
                <span className="mt-0.5 block text-[11px] leading-[1.45] text-ink-2">{basis}</span>
              )}
            </div>
            {!readOnly && (
              <span className="flex shrink-0 items-center gap-2">
                {reorder}
                <button className={action} onClick={() => onChange?.(removeUnitAt(moves, unitIndex))}>
                  remove
                </button>
              </span>
            )}
          </motion.div>
        );
      })}
    </MotionConfig>
  );
}


function moveFingerprint(move: ScenarioMove): string {
  return [move.kind, move.player ?? "", move.season ?? "", move.label ?? "", String(move.amount ?? "")].join("|");
}

function stableUnitKeys(units: MoveUnit[]): (string | undefined)[] {
  const seen = new Map<string, number>();
  return units.map((unit) => {
    if (unit.group) return unit.group;
    const base = moveFingerprint(unit.entries[0].move);
    const occurrence = seen.get(base) ?? 0;
    seen.set(base, occurrence + 1);
    return occurrence === 0 ? base : `${base}#${occurrence}`;
  });
}

export function ReadOnlyMoveList({ moves, groups }: { moves: ScenarioMove[]; groups: MoveGroupsMap }) {
  return <ScenarioMoveList moves={moves} groups={groups} labels={{ describe: describeScenarioMove }} numbered readOnly />;
}

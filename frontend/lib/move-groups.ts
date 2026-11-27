import type { ScenarioMove } from "./capsheet-fixture";

export interface MoveGroupMeta {
  partner?: string;
  verdict?: boolean | null;
  evaluated_at?: string;
}

export type MoveGroupsMap = Record<string, MoveGroupMeta>;

export interface MoveUnit {
  group: string | null;
  entries: { move: ScenarioMove; index: number }[];
}

export function mintGroupId(): string {
  return `trade-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function unitizeMoves(moves: ScenarioMove[]): MoveUnit[] {
  const units: MoveUnit[] = [];
  moves.forEach((move, index) => {
    const previous = units[units.length - 1];
    if (move.group && previous && previous.group === move.group) {
      previous.entries.push({ move, index });
      return;
    }
    units.push({ group: move.group ?? null, entries: [{ move, index }] });
  });
  return units;
}

export function removeUnitAt(moves: ScenarioMove[], unitIndex: number): ScenarioMove[] {
  const units = unitizeMoves(moves);
  const unit = units[unitIndex];
  if (!unit) return moves;
  if (unit.group) return moves.filter((move) => move.group !== unit.group);
  const [entry] = unit.entries;
  return moves.filter((_, index) => index !== entry.index);
}

export function ungroupAt(moves: ScenarioMove[], unitIndex: number): ScenarioMove[] {
  const units = unitizeMoves(moves);
  const unit = units[unitIndex];
  if (!unit || !unit.group) return moves;
  const group = unit.group;
  return moves.map((move) => {
    if (move.group !== group) return move;
    const next = { ...move };
    delete next.group;
    return next;
  });
}

export function pruneGroups(moves: ScenarioMove[], groups: MoveGroupsMap): MoveGroupsMap {
  const live = new Set(moves.map((move) => move.group).filter((group): group is string => Boolean(group)));
  const next: MoveGroupsMap = {};
  let changed = false;
  for (const [id, meta] of Object.entries(groups)) {
    if (live.has(id)) next[id] = meta;
    else changed = true;
  }
  if (!changed && Object.keys(next).length === Object.keys(groups).length) return groups;
  return next;
}

export function moveUnit(moves: ScenarioMove[], unitIndex: number, direction: -1 | 1): ScenarioMove[] {
  const units = unitizeMoves(moves);
  const target = unitIndex + direction;
  if (unitIndex < 0 || unitIndex >= units.length || target < 0 || target >= units.length) return moves;
  const reordered = units.slice();
  const [swapped] = reordered.splice(unitIndex, 1);
  reordered.splice(target, 0, swapped);
  return reordered.flatMap((unit) => unit.entries.map((entry) => entry.move));
}

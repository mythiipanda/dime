


























import type {
  Mover,
  MoversRows,
  NewEntry,
  TeamStreak,
  TodayMover,
  WatchItem,
} from "./api";
import { rankOf } from "./rankContext";

type FeedKind = "mover" | "streak" | "watchlist";

export interface FeedItem {
  id: string;
  kind: FeedKind;
  

  entity: "player" | "team";
  name: string;
  team?: string;
  

  statText: string;
  

  rankLabel: string;
  

  rankTitle: string;
  

  question: string | null;
}

interface FeedInput {
  movers?: MoversRows | TodayMover[] | null;
  streaks?: TeamStreak[] | null;
  watchlist?: WatchItem[] | null;
}

export const FEED_MOVER_CAP = 6;
export const FEED_STREAK_CAP = 4;
export const FEED_WATCH_CAP = 4;

function clean(v: unknown): string {
  return typeof v === "string" ? v.trim() : "";
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function pts(delta: number): string {
  return `${delta > 0 ? "+" : ""}${delta.toFixed(1)} pts`;
}



function spots(change: number): string {
  const n = Math.abs(Math.round(change));
  return `${change > 0 ? "up" : "down"} ${n} spot${n === 1 ? "" : "s"}`;
}



function changeText(raw: string): string | null {
  const n = Number(raw);
  if (raw !== "" && Number.isFinite(n) && Math.round(n) !== 0) {
    return spots(n);
  }
  return raw !== "" ? raw : null;
}



function streakText(raw: string): { text: string; won: boolean | null; games: number | null } {
  const head = raw.charAt(0).toUpperCase();
  const n = parseInt(raw.slice(1).trim(), 10);
  if ((head === "W" || head === "L") && Number.isFinite(n) && n > 0) {
    const won = head === "W";
    return {
      text: won ? `won ${n} straight` : `lost ${n} straight`,
      won,
      games: n,
    };
  }
  return { text: raw, won: null, games: null };
}

function moverFromMover(
  m: Mover,
  index: number,
  total: number,
): FeedItem | null {
  const name = clean(m.player);
  if (!name) return null;
  const rankChange = num(m.rank_change);
  const ptsChange = num(m.pts_change);
  const ptsNow = num(m.pts_now);
  const rankNow = num(m.rank_now);
  const parts: string[] = [];
  if (rankChange !== null && Math.round(rankChange) !== 0) {
    parts.push(spots(rankChange));
  }
  if (ptsChange !== null) parts.push(pts(ptsChange));
  if (parts.length === 0 && ptsNow !== null) {
    parts.push(`${ptsNow.toFixed(1)} pts`);
  }
  if (parts.length === 0 && rankNow !== null) {
    parts.push(`ranked #${Math.round(rankNow)}`);
  }
  if (parts.length === 0) return null;
  const rankLabel =
    rankNow !== null ? `#${Math.round(rankNow)}` : rankOf(index, total).chip;
  const rankTitle =
    rankNow !== null
      ? `Ranked #${Math.round(rankNow)} by points per game`
      : `Ranked ${rankOf(index, total).chip} of ${total} movers by points per game`;
  return {
    id: `mover-${index}-${name}`,
    kind: "mover",
    entity: "player",
    name,
    team: clean(m.team) || undefined,
    statText: parts.join(", "),
    rankLabel,
    rankTitle,
    question: null,
  };
}

function moverFromEntry(
  e: NewEntry,
  index: number,
  total: number,
): FeedItem | null {
  const name = clean(e.player);
  if (!name) return null;
  const p = num(e.pts);
  const r = num(e.rank);
  if (p === null && r === null) return null;
  const statText = p !== null ? `${p.toFixed(1)} pts` : `ranked #${Math.round(r!)}`;
  const rankLabel = r !== null ? `#${Math.round(r)}` : rankOf(index, total).chip;
  const rankTitle =
    r !== null
      ? `Ranked #${Math.round(r)} by points per game`
      : `Ranked ${rankOf(index, total).chip} of ${total} new entries by points per game`;
  return {
    id: `new-${index}-${name}`,
    kind: "mover",
    entity: "player",
    name,
    team: clean(e.team) || undefined,
    statText,
    rankLabel,
    rankTitle,
    question: null,
  };
}

function moverFromToday(
  m: TodayMover,
  index: number,
  total: number,
): FeedItem | null {
  const name = clean(m.PLAYER);
  if (!name) return null;
  const parts: string[] = [];
  const rc = changeText(clean(m.RANK_CHANGE));
  if (rc) parts.push(rc);
  const pc = num(m.PTS_CHANGE);
  if (pc !== null) parts.push(pts(pc));
  if (parts.length === 0) {
    const note = clean(m.note);
    if (!note) return null;
    parts.push(note);
  }
  const rc2 = rankOf(index, total);
  return {
    id: `mover-today-${index}-${name}`,
    kind: "mover",
    entity: "player",
    name,
    team: clean(m.TEAM) || undefined,
    statText: parts.join(", "),
    rankLabel: rc2.chip,
    rankTitle: `Ranked ${rc2.chip} of ${total} movers by points per game`,
    question: null,
  };
}

function buildFullMoverItems(
  movers: MoversRows | TodayMover[] | null | undefined,
): FeedItem[] {
  if (!movers) return [];
  if (Array.isArray(movers)) {
    const total = Math.max(1, movers.length);
    const out: FeedItem[] = [];
    for (let i = 0; i < movers.length; i++) {
      const item = moverFromToday(movers[i], i, total);
      if (item) out.push(item);
    }
    return out;
  }
  const climbers = Array.isArray(movers.climbers) ? movers.climbers : [];
  const fallers = Array.isArray(movers.fallers) ? movers.fallers : [];
  const entries = Array.isArray(movers.new_entries) ? movers.new_entries : [];
  const pool: FeedItem[] = [];
  const push = (item: FeedItem | null) => {
    if (item) pool.push(item);
  };
  const ct = Math.max(1, climbers.length);
  const ft = Math.max(1, fallers.length);
  const et = Math.max(1, entries.length);
  climbers.forEach((m, i) => push(moverFromMover(m, i, ct)));
  fallers.forEach((m, i) => push(moverFromMover(m, i, ft)));
  entries.forEach((e, i) => push(moverFromEntry(e, i, et)));
  return pool;
}

export function buildMoverItems(
  movers: MoversRows | TodayMover[] | null | undefined,
): FeedItem[] {
  return buildFullMoverItems(movers).slice(0, FEED_MOVER_CAP);
}

function buildFullStreakItems(
  streaks: TeamStreak[] | null | undefined,
): FeedItem[] {
  if (!Array.isArray(streaks)) return [];
  const total = Math.max(1, streaks.length);
  const out: FeedItem[] = [];
  for (let i = 0; i < streaks.length; i++) {
    const s = streaks[i];
    if (!s) continue;
    const name = clean(s.TEAM);
    const raw = clean(s.STREAK);
    if (!name || !raw) continue;
    const parsed = streakText(raw);
    const w = num(s.W);
    const l = num(s.L);
    const record = w !== null && l !== null ? `${w}-${l}` : "";
    const statText = record ? `${parsed.text} · ${record}` : parsed.text;
    const rc = rankOf(i, total);
    let question: string;
    if (parsed.won !== null && parsed.games !== null) {
      question = `Why has ${name} ${parsed.won ? "won" : "lost"} ${parsed.games} straight?`;
    } else if (record) {
      question = `How is ${name} playing at ${record}?`;
    } else {
      question = `How is ${name} playing?`;
    }
    out.push({
      id: `streak-${i}-${name}`,
      kind: "streak",
      entity: "team",
      name,
      statText,
      rankLabel: rc.chip,
      rankTitle: `Ranked ${rc.chip} of ${total} team streaks`,
      question,
    });
  }
  return out;
}

export function buildStreakItems(
  streaks: TeamStreak[] | null | undefined,
): FeedItem[] {
  return buildFullStreakItems(streaks).slice(0, FEED_STREAK_CAP);
}

interface RankedWatch {
  item: WatchItem;
  name: string;
  sub: string | undefined;
}

function buildFullWatchItems(
  watchlist: WatchItem[] | null | undefined,
): FeedItem[] {
  if (!Array.isArray(watchlist)) return [];
  const players: RankedWatch[] = [];
  const teams: RankedWatch[] = [];
  for (const item of watchlist) {
    if (!item || !item.snapshot) continue;
    const s = item.snapshot;
    if (s.found === false) continue;
    if (item.entity_type === "player") {
      if (num(s.ppg) === null) continue;
      const name = clean(s.player) || clean(s.name) || clean(item.entity_id);
      if (!name) continue;
      players.push({ item, name, sub: clean(s.team) || undefined });
    } else if (item.entity_type === "team") {
      const name = clean(s.name) || clean(s.team) || clean(item.entity_id);
      const record = clean(s.record);
      const wins = num(s.wins);
      if (!name || (!record && wins === null)) continue;
      teams.push({ item, name, sub: undefined });
    }
  }
  const byPpg = [...players].sort(
    (a, b) => (num(b.item.snapshot.ppg) ?? 0) - (num(a.item.snapshot.ppg) ?? 0),
  );
  const playerRank = new Map<WatchItem, number>();
  byPpg.forEach((p, i) => playerRank.set(p.item, i + 1));
  const winsOf = (w: RankedWatch): number => {
    const s = w.item.snapshot;
    const direct = num(s.wins);
    if (direct !== null) return direct;
    const head = Number(clean(s.record).split("-")[0]);
    return Number.isFinite(head) ? head : -1;
  };
  const byWins = [...teams].sort((a, b) => winsOf(b) - winsOf(a));
  const teamRank = new Map<WatchItem, number>();
  byWins.forEach((t, i) => teamRank.set(t.item, i + 1));

  const out: FeedItem[] = [];
  for (const item of watchlist) {
    if (!item || !item.snapshot) continue;
    if (item.entity_type === "player") {
      const found = players.find((p) => p.item === item);
      if (!found) continue;
      const rank = playerRank.get(item) ?? 1;
      const ppg = num(item.snapshot.ppg) ?? 0;
      out.push({
        id: `watch-player-${clean(item.entity_id) || found.name}`,
        kind: "watchlist",
        entity: "player",
        name: found.name,
        team: found.sub,
        statText: `${ppg.toFixed(1)} ppg`,
        rankLabel: `#${rank}`,
        rankTitle: `Ranked #${rank} of ${players.length} watched players by PPG`,
        question: null,
      });
    } else if (item.entity_type === "team") {
      const found = teams.find((t) => t.item === item);
      if (!found) continue;
      const rank = teamRank.get(item) ?? 1;
      const s = item.snapshot;
      const record = clean(s.record);
      const w = num(s.wins);
      const l = num(s.losses);
      const text = record || (w !== null ? `${w}-${l ?? 0}` : "");
      out.push({
        id: `watch-team-${clean(item.entity_id) || found.name}`,
        kind: "watchlist",
        entity: "team",
        name: found.name,
        statText: text,
        rankLabel: `#${rank}`,
        rankTitle: `Ranked #${rank} of ${teams.length} watched teams by wins`,
        question: `How is ${found.name} playing at ${text}?`,
      });
    }
  }
  return out;
}

export function buildWatchItems(
  watchlist: WatchItem[] | null | undefined,
): FeedItem[] {
  return buildFullWatchItems(watchlist).slice(0, FEED_WATCH_CAP);
}



export function buildFeedItems(input: FeedInput): FeedItem[] {
  return [
    ...buildMoverItems(input.movers),
    ...buildStreakItems(input.streaks),
    ...buildWatchItems(input.watchlist),
  ];
}

export interface FeedExpansion {
  visible: FeedItem[];
  extra: FeedItem[];
  total: number;
}



export function buildFeedExpansion(input: FeedInput): FeedExpansion {
  const visible = buildFeedItems(input);
  const extra = [
    ...buildFullMoverItems(input.movers).slice(FEED_MOVER_CAP),
    ...buildFullStreakItems(input.streaks).slice(FEED_STREAK_CAP),
    ...buildFullWatchItems(input.watchlist).slice(FEED_WATCH_CAP),
  ];
  return { visible, extra, total: visible.length + extra.length };
}

// Data-driven Explore quick-ask starters (redesign Phase C). Names come from
// live data — the user's watchlist plus the weekly story (movers, streaks) —
// capped at 3. The templates are fixed but no player, team, or stat is
// hardcoded; nothing here judges, only asks.
import type { Mover, TeamStreak, WatchItem } from "./api";

export interface QuickStarter {
  label: string;
  question: string;
}

export function watchDisplayName(item: WatchItem): string {
  const s = item.snapshot ?? {};
  return s.player || s.team || s.name || item.entity_id;
}

export function buildQuickStarters(input: {
  watchlist?: WatchItem[];
  climbers?: Mover[];
  streaks?: TeamStreak[];
}): QuickStarter[] {
  const out: QuickStarter[] = [];

  // Watchlist first: the questions the user is already invested in.
  for (const item of (input.watchlist ?? []).slice(0, 2)) {
    if (out.length >= 3) break;
    const name = watchDisplayName(item);
    out.push({
      label: "Watchlist",
      question:
        item.entity_type === "team"
          ? `How is ${name} performing this season?`
          : `What is driving ${name}'s season so far?`,
    });
  }

  // Weekly story: the biggest scoring climber, then a live streak.
  if (out.length < 3) {
    const mover = (input.climbers ?? []).find((m) => m.player || m.team);
    if (mover) {
      out.push({
        label: "Movers",
        question: `${mover.player || mover.team} is climbing the scoring leaderboard this week — what changed?`,
      });
    }
  }
  if (out.length < 3) {
    const s = (input.streaks ?? []).find(
      (x) => x.TEAM && /^[WL]\d+$/i.test(String(x.STREAK || "")),
    );
    if (s) {
      const m = /^([WL])(\d+)$/i.exec(String(s.STREAK))!;
      out.push({
        label: "Streaks",
        question: `What is behind ${s.TEAM}'s ${m[2]}-game ${m[1].toUpperCase() === "W" ? "winning" : "losing"} streak?`,
      });
    }
  }

  // Graceful when the backend is unreachable: one generic live-data question.
  if (out.length === 0) {
    out.push({
      label: "Ask",
      question: "Which players are trending up in the data right now?",
    });
  }
  return out.slice(0, 3);
}

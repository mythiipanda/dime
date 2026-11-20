"use client";

import { useEffect, useState } from "react";
import { getToday, getWatchlist } from "../lib/api";
import type { TodayMover, TeamStreak, WatchItem } from "../lib/api";
import { buildFeedExpansion, feedActionFor, type FeedExpansion, type FeedItem } from "../lib/exploreFeed";
import type { ExploreContext } from "../lib/exploreSearch";
import Skeleton from "./Skeleton";
import { Panel } from "./ds/Panel";
import { Button } from "./ds/Button";
import { ValuePill } from "./ds/ValuePill";









export default function ExploreFeed({
  onAsk,
  onSelect,
}: {
  onAsk: (q: string) => void;
  onSelect: (ctx: ExploreContext) => void;
}) {
  const [feed, setFeed] = useState<FeedExpansion | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let live = true;
    let base: { movers: TodayMover[]; streaks: TeamStreak[] } | null = null;
    let watchlist: WatchItem[] | null = null;
    const paint = (resetExpansion: boolean) => {
      if (!base) return;
      setFeed(buildFeedExpansion(watchlist ? { ...base, watchlist } : base));
      if (resetExpansion) setExpanded(false);
    };
    getToday()
      .then((today) => {
        if (!live) return;
        base = { movers: today.movers, streaks: today.streaks };
        paint(true);
      })
      .catch(() => {
        if (live) setFeed({ visible: [], extra: [], total: 0 });
      });
    getWatchlist()
      .then((watch) => {
        if (!live) return;
        watchlist = watch;
        paint(false);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  if (feed === null) {
    return (
      <Panel title="Right now" className="my-6">
        <div style={{ minHeight: 132 }}>
          <Skeleton lines={4} />
        </div>
      </Panel>
    );
  }
  if (feed.total === 0) return null;

  const activate = (item: FeedItem) => {
    const action = feedActionFor(item);
    if (action.kind === "select") {
      onSelect(action.ctx);
    } else if (action.kind === "ask") {
      onAsk(action.question);
    }
  };

  const shown = expanded ? [...feed.visible, ...feed.extra] : feed.visible;

  const row = (item: FeedItem) => (
    <li key={item.id}>
      <button
        type="button"
        className="flex w-full flex-wrap items-baseline gap-2 rounded-lg px-2 py-3 text-left text-[12px] transition-colors hover:bg-hover"
        onClick={() => activate(item)}
        aria-label={`${item.name}, ${item.statText}, ${item.rankTitle}`}
      >
        <span className="min-w-40 flex-1 font-medium">
          {item.name}
          {item.team ? (
            <span className="font-normal text-ink-3"> {item.team}</span>
          ) : null}
        </span>
        <span className="text-[11px] tabular-nums text-ink-2">{item.statText}</span>
        <span title={item.rankTitle}>
          <ValuePill>{item.rankLabel}</ValuePill>
        </span>
      </button>
    </li>
  );

  return (
    <Panel title="Right now" description="Signals from the latest available league data and your watchlist." className="my-6">
      <ul className="divide-y divide-line">
        {shown.map(row)}
        {feed.extra.length > 0 ? (
          <li key="explore-feed-expander">
            <Button
              type="button"
              variant="quiet" size="xs" className="mt-2 text-ink-3"
              aria-expanded={expanded}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Show fewer" : "Show all " + feed.total}
            </Button>
          </li>
        ) : null}
      </ul>
    </Panel>
  );
}

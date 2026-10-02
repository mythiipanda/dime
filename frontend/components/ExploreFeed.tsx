"use client";

import { useEffect, useState } from "react";
import { getToday, getWatchlist } from "../lib/api";
import type { TodayMover, TeamStreak, WatchItem } from "../lib/api";
import { buildFeedExpansion, feedActionFor, type FeedExpansion, type FeedItem } from "../lib/exploreFeed";
import type { ExploreContext } from "../lib/exploreSearch";
import Skeleton from "./Skeleton";









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
    const render = () => {
      if (!base) return;
      setFeed(buildFeedExpansion(watchlist ? { ...base, watchlist } : base));
      setExpanded(false);
    };
    getToday()
      .then((today) => {
        if (!live) return;
        base = { movers: today.movers, streaks: today.streaks };
        render();
      })
      .catch(() => {
        if (live) setFeed({ visible: [], extra: [], total: 0 });
      });
    getWatchlist()
      .then((watch) => {
        if (!live) return;
        watchlist = watch;
        render();
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  if (feed === null) {
    return (
      <div className="explore-feed" aria-label="Right now">
        <div className="panel-kicker">Right now</div>
        <div style={{ minHeight: 132 }}>
          <Skeleton lines={4} />
        </div>
      </div>
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
        className="explore-feed-row"
        onClick={() => activate(item)}
        aria-label={`${item.name}, ${item.statText}, ${item.rankTitle}`}
      >
        <span className="explore-feed-name">
          {item.name}
          {item.team ? (
            <span className="explore-feed-team"> {item.team}</span>
          ) : null}
        </span>
        <span className="explore-feed-stat">{item.statText}</span>
        <span className="explore-feed-rank" title={item.rankTitle}>
          {item.rankLabel}
        </span>
      </button>
    </li>
  );

  return (
    <section className="explore-feed" aria-label="Right now">
      <div className="panel-kicker">Right now</div>
      <ul className="explore-feed-list">
        {shown.map(row)}
        {feed.extra.length > 0 ? (
          <li key="explore-feed-expander">
            <button
              type="button"
              className="explore-feed-expander"
              aria-expanded={expanded}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Show fewer" : "Show all " + feed.total}
            </button>
          </li>
        ) : null}
      </ul>
    </section>
  );
}

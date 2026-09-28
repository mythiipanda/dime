"use client";

import { useEffect, useState } from "react";
import { getToday, getWatchlist } from "../lib/api";
import { buildFeedItems, type FeedItem } from "../lib/exploreFeed";
import type { ExploreContext } from "../lib/exploreSearch";
import Skeleton from "./Skeleton";

// Right-now feed (redesign Phase 4). One clickable row per item: player
// rows open the shots panel with context applied, team rows ask Dime a
// factual question. Renders nothing on fetch error or when every endpoint
// comes back without data: no error prose, no empty states.
export default function ExploreFeed({
  onAsk,
  onSelect,
}: {
  onAsk: (q: string) => void;
  onSelect: (ctx: ExploreContext) => void;
}) {
  const [items, setItems] = useState<FeedItem[] | null>(null);

  useEffect(() => {
    let live = true;
    // Staggered: the watchlist fetch waits until today resolves. The page
    // already fires 4+ parallel fetches on mount, so this one stays gentle.
    getToday()
      .then((today) => {
        if (!live) return;
        const base = { movers: today.movers, streaks: today.streaks };
        setItems(buildFeedItems(base));
        getWatchlist()
          .then((watch) => {
            if (live) setItems(buildFeedItems({ ...base, watchlist: watch }));
          })
          .catch(() => {});
      })
      .catch(() => {
        if (live) setItems([]);
      });
    return () => {
      live = false;
    };
  }, []);

  if (items === null) {
    return (
      <div className="explore-feed" aria-label="Right now">
        <div className="panel-kicker">Right now</div>
        <div style={{ minHeight: 132 }}>
          <Skeleton lines={4} />
        </div>
      </div>
    );
  }
  if (items.length === 0) return null;

  const activate = (item: FeedItem) => {
    if (item.entity === "player") {
      onSelect({ panel: "shots", playerName: item.name });
    } else if (item.question) {
      onAsk(item.question);
    }
  };

  return (
    <section className="explore-feed" aria-label="Right now">
      <div className="panel-kicker">Right now</div>
      <ul className="explore-feed-list">
        {items.map((item) => (
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
        ))}
      </ul>
    </section>
  );
}

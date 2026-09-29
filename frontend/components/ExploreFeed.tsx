"use client";

import { useEffect, useState } from "react";
import { getToday, getWatchlist } from "../lib/api";
import { buildFeedExpansion, type FeedExpansion, type FeedItem } from "../lib/exploreFeed";
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


    getToday()
      .then((today) => {
        if (!live) return;
        const base = { movers: today.movers, streaks: today.streaks };
        setFeed(buildFeedExpansion(base));
        setExpanded(false);
        getWatchlist()
          .then((watch) => {
            if (live) {
              setFeed(buildFeedExpansion({ ...base, watchlist: watch }));
              setExpanded(false);
            }
          })
          .catch(() => {});
      })
      .catch(() => {
        if (live) setFeed({ visible: [], extra: [], total: 0 });
      });
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
    if (item.entity === "player") {
      onSelect({ panel: "shots", playerName: item.name });
    } else if (item.question) {
      onAsk(item.question);
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

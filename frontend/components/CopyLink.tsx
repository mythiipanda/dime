"use client";

import { useState } from "react";
import { panelShareUrl } from "../lib/exploreUrl";







export default function CopyLink({ panel, anchor }: { panel: string; anchor?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] transition-colors bg-field text-ink-2 hover:bg-hover"
      style={{ fontSize: 12 }}
      onClick={() => {
        if (typeof window === "undefined") return;
        const url = panelShareUrl(
          window.location.origin,
          window.location.pathname,
          window.location.search,
          panel,
          anchor,
        );
        navigator.clipboard
          .writeText(url)
          .then(() => {
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          })
          .catch(() => {});
      }}
    >
      {done ? "Copied" : "Copy link"}
    </button>
  );
}

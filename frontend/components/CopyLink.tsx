"use client";

import { useState } from "react";
import { panelShareUrl } from "../lib/exploreUrl";
/**
 * Copy-link button for an Explore panel (redesign Phase 3). Copies the
 * panel's shareable URL: only that panel's filter params plus the panel
 * id, so opening the link reproduces the view.
 */


export default function CopyLink({ panel, anchor }: { panel: string; anchor?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="pill-ghost"
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

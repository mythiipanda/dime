"use client";

import { useState } from "react";
import FreshnessPanel from "./FreshnessPanel";

// Collapsed by default: the raw table-row freshness view is a system-status
// detail, not an end-user analysis section.
export default function SystemStatus() {
  const [open, setOpen] = useState(false);

  return (
    <details
      id="system-status"
      className="system-status"
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="system-status-summary">Data updates</summary>
      {open && (
        <div className="system-status-body">
          <FreshnessPanel />
        </div>
      )}
    </details>
  );
}

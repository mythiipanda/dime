"use client";

import { useEffect, useRef, useState } from "react";

/* Thinking-states transition (transitions.dev #28, vendored at
 * research/design-skills/transitions-dev/skill/28-thinking-states.md):
 * the status line shimmers while a state holds, then swaps to the next
 * state - old copy exits up through a blur, new copy rises from below. */
export default function ThinkLine({ text }: { text: string }) {
  const [shown, setShown] = useState(text);
  const [leaving, setLeaving] = useState<string | null>(null);
  const first = useRef(true);

  useEffect(() => {
    if (text === shown) return;
    if (first.current) {
      first.current = false;
      setShown(text);
      return;
    }
    setLeaving(shown);
    setShown(text);
    const t = setTimeout(() => setLeaving(null), 220);
    return () => clearTimeout(t);
  }, [text, shown]);

  return (
    <span className="t-think" role="status" style={{ textAlign: "left" }}>
      <span className="t-think-sizer" aria-hidden="true">
        {shown.length >= "Writing answer".length ? shown : "Writing answer"}
      </span>
      {leaving !== null && (
        <span className="t-think-text is-exit" data-text={leaving} aria-hidden="true">
          {leaving}
        </span>
      )}
      <span key={shown} className="t-think-text is-enter" data-text={shown}>
        {shown}
      </span>
    </span>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";


export function StreamText({
  text,
  tickMs = 9,
  blurTail = 6,
  caret = true,
  onProgress,
  onDone,
}: {
  text: string;
  tickMs?: number;
  blurTail?: number;
  caret?: boolean;
  onProgress?: () => void;
  onDone?: () => void;
}) {
  const [count, setCount] = useState(0);
  const textRef = useRef(text);
  textRef.current = text;
  const onProgressRef = useRef(onProgress);
  const onDoneRef = useRef(onDone);
  onProgressRef.current = onProgress;
  onDoneRef.current = onDone;

  useEffect(() => {
    const id = setInterval(() => {
      const target = textRef.current.length;
      setCount((c) => {
        if (c >= target) return c;
        const remaining = target - c;

        const step = Math.max(2, Math.ceil(remaining / 40));
        return Math.min(c + step, target);
      });
      onProgressRef.current?.();
    }, tickMs);
    return () => clearInterval(id);
  }, [tickMs]);

  const streaming = count < text.length;
  const shown = text.slice(0, count);
  const split = streaming ? Math.max(0, shown.length - blurTail) : shown.length;
  if (!streaming) onDoneRef.current?.();

  return (
    <span style={{ whiteSpace: "pre-wrap", overflowWrap: "break-word" }}>
      {shown.slice(0, split)}
      {split < shown.length && <span className="stream-tail">{shown.slice(split)}</span>}
      {caret && <span aria-hidden className={`stream-caret${streaming ? " is-streaming" : ""}`} />}
    </span>
  );
}

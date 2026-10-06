"use client";







export function StreamText({ text, streaming }: { text: string; streaming: boolean }) {
  return (
    <span style={{ whiteSpace: "pre-wrap", overflowWrap: "break-word" }}>
      {text}
      {streaming ? <span aria-hidden className="stream-caret is-streaming" /> : null}
    </span>
  );
}

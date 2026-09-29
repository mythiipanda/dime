"use client";

export function StreamText({ text }: { text: string }) {
  return (
    <span style={{ whiteSpace: "pre-wrap", overflowWrap: "break-word" }}>
      {text}
    </span>
  );
}

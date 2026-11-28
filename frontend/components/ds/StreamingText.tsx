import type { ReactNode } from "react";

export function StreamingText({ children, streaming = false }: { children: ReactNode; streaming?: boolean }) {
  return <div className="text-[13px] leading-[1.75]" aria-busy={streaming}>{children}{streaming && <span className="stream-caret is-streaming" aria-hidden="true" />}</div>;
}

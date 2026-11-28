import type { ReactNode } from "react";

export function MintedLink({ link, copied, onCopy, note }: { link: string; copied: boolean; onCopy: (link: string) => void; note: ReactNode }) {
  return (
    <div className="w-full rounded-[7px] border border-line bg-field p-2">
      <p className="text-[11px] leading-[1.45] text-ink-2">{note}</p>
      <div className="mt-1.5 flex items-center gap-1.5">
        <input
          readOnly
          value={link}
          aria-label="share link"
          onFocus={(e) => e.currentTarget.select()}
          className="h-7 w-0 flex-1 rounded-[7px] border border-line bg-surface px-2 font-mono text-[11px] text-ink"
        />
        <button
          className="h-7 shrink-0 rounded-[7px] bg-[var(--accent)] px-2.5 text-[11.5px] font-medium text-white hover:opacity-90"
          onClick={() => onCopy(link)}
        >
          {copied ? "Copied" : "Copy link"}
        </button>
      </div>
    </div>
  );
}

export function copyToClipboard(text: string, done: () => void) {
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(done, () => {});
  }
}

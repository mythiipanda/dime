"use client";

import { Download } from "lucide-react";
import { Button } from "@/components/ds/Button";
import { memoToMarkdown, type MemoArtifactPayload } from "@/lib/dime-stream";

function fileSlug(title: string): string {
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return slug || "memo";
}

export default function ArtifactMemo({ artifact }: { artifact: MemoArtifactPayload }) {
  const download = () => {
    const blob = new Blob([memoToMarkdown(artifact)], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${fileSlug(artifact.title)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };
  return <div className="p-4">
    {artifact.subtitle && <p className="mb-4 text-xs text-ink-3">{artifact.subtitle}</p>}
    <div className="flex flex-col gap-4">
      {artifact.sections.map((section, i) => <section key={i} className="min-w-0">
        <h3 className="break-words text-[15px] font-medium tracking-tight text-ink">{section.heading}</h3>
        <p className="mt-1.5 whitespace-pre-wrap break-words text-[13px] leading-relaxed text-ink-2">{section.body}</p>
        {section.anchors && section.anchors.length > 0 && (
          <p className="mt-1 break-all text-xs text-ink-3">
            Cited rows: {[...new Set(section.anchors.map(a => `${a.ref} row ${a.row}`))].join(" · ")}
          </p>
        )}
      </section>)}
    </div>
    <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
      <p className="break-words text-xs text-ink-3">{artifact.footnote || "Section citations reference queried source rows."}</p>
      <Button size="sm" variant="quiet" aria-label={`Download ${artifact.title} as markdown`} onClick={download}>
        <Download size={14} aria-hidden="true" />Download memo
      </Button>
    </div>
  </div>;
}

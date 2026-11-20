import { jsPDF } from "jspdf";
import type { MemoArtifactPayload } from "./types";

export type MemoPdfStyle = "title" | "subtitle" | "heading" | "body" | "meta";

export interface MemoPdfLine {
  text: string;
  style: MemoPdfStyle;
}

export function memoPdfLines(artifact: MemoArtifactPayload): MemoPdfLine[] {
  const lines: MemoPdfLine[] = [{ text: artifact.title, style: "title" }];
  if (artifact.subtitle) lines.push({ text: artifact.subtitle, style: "subtitle" });
  for (const section of artifact.sections) {
    lines.push({ text: section.heading, style: "heading" });
    lines.push({ text: section.body, style: "body" });
    if (section.anchors?.length) {
      const refs = [...new Set(section.anchors.map(a => `${a.ref} row ${a.row}`))];
      lines.push({ text: `Cited rows: ${refs.join(" · ")}`, style: "meta" });
    }
  }
  if (artifact.footnote) lines.push({ text: artifact.footnote, style: "meta" });
  if (artifact.source) lines.push({ text: `Source: ${artifact.source}`, style: "meta" });
  return lines;
}

const STYLES: Record<MemoPdfStyle, { size: number; bold: boolean; gap: number }> = {
  title: { size: 16, bold: true, gap: 8 },
  subtitle: { size: 10, bold: false, gap: 8 },
  heading: { size: 12, bold: true, gap: 6 },
  body: { size: 10, bold: false, gap: 3 },
  meta: { size: 8, bold: false, gap: 8 },
};

export function memoToPdfBlob(artifact: MemoArtifactPayload): Blob {
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 54;
  const usable = pageWidth - margin * 2;
  let y = margin;
  for (const line of memoPdfLines(artifact)) {
    const style = STYLES[line.style];
    doc.setFontSize(style.size);
    doc.setFont("helvetica", line.style === "meta" ? "italic" : style.bold ? "bold" : "normal");
    const wrapped = doc.splitTextToSize(line.text, usable) as string[];
    for (const chunk of wrapped) {
      if (y + style.size > pageHeight - margin) {
        doc.addPage();
        y = margin;
      }
      doc.text(chunk, margin, y);
      y += style.size + 4;
    }
    y += style.gap;
  }
  return doc.output("blob");
}

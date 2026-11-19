"use client";

import CodeMirror, { EditorView, Prec, keymap } from "@uiw/react-codemirror";
import { sql } from "@codemirror/lang-sql";
import { python } from "@codemirror/lang-python";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags } from "@lezer/highlight";
import type { CellKind } from "../../lib/notebooks";

const theme = EditorView.theme({
  "&": { backgroundColor: "var(--surface)", color: "var(--ink-2)", fontSize: "12px" },
  ".cm-content": { fontFamily: "var(--font-mono), monospace", padding: "16px 0", caretColor: "var(--ink)" },
  ".cm-line": { padding: "0 20px 0 12px" },
  ".cm-gutters": { backgroundColor: "var(--surface)", color: "var(--ink-3)", border: "none", paddingLeft: "12px" },
  ".cm-activeLine, .cm-activeLineGutter": { backgroundColor: "var(--hover)" },
  "&.cm-focused": { outline: "none" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground": { background: "var(--hover-2)" },
  ".cm-cursor": { borderLeftColor: "var(--ink)" },
});
const languages = { sql: sql(), python: python(), markdown: [] };
const syntax = syntaxHighlighting(HighlightStyle.define([
  { tag: tags.keyword, color: "var(--accent)" },
  { tag: [tags.string, tags.number, tags.bool], color: "var(--green)" },
  { tag: tags.comment, color: "var(--ink-3)" },
  { tag: [tags.function(tags.variableName), tags.typeName], color: "var(--ink)" },
]));
export default function CellEditor({ source, kind, label, onChange, onRun, disabled }: { source: string; kind: CellKind; label: string; onChange: (value: string) => void; onRun: () => void; disabled: boolean }) {
  return <CodeMirror value={source} aria-label={label} minHeight="88px" maxHeight="440px" theme={theme} editable={!disabled} extensions={[languages[kind], syntax, EditorView.lineWrapping, Prec.highest(keymap.of([{ key: "Shift-Enter", stopPropagation: true, run: () => { onRun(); return true; } }]))]} basicSetup={{ foldGutter: false, highlightActiveLine: true }} onChange={(value) => { if (value.length <= 100000) onChange(value); }} />;
}

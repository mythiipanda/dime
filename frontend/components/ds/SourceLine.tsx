type SourceLineProps = {
  table?: string | null;
  asOf?: string | null;
  extra?: string;
  className?: string;
};

export function SourceLine({ table, asOf, extra, className = "" }: SourceLineProps) {
  return (
    <p className={`mt-4 border-t border-line pt-3 text-[11px] text-ink-2 ${className}`}>
      {table ?? "source unknown"}{asOf ? ` · as of ${String(asOf).slice(0, 10)}` : ""}{extra ? ` · ${extra}` : ""}
    </p>
  );
}

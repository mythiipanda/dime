type DataStateProps = {
  tone: "error" | "absent";
  label: string;
  detail?: string;
  className?: string;
};

export function DataState({ tone, label, detail, className = "" }: DataStateProps) {
  return (
    <div role={tone === "error" ? "alert" : undefined} className={`py-3 ${className}`}>
      <p className={`text-[12.5px] font-medium ${tone === "error" ? "text-red" : "text-ink-2"}`}>{label}</p>
      {detail ? <p className="mt-0.5 text-[12px] text-ink-3">{detail}</p> : null}
    </div>
  );
}

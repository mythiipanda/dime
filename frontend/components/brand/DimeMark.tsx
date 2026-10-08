export function DimeMark({
  size = 20,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <circle cx="12" cy="12" r="9.25" stroke="currentColor" strokeWidth="1.9" />
      <path
        d="M12 2.75v18.5"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function DimeLockup({
  size = 20,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <DimeMark size={size} className="shrink-0 text-ink" />
      <span className="text-[14px] font-medium tracking-[-0.01em] text-ink-2">
        dime
      </span>
    </span>
  );
}
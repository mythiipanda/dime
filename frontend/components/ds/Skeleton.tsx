export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-[6px] bg-field ${className}`} aria-hidden="true" />;
}

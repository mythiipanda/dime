import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";

export function QuietDetails({ label, children, id }: { label: ReactNode; children: ReactNode; id?: string }) {
  return (
    <details id={id} className="group mt-3">
      <summary className="-mx-1.5 flex w-fit cursor-pointer list-none items-center gap-1.5 rounded-control px-1.5 py-1 text-[12px] font-medium text-ink-2 transition-colors duration-100 hover:bg-hover-2 [&::-webkit-details-marker]:hidden">
        <ChevronDown width={11} height={11} strokeWidth={2.2} className="-rotate-90 text-ink-3 transition-transform duration-150 group-open:rotate-0" />
        {label}
      </summary>
      <div className="mt-1 ml-[5px] border-l border-line pl-4 pb-1">
        {children}
      </div>
    </details>
  );
}

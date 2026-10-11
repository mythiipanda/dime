import Link from "next/link";
import { ArrowRight, type LucideIcon } from "lucide-react";
import WorkspaceShell from "@/components/site/WorkspaceShell";

export default function SurfaceEmptyState({
  name,
  eyebrow,
  description,
  action,
  href,
  icon: Icon,
}: {
  name: string;
  eyebrow: string;
  description: string;
  action: string;
  href: string;
  icon: LucideIcon;
}) {
  return (
    <WorkspaceShell active={name}>
      <main className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto bg-page px-6 py-12">
        <section className="w-full max-w-[540px]">
          <div className="mb-8 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.12em] text-ink-3">
            <span>Workspace</span><span aria-hidden="true">/</span><span className="text-ink-2">{name}</span>
          </div>
          <div className="relative overflow-hidden rounded-[16px] border border-line bg-surface shadow-card">
            <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-accent/0 via-accent/70 to-accent/0" />
            <div className="p-8 sm:p-10">
              <div className="mb-7 flex size-12 items-center justify-center rounded-[13px] border border-line bg-inset text-accent-ink shadow-hairline">
                <Icon size={21} strokeWidth={1.7} />
              </div>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-accent-ink">{eyebrow}</p>
              <h1 className="text-[27px] font-semibold tracking-[-0.04em] text-ink">{name}</h1>
              <p className="mt-2 max-w-[390px] text-[14px] leading-6 text-ink-2">{description}</p>
              <Link href={href} className="mt-7 inline-flex h-10 items-center gap-2 rounded-[9px] bg-ink px-4 text-[12px] font-medium text-page transition-[transform,opacity] duration-150 hover:opacity-90 active:scale-[0.98]">
                {action}<ArrowRight size={14} />
              </Link>
            </div>
            <div aria-hidden="true" className="flex h-10 items-center justify-between border-t border-line bg-inset px-8 font-mono text-[9px] text-ink-3 sm:px-10">
              <span>DIME / ANALYST WORKSPACE</span><span>01 — 08</span>
            </div>
          </div>
        </section>
      </main>
    </WorkspaceShell>
  );
}

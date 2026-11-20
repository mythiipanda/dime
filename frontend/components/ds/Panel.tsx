import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export function Surface({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("min-w-0 rounded-xl border border-line bg-surface p-5", className)}>{children}</section>;
}

export function Panel({ title, description, actions, children, className }: { title: string; description?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return <Surface className={className}>
    <header className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-[13px] font-medium text-ink">{title}</h2>{description && <p className="mt-1 text-[12px] leading-relaxed text-ink-3">{description}</p>}</div>{actions}</header>
    {children}
  </Surface>;
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <header className="mb-8 flex flex-wrap items-end justify-between gap-4"><div><p className="mb-3 text-[10px] font-medium uppercase tracking-widest text-ink-3">{eyebrow}</p><h1 className="text-[28px] font-medium tracking-tight text-ink">{title}</h1><p className="mt-2 max-w-xl text-[13px] leading-relaxed text-ink-2">{description}</p></div>{actions}</header>;
}
=======
import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export function Surface({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("ds-surface", className)}>{children}</section>;
}

export function Panel({ title, description, actions, children, className }: { title: string; description?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return <Surface className={className}>
    <header className="ds-panel-header"><div className="min-w-0"><h2 className="ds-panel-title">{title}</h2>{description && <p className="ds-panel-description">{description}</p>}</div>{actions}</header>
    {children}
  </Surface>;
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <header className="ds-page-header"><div className="min-w-0"><p className="ds-eyebrow">{eyebrow}</p><h1 className="ds-page-title">{title}</h1><p className="ds-page-description">{description}</p></div>{actions}</header>;
}
>>>>>>> origin/dev

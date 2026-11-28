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

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return <header className="ds-page-header"><div className="min-w-0">{eyebrow ? <p className="ds-eyebrow">{eyebrow}</p> : null}<h1 className="ds-page-title">{title}</h1>{description ? <p className="ds-page-description">{description}</p> : null}</div>{actions}</header>;
}

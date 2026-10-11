"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Archive, BookOpen, CalendarDays, Compass, History, MessageSquare, Trophy, WandSparkles } from "lucide-react";
import type { ReactNode } from "react";
import { isActiveDestination, normalizeActive } from "@/lib/shell";

const destinations = [
  { name: "Today", href: "/today", icon: CalendarDays },
  { name: "Chat", href: "/", icon: MessageSquare },
  { name: "Notebook", href: "/notebook", icon: BookOpen },
  { name: "Warehouse", href: "/warehouse", icon: Archive },
  { name: "Skills", href: "/skills", icon: WandSparkles },
  { name: "History", href: "/history", icon: History },
  { name: "Explore", href: "/explore", icon: Compass },
  { name: "Standings", href: "/standings", icon: Trophy },
];

export function resolveSelected(active?: string, pathname?: string) {
  const fallback = destinations.find((destination) => destination.href === pathname)?.name ?? "";
  return normalizeActive(active ?? fallback);
}

export default function WorkspaceShell({ children, active }: { children: ReactNode; active?: string }) {
  const pathname = usePathname();
  const selected = resolveSelected(active, pathname ?? undefined);

  return (
    <div className="flex h-[100dvh] gap-2.5 overflow-hidden bg-canvas p-2.5 text-ink">
      <aside aria-label="Workspace navigation" className="flex w-[48px] shrink-0 flex-col rounded-[14px] border border-line bg-page px-1 py-3 sm:w-[216px] sm:px-2">
        <div className="mb-6 flex h-9 items-center justify-center gap-2 px-1 sm:justify-start sm:px-2">
          <span className="flex size-6 items-center justify-center rounded-[7px] bg-ink text-[11px] font-semibold text-page">d</span>
          <span className="hidden text-[14px] font-semibold tracking-[-0.03em] sm:inline">dime</span>
          <span className="ml-auto hidden rounded-md border border-line px-1.5 py-0.5 font-mono text-[9px] text-ink-3 sm:inline">NBA</span>
        </div>
        <p className="mb-2 hidden px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-3 sm:block">Workspace</p>
        <nav className="flex flex-col gap-1">
          {destinations.map(({ name, href, icon: Icon }) => {
            const isActive = isActiveDestination(name, selected);
            return (
              <Link key={name} href={href} aria-current={isActive ? "page" : undefined}
                aria-label={name}
                title={name}
                className={`relative flex h-9 items-center justify-center gap-2.5 rounded-[8px] px-0 text-[13px] font-medium transition-[background-color,color,transform] duration-150 hover:bg-hover active:scale-[0.98] sm:justify-start sm:px-2.5 ${isActive ? "bg-hover-2 text-ink" : "text-ink-2"}`}>
                <Icon size={16} strokeWidth={1.8} />
                <span className="hidden sm:inline">{name}</span>
                {isActive && <span className="absolute right-1 top-1 size-1.5 rounded-full bg-accent sm:static sm:ml-auto" />}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto border-t border-line px-1 pt-3 sm:px-2">
          <div className="flex items-center justify-center gap-2 sm:justify-start">
            <span className="flex size-7 items-center justify-center rounded-full bg-accent-tint text-[11px] font-semibold text-accent-ink">T</span>
            <div className="hidden min-w-0 sm:block"><p className="text-[12px] font-medium">Tony</p><p className="text-[10px] text-ink-3">Analyst workspace</p></div>
          </div>
        </div>
      </aside>
      <div className="workspace-content flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[14px]">{children}</div>
      <style jsx global>{`.workspace-content main aside[aria-label="dime navigation"] { display: none; }`}</style>
    </div>
  );
}

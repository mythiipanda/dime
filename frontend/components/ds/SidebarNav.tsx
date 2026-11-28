"use client";

import { Fragment, useState, type ReactNode } from "react";
import { PanelLeftClose, PanelLeftOpen, Pencil, Search } from "lucide-react";
import { BasketballIcon } from "@/components/ds/BasketballIcon";

export interface SidebarItem { id: string; label: string; icon: ReactNode; href?: string; group?: string }
export interface SidebarRecent { id: string; label: string }

export function SidebarNav({ workspace, items, activeNav, recents, activeThread, onNavigate, onNewChat, onPick, footer }: {
  workspace: string; items: SidebarItem[]; activeNav: string; recents: SidebarRecent[]; activeThread?: string | null;
  onNavigate: (id: string) => void; onNewChat: () => void; onPick: (id: string) => void; footer?: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  return <aside className={`dime-sidebar${collapsed ? " is-collapsed" : ""}`} aria-label="Workspace navigation">
    <div className="flex h-11 items-center justify-between px-2">
      <div className="flex items-center gap-2 text-[13px] font-medium"><BasketballIcon size={17} /><span className="sidebar-copy">{workspace}</span></div>
      <button className="icon-button sidebar-copy" aria-label="Collapse sidebar" onClick={() => setCollapsed(true)}><PanelLeftClose width={16} height={16} /></button>
    </div>
    {collapsed && <button className="icon-button mx-auto mb-2" aria-label="Expand sidebar" onClick={() => setCollapsed(false)}><PanelLeftOpen width={16} height={16} /></button>}
    <button className="sidebar-row mt-2 mb-3" onClick={onNewChat} title="New chat"><Pencil width={17} height={17} /><span className="sidebar-copy">New chat</span></button>
    <nav className="flex flex-col gap-0.5" aria-label="Main navigation">
      {items.map((item, index) => <Fragment key={item.id}>
        {item.group && item.group !== items[index - 1]?.group && <p className="sidebar-copy mt-5 mb-1 px-2 text-[10px] uppercase tracking-widest text-ink-3">{item.group}</p>}
        {item.href ? <a className="sidebar-row" href={item.href} title={item.label}>{item.icon}<span className="sidebar-copy">{item.label}</span></a> : <button className="sidebar-row" title={item.label} aria-current={activeNav === item.id ? "page" : undefined} onClick={() => onNavigate(item.id)}>{item.icon}<span className="sidebar-copy">{item.label}</span></button>}
      </Fragment>)}
    </nav>
    <div className="sidebar-copy mt-8 flex min-h-0 flex-1 flex-col">
      <label className="mb-2 flex items-center gap-2 px-2 text-[11px] text-ink-3"><span>Chats</span><Search width={12} height={12} className="ml-auto" /><input aria-label="Search chats" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} className="w-20 min-w-0 bg-transparent text-ink-2 outline-none placeholder:text-ink-3" /></label>
      <div className="min-h-0 overflow-y-auto">
        {recents.filter((r) => r.label.toLowerCase().includes(search.toLowerCase())).map((r) => <button key={r.id} className="sidebar-row" aria-current={activeThread === r.id && activeNav === "chat" ? "page" : undefined} onClick={() => onPick(r.id)}><span className="truncate text-[12px]">{r.label}</span></button>)}
        {!recents.length && (
          <div className="px-2 py-2">
            <p className="text-[11.5px] leading-relaxed text-ink-2">Ask about a team, a player, or a trade. Every answer cites its source.</p>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-3">Your conversations will live here.</p>
          </div>
        )}
        {!!recents.length && !recents.some((r) => r.label.toLowerCase().includes(search.toLowerCase())) && <p className="px-2 py-2 text-[11px] text-ink-3">No matching chats.</p>}
      </div>
    </div>
    <div className="sidebar-copy mt-auto border-t border-line px-2 pt-4 pb-14">{footer}</div>
  </aside>;
}

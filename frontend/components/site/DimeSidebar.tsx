"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { IconArrowLeftRight } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconArrowLeftRight";
import { IconArchive } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconArchive";
import { IconArrowsRepeatRightLeft } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconArrowsRepeatRightLeft";
import { IconBookmark } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconBookmark";
import { IconCalendar1 } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconCalendar1";
import { IconChatBubble7 } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconChatBubble7";
import { IconChevronDownSmall } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconChevronDownSmall";
import { IconCompassRound } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconCompassRound";
import { IconCrossSmall } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconCrossSmall";
import { IconEditBig } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconEditBig";
import { IconMagnifyingGlass } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconMagnifyingGlass";
import { IconSidebarLeftArrow } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconSidebarLeftArrow";
import { IconTarget } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconTarget";
import { IconTrophy } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconTrophy";
import { IconUserGroup } from "@central-icons-react/round-outlined-radius-2-stroke-2/IconUserGroup";
import GlideMenu from "@/components/primitives/GlideMenu";

const SIDEBAR_MOTION = {
  expandedWidth: 224,
  collapsedWidth: 52,
  duration: 280,
  copyDuration: 180,
  copyOffset: 8,
  easing: "cubic-bezier(0.16, 1, 0.3, 1)",
};

const CHAT_SEARCH_MOTION = {
  duration: 180,
  closedWidth: 28,
  easing: "cubic-bezier(0.16, 1, 0.3, 1)",
};

function GlideGroup({ children }: { children: ReactNode }) {
  return (
    <GlideMenu
      rowSelector="[data-row]"
      highlightClassName="sidebar-glide-highlight rounded-[7px] bg-hover-2"
      className="group/glide flex flex-col gap-px"
    >
      {children}
    </GlideMenu>
  );
}

function RailButton({
  icon,
  label,
  active = false,
  onClick,
}: {
  icon?: ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      data-row
      type="button"
      onClick={onClick}
      className={`sidebar-row relative z-10 mx-2 flex h-8 items-center rounded-[8px] px-2 text-left
        transition-[width,background-color,color,transform] duration-150 active:scale-[0.98]
        ${active ? "bg-hover-2 group-hover/glide:bg-transparent" : ""}`}
    >
      {icon && (
        <span className={`flex size-5 shrink-0 items-center justify-center ${active ? "text-ink" : "text-ink-2"}`}>
          {icon}
        </span>
      )}
      <span className={`sidebar-copy min-w-0 flex-1 truncate text-[14px] font-medium ${icon ? "ml-1.5" : ""} ${active ? "text-ink" : "text-ink-2"}`}>
        {label}
      </span>
    </button>
  );
}

const NAV_GROUPS: { key: string; label: string; icon: ReactNode }[][] = [
  [
    { key: "chat", label: "Chat", icon: <IconChatBubble7 size={18} /> },
    { key: "tonight", label: "Tonight", icon: <IconCalendar1 size={18} /> },
    { key: "explore", label: "Explore", icon: <IconCompassRound size={18} /> },
  ],
  [
    { key: "matchups", label: "Matchups", icon: <IconArrowsRepeatRightLeft size={18} /> },
    { key: "lineups", label: "Lineups", icon: <IconUserGroup size={18} /> },
    { key: "trades", label: "Trades", icon: <IconArrowLeftRight size={18} /> },
    { key: "awards", label: "Awards", icon: <IconTrophy size={18} /> },
    { key: "props", label: "Props", icon: <IconTarget size={18} /> },
  ],
  [
    { key: "saved", label: "Saved", icon: <IconBookmark size={18} /> },
    { key: "warehouse", label: "Warehouse", icon: <IconArchive size={18} /> },
  ],
];

const RECENTS = [
  { id: "sga-luka", label: "SGA vs Luka — Oct 6" },
  { id: "thunder-bench", label: "Thunder bench minutes" },
  { id: "luka-onoff", label: "Luka on/off splits" },
  { id: "mvp-ladder", label: "MVP ladder — week 2" },
  { id: "tonight-slate", label: "Tonight's slate" },
];

export default function DimeSidebar({
  className = "",
  activeNav,
  onNavChange,
  onNewAnalysis,
  forceVisible = false,
  onRequestClose,
}: {
  className?: string;
  activeNav: string;
  onNavChange: (key: string) => void;
  onNewAnalysis?: () => void;
  forceVisible?: boolean;
  onRequestClose?: () => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [activeTitle, setActiveTitle] = useState<string | null>("SGA vs Luka — Oct 6");
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const overlay = onRequestClose !== undefined;

  const visibleRecents = RECENTS.filter((item) => item.label.toLowerCase().includes(query.trim().toLowerCase()));

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus();
  }, [searchOpen]);

  useEffect(() => {
    const onCollapse = () => {
      if (overlay) onRequestClose();
      else collapse();
    };
    window.addEventListener("dime:collapse-sidebar", onCollapse);
    return () => window.removeEventListener("dime:collapse-sidebar", onCollapse);
  }, [overlay, onRequestClose]);

  const collapse = () => {
    setCollapsed(true);
    setSearchOpen(false);
    setQuery("");
  };

  return (
    <aside
      data-sidebar-collapsed={collapsed}
      aria-label="Dime navigation"
      className={`relative flex h-full shrink-0 overflow-hidden transition-[width] ${forceVisible ? "" : "max-lg:hidden"} ${className}`}
      style={{
        width: collapsed ? SIDEBAR_MOTION.collapsedWidth : SIDEBAR_MOTION.expandedWidth,
        transitionDuration: `${SIDEBAR_MOTION.duration}ms`,
        transitionTimingFunction: SIDEBAR_MOTION.easing,
        "--sidebar-copy-duration": `${SIDEBAR_MOTION.copyDuration}ms`,
        "--sidebar-copy-offset": `${SIDEBAR_MOTION.copyOffset}px`,
        "--sidebar-easing": SIDEBAR_MOTION.easing,
      } as CSSProperties}
    >
      <div className="flex min-h-0 w-[224px] shrink-0 flex-col">
        <div className="relative mb-2.5 h-10 shrink-0">
          <div className="sidebar-workspace-control absolute left-2 top-1 flex h-8 w-[164px] items-center px-2">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-[7px] bg-ink text-[11px] font-semibold text-surface">
              D
            </span>
            <span className="sidebar-copy ml-1.5 min-w-0 flex-1 truncate text-[14px] font-medium text-ink-2">
              Dime
            </span>
          </div>

          <button
            type="button"
            aria-label={overlay ? "Close navigation" : "Collapse sidebar"}
            aria-hidden={collapsed}
            tabIndex={collapsed ? -1 : 0}
            onClick={() => {
              if (overlay) onRequestClose();
              else collapse();
            }}
            className="sidebar-collapse-control absolute right-2 top-1 flex size-8 items-center justify-center rounded-[8px] text-ink-3 transition-[opacity,background-color,color] duration-150 hover:bg-hover-2 hover:text-ink"
          >
            <IconSidebarLeftArrow size={18} />
          </button>
          <button
            type="button"
            aria-label="Expand sidebar"
            aria-hidden={!collapsed}
            tabIndex={collapsed ? 0 : -1}
            onClick={() => setCollapsed(false)}
            className="sidebar-expand-control absolute left-2 top-0.5 flex size-9 items-center justify-center rounded-[8px] text-ink-3 transition-[opacity,background-color,color] duration-150 hover:bg-hover-2 hover:text-ink"
          >
            <IconSidebarLeftArrow size={18} className="rotate-180" />
          </button>
        </div>

        <GlideGroup>
          <RailButton
            icon={<IconEditBig size={18} />}
            label="New analysis"
            onClick={() => {
              onNavChange("chat");
              setActiveTitle(null);
              onNewAnalysis?.();
            }}
          />
        </GlideGroup>

        {NAV_GROUPS.map((group, gi) => (
          <div key={gi} className="mt-3">
            <GlideGroup>
              {group.map((item) => (
                <RailButton
                  key={item.key}
                  icon={item.icon}
                  label={item.label}
                  active={activeNav === item.key}
                  onClick={() => onNavChange(item.key)}
                />
              ))}
            </GlideGroup>
          </div>
        ))}

        <div className="mt-3 min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <div className="sidebar-copy relative mx-2 mb-1 h-8">
            <div
              aria-hidden={searchOpen}
              className={`absolute inset-0 flex items-center gap-1.5 px-2 text-[12.5px] font-medium text-ink-3 transition-[opacity,transform] ${searchOpen ? "pointer-events-none -translate-x-1 opacity-0" : "translate-x-0 opacity-100"}`}
              style={{ transitionDuration: `${CHAT_SEARCH_MOTION.duration}ms`, transitionTimingFunction: CHAT_SEARCH_MOTION.easing }}
            >
              <IconChevronDownSmall size={16} />
              <span>Analyses</span>
            </div>

            <button
              type="button"
              aria-label="Search analyses"
              aria-expanded={searchOpen}
              onClick={() => setSearchOpen(true)}
              className={`absolute right-0 top-0 z-10 flex size-8 items-center justify-center rounded-[8px] text-ink-3 transition-[opacity,background-color,color,transform] hover:bg-hover-2 hover:text-ink active:scale-[0.96] ${searchOpen ? "pointer-events-none opacity-0" : "opacity-100"}`}
              style={{ transitionDuration: `${CHAT_SEARCH_MOTION.duration}ms` }}
            >
              <IconMagnifyingGlass size={16} />
            </button>

            <div
              className={`absolute right-0 top-0 z-20 flex h-8 items-center overflow-hidden rounded-[8px] bg-field text-ink-3 shadow-hairline transition-[width,opacity] focus-within:text-ink-2 ${searchOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"}`}
              style={{
                width: searchOpen ? "100%" : CHAT_SEARCH_MOTION.closedWidth,
                transitionDuration: `${CHAT_SEARCH_MOTION.duration}ms`,
                transitionTimingFunction: CHAT_SEARCH_MOTION.easing,
              }}
            >
              <span className="ml-2 flex shrink-0 items-center justify-center">
                <IconMagnifyingGlass size={15} />
              </span>
              <input
                ref={searchRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setSearchOpen(false);
                    setQuery("");
                  }
                }}
                placeholder="Search analyses"
                aria-label="Search analyses"
                className="ml-1.5 min-w-0 flex-1 bg-transparent text-[13px] font-medium text-ink outline-none placeholder:text-ink-3"
              />
              <button
                type="button"
                aria-label="Close analysis search"
                onClick={() => {
                  setSearchOpen(false);
                  setQuery("");
                }}
                className="flex size-8 shrink-0 items-center justify-center rounded-[8px] text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-hover-2 hover:text-ink active:scale-[0.96]"
              >
                <IconCrossSmall size={16} />
              </button>
            </div>
          </div>

          <GlideGroup>
            {visibleRecents.map((item) => (
              <RailButton
                key={item.id}
                label={item.label}
                active={item.label === activeTitle}
                onClick={() => {
                  onNavChange("chat");
                  setActiveTitle(item.label);
                }}
              />
            ))}
            {query && visibleRecents.length === 0 && (
              <div className="sidebar-copy mx-2 px-2 py-2 text-[12.5px] text-ink-3">No analyses found</div>
            )}
          </GlideGroup>
        </div>

        <div className="sidebar-copy mx-2 mt-3 w-[208px] border-t border-line pt-3">
          <div className="flex h-8 w-full items-center gap-2 px-2 text-[12.5px] font-medium text-ink">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-line-strong text-[10px] font-semibold text-ink-2">
              T
            </span>
            <span className="min-w-0 flex-1 truncate text-left">Tony</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

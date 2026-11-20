"use client";

import type { RefObject } from "react";
import DimeSidebar from "@/components/site/DimeSidebar";
import type { ViewKey } from "./types";

export function MobileTopBar({
  menuBtnRef,
  mobileNavOpen,
  onOpenNav,
  onNewAnalysis,
}: {
  menuBtnRef: RefObject<HTMLButtonElement | null>;
  mobileNavOpen: boolean;
  onOpenNav: () => void;
  onNewAnalysis: () => void;
}) {
  return (
    <div className="flex h-12 shrink-0 items-center gap-1 rounded-[14px] border border-line bg-page px-1 lg:hidden">
      <button
        ref={menuBtnRef}
        type="button"
        aria-label="Open navigation"
        aria-expanded={mobileNavOpen}
        onClick={onOpenNav}
        className="flex size-11 shrink-0 touch-manipulation select-none items-center justify-center rounded-[8px] text-ink-2 transition-[background-color,color,transform] duration-150 hover:bg-hover-2 hover:text-ink active:scale-[0.96]"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          aria-hidden
        >
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </button>
      <span className="min-w-0 flex-1 truncate px-1 text-[14px] font-medium text-ink">Dime</span>
      <button
        type="button"
        aria-label="New analysis"
        onClick={onNewAnalysis}
        className="flex size-11 shrink-0 touch-manipulation select-none items-center justify-center rounded-[8px] text-ink-2 transition-[background-color,color,transform] duration-150 hover:bg-hover-2 hover:text-ink active:scale-[0.96]"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          aria-hidden
        >
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>
    </div>
  );
}

export function MobileNavDrawer({
  open,
  shown,
  sheetRef,
  activeView,
  onClose,
  onSelectView,
  onNewAnalysis,
}: {
  open: boolean;
  shown: boolean;
  sheetRef: RefObject<HTMLDivElement | null>;
  activeView: "chat" | ViewKey;
  onClose: () => void;
  onSelectView: (view: "chat" | ViewKey) => void;
  onNewAnalysis: () => void;
}) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Dime navigation"
      className="fixed inset-0 z-50 lg:hidden"
    >
      <button
        type="button"
        aria-label="Close navigation"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-black/45 transition-opacity duration-200 ease-out"
        style={{ opacity: shown ? 1 : 0 }}
      />
      <div
        ref={sheetRef}
        className="absolute left-0 top-0 h-[100dvh] w-[300px] max-w-[85vw] border-r border-line bg-page pt-2 shadow-overlay transition-transform duration-200 ease-out [&_[data-row]]:min-h-[44px] [&_.sidebar-collapse-control]:size-11"
        style={{ transform: shown ? "translateX(0)" : "translateX(-102%)" }}
      >
        <DimeSidebar
          forceVisible
          activeNav={activeView}
          onRequestClose={onClose}
          onNavChange={(key: string) => {
            onSelectView(key as "chat" | ViewKey);
            onClose();
          }}
          onNewAnalysis={() => {
            onNewAnalysis();
            onClose();
          }}
        />
      </div>
    </div>
  );
}

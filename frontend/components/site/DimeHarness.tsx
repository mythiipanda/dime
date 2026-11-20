"use client";

import type { ComponentType } from "react";
import AwardsView from "@/components/dime/views/AwardsView";
import ExploreView from "@/components/dime/views/ExploreView";
import LineupsView from "@/components/dime/views/LineupsView";
import MatchupsView from "@/components/dime/views/MatchupsView";
import PropsView from "@/components/dime/views/PropsView";
import SavedView from "@/components/dime/views/SavedView";
import TonightView from "@/components/dime/views/TonightView";
import TradesView from "@/components/dime/views/TradesView";
import WarehouseView from "@/components/dime/views/WarehouseView";
import DimeCommandPalette from "@/components/site/DimeCommandPalette";
import DimeSidebar from "@/components/site/DimeSidebar";
import { AssistantTurn, Ico, LiveAssistant } from "./harness/AnswerView";
import { DimeComposer } from "./harness/DimeComposer";
import { MobileNavDrawer, MobileTopBar } from "./harness/MobileNav";
import { ReferenceExample } from "./harness/ReferenceExample";
import { FADE_UP, type ViewKey } from "./harness/types";
import { useDimeChat } from "./harness/useDimeChat";

export type { LiveRun } from "./harness/types";
export { assistantMessageFromSnapshot } from "./harness/types";
export { ArtifactBody, artifactToCopyText, ProvenancePanel } from "./harness/ArtifactsView";
export {
  AnswerBlocks,
  AnswerVerification,
  AssistantTurn,
  LiveAssistant,
} from "./harness/AnswerView";

const VIEWS: Record<ViewKey, ComponentType> = {
  tonight: TonightView,
  explore: ExploreView,
  matchups: MatchupsView,
  lineups: LineupsView,
  trades: TradesView,
  awards: AwardsView,
  props: PropsView,
  saved: SavedView,
  warehouse: WarehouseView,
};

const SHELLED_VIEWS: ReadonlySet<ViewKey> = new Set(["props", "saved", "warehouse"]);
const FLEX_VIEWS: ReadonlySet<ViewKey> = new Set(["lineups", "trades", "awards"]);

function renderView(key: ViewKey) {
  const View = VIEWS[key];
  if (SHELLED_VIEWS.has(key)) return <View key={key} />;
  if (FLEX_VIEWS.has(key)) {
    return (
      <div
        key={key}
        className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[14px] border border-line bg-page"
      >
        <View />
      </div>
    );
  }
  return (
    <div
      key={key}
      className="min-h-0 min-w-0 flex-1 overflow-y-auto rounded-[14px] border border-line bg-page"
    >
      <View />
    </div>
  );
}

export default function DimeHarness() {
  const chat = useDimeChat();
  const pickFollowUp = (f: string) => {
    chat.submit(f);
  };

  return (
    <main className="flex h-[100dvh] gap-0 overscroll-none bg-canvas p-2.5 text-ink lg:pl-0">
      <DimeSidebar
        activeNav={chat.activeView}
        onNavChange={(key: string) => chat.setActiveView(key as "chat" | ViewKey)}
        onNewAnalysis={() => {
          chat.setActiveView("chat");
          chat.addTab();
        }}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-2.5">
        <MobileTopBar
          menuBtnRef={chat.menuBtnRef}
          mobileNavOpen={chat.mobileNavOpen}
          onOpenNav={chat.openMobileNav}
          onNewAnalysis={() => {
            chat.setActiveView("chat");
            chat.addTab();
          }}
        />
        <div className="flex min-h-0 flex-1 gap-2.5">
          {chat.activeView === "chat" ? (
            <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[14px] border border-line bg-page">
              <div className="flex h-11 shrink-0 items-center gap-1 overflow-x-auto border-b border-line px-2">
                {chat.tabs.map((t) => (
                  <span
                    key={t.id}
                    className={`flex h-7 shrink-0 items-center gap-1 rounded-[7px] pr-1 transition-[background-color,color] duration-150 ${
                      chat.activeTab === t.id
                        ? "bg-hover text-ink"
                        : "text-ink-3 hover:bg-hover hover:text-ink-2"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => chat.setActiveTab(t.id)}
                      className="flex h-full max-w-[180px] items-center truncate px-2 text-[12.5px] font-medium transition-transform duration-150 active:scale-[0.97]"
                    >
                      {t.label}
                    </button>
                    {chat.tabs.length > 1 && (
                      <button
                        type="button"
                        aria-label={`Close ${t.label}`}
                        onClick={() => chat.closeTab(t.id)}
                        className="mr-0.5 flex size-6 shrink-0 items-center justify-center rounded-[5px] text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-page hover:text-ink active:scale-[0.9]"
                      >
                        <Ico d={<path d="M6 6l12 12M18 6L6 18" />} size={11} />
                      </button>
                    )}
                  </span>
                ))}
                <button
                  type="button"
                  aria-label="New tab"
                  onClick={chat.addTab}
                  className="flex size-7 shrink-0 items-center justify-center rounded-[7px] text-ink-3 transition-[background-color,color,transform] duration-150 hover:bg-hover hover:text-ink active:scale-[0.94]"
                >
                  <Ico d={<path d="M12 5v14M5 12h14" />} size={14} />
                </button>
              </div>

              <div ref={chat.scrollRef} className="min-h-0 flex-1 overflow-y-auto">
                <div className="mx-auto w-full max-w-[760px] px-4 py-8 sm:px-8">
                  {chat.showReference && <ReferenceExample onFollowUp={pickFollowUp} />}
                  {chat.messages.map((m, i) =>
                    m.role === "user" ? (
                      <div
                        key={i}
                        className="mt-4 flex justify-end pl-10 sm:pl-24"
                        style={{ animation: FADE_UP }}
                      >
                        <div className="rounded-xl bg-field px-3.5 py-2 text-[13px] leading-relaxed text-ink shadow-hairline">
                          {m.text}
                        </div>
                      </div>
                    ) : (
                      <AssistantTurn
                        key={i}
                        text={m.text}
                        artifacts={m.artifacts}
                        suggestions={m.suggestions}
                        carry={m.carry}
                        failure={m.failure}
                        onFollowUp={pickFollowUp}
                      />
                    ),
                  )}
                  {chat.live && <LiveAssistant live={chat.live} />}
                  <div className="h-6" />
                </div>
              </div>

              <div className="shrink-0 px-4 pb-4">
                <div className="mx-auto max-w-[760px]">
                  <DimeComposer
                    draft={chat.draft}
                    setDraft={chat.setDraft}
                    onSubmit={() => chat.submit()}
                    inputRef={chat.inputRef}
                    modelOptions={chat.modelOptions}
                    model={chat.model}
                    setModel={chat.setModel}
                  />
                </div>
              </div>
            </section>
          ) : (
            renderView(chat.activeView)
          )}
        </div>
      </div>
      <MobileNavDrawer
        open={chat.mobileNavOpen}
        shown={chat.mobileNavShown}
        sheetRef={chat.sheetRef}
        activeView={chat.activeView}
        onClose={chat.closeMobileNav}
        onSelectView={chat.setActiveView}
        onNewAnalysis={() => {
          chat.setActiveView("chat");
          chat.addTab();
        }}
      />
      <DimeCommandPalette
        open={chat.paletteOpen}
        entries={chat.paletteEntries}
        onClose={() => chat.setPaletteOpen(false)}
      />
    </main>
  );
}

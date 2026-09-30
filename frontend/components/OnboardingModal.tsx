"use client";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

interface Props {
  onFinish: () => void;
  onSelectPrompt: (q: string) => void;
}

const PROMPTS = [
  "Who's the most clutch player?",
  "Compare Luka and SGA",
  "Show me rising stars",
];

export default function OnboardingModal({ onFinish, onSelectPrompt }: Props) {
  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onFinish();
      }}
    >
      <DialogContent
        aria-label="Welcome to Dime"
        showCloseButton={false}
        className="card onboard-panel"
        style={{ width: 460, maxWidth: "92vw", padding: 24, gap: 0 }}
      >
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
          <DialogTitle className="display" style={{ fontSize: 24, fontWeight: 400, color: "var(--color-ink-black)" }}>
            Meet Dime
          </DialogTitle>
          <button
            type="button"
            onClick={onFinish}
            style={{ background: "transparent", border: "none", fontSize: 12, color: "var(--color-warm-gray)", cursor: "pointer" }}
          >
            Skip
          </button>
        </div>
        <DialogDescription style={{ fontSize: 13, fontWeight: 400, color: "var(--color-warm-gray)", marginBottom: 14 }}>
          Ask a hard basketball question. Every number traces back to the data.
        </DialogDescription>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {PROMPTS.map((p) => (
            <button
              key={p}
              type="button"
              className="pill-ghost interactive-tactile"
              style={{ textAlign: "left", fontSize: 13, padding: "10px 16px", cursor: "pointer" }}
              onClick={() => onSelectPrompt(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

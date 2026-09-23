"use client";

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
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to Dime"
      className="onboard-backdrop"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(12, 10, 9, 0.25)",
        zIndex: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
      onClick={onFinish}
    >
      <div
        className="card onboard-panel"
        style={{ width: 460, maxWidth: "92vw", padding: 24 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
          <div className="display" style={{ fontSize: 24, color: "var(--color-ink-black)" }}>
            Meet Dime
          </div>
          <button
            type="button"
            onClick={onFinish}
            style={{ background: "transparent", border: "none", fontSize: 12, color: "var(--color-warm-gray)", cursor: "pointer" }}
          >
            Skip
          </button>
        </div>
        <div style={{ fontSize: 13, color: "var(--color-warm-gray)", marginBottom: 14 }}>
          Ask a hard basketball question. Every number traces back to the data.
        </div>
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
      </div>
    </div>
  );
}

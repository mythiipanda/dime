"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  onFinish: () => void;
  onSelectPrompt: (q: string) => void;
}

const PROMPTS = [
  "Who's the most clutch player?",
  "Compare Luka and SGA",
  "Show me rising stars",
];

const CAPABILITIES = [
  { title: "Ask", desc: "Chat with evidence, every number traced to its source." },
  { title: "Track", desc: "Watchlists follow your players and teams daily." },
  { title: "Debate", desc: "Shareable cards settle arguments with data." },
];

export default function OnboardingModal({ onFinish, onSelectPrompt }: Props) {
  const [step, setStep] = useState(0);
  const skipRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    skipRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onFinish();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onFinish]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to Dime"
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
        className="card"
        style={{ width: 520, maxWidth: "92vw", padding: 28 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 6 }} aria-label={`Step ${step + 1} of 3`}>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                style={{
                  width: i === step ? 20 : 8,
                  height: 8,
                  borderRadius: 9999,
                  background: i === step ? "var(--color-ink-black)" : "var(--color-stone-muted)",
                  transition: "width 160ms ease",
                }}
              />
            ))}
          </div>
          <button
            type="button"
            ref={skipRef}
            onClick={onFinish}
            style={{ background: "transparent", border: "none", fontSize: 12, color: "var(--color-warm-gray)", cursor: "pointer" }}
          >
            Skip
          </button>
        </div>

        {step === 0 && (
          <div>
            <div className="display" style={{ fontSize: 28, color: "var(--color-ink-black)", marginBottom: 6 }}>
              Meet Dime
            </div>
            <div style={{ fontSize: 14, color: "var(--color-warm-gray)", marginBottom: 18 }}>
              NBA analytics that shows its work.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10 }}>
              {CAPABILITIES.map((c) => (
                <div
                  key={c.title}
                  style={{
                    border: "1px solid var(--color-stone-border)",
                    borderRadius: 10,
                    padding: "14px 12px",
                    background: "var(--color-pure-white)",
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink-black)", marginBottom: 2 }}>
                    {c.title}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--color-warm-gray)", lineHeight: 1.5 }}>
                    {c.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {step === 1 && (
          <div>
            <div className="display" style={{ fontSize: 28, color: "var(--color-ink-black)", marginBottom: 6 }}>
              Try it
            </div>
            <div style={{ fontSize: 14, color: "var(--color-warm-gray)", marginBottom: 18 }}>
              Pick a question to start the conversation.
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {PROMPTS.map((p) => (
                <button
                  key={p}
                  type="button"
                  className="pill-ghost"
                  style={{ textAlign: "left", fontSize: 13, padding: "10px 16px", cursor: "pointer" }}
                  onClick={() => onSelectPrompt(p)}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            <div className="display" style={{ fontSize: 28, color: "var(--color-ink-black)", marginBottom: 6 }}>
              Stay in the loop
            </div>
            <div style={{ fontSize: 14, color: "var(--color-warm-gray)", marginBottom: 18, lineHeight: 1.6 }}>
              The Today tab shows last night&apos;s scores, tonight&apos;s slate, and leaderboard movers.
              Add players to your watchlist and Dime tracks them for you.
            </div>
            <button
              type="button"
              className="pill-cta"
              style={{ fontSize: 13, padding: "10px 24px", cursor: "pointer" }}
              onClick={onFinish}
            >
              Get it
            </button>
          </div>
        )}

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 24 }}>
          <button
            type="button"
            className="pill-ghost"
            style={{
              fontSize: 12,
              cursor: step === 0 ? "default" : "pointer",
              opacity: step === 0 ? 0.4 : 1,
            }}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
          >
            Back
          </button>
          {step < 2 ? (
            <button
              type="button"
              className="pill-cta"
              style={{ fontSize: 12, cursor: "pointer" }}
              onClick={() => setStep((s) => Math.min(2, s + 1))}
            >
              Next
            </button>
          ) : (
            <span style={{ fontSize: 12, color: "var(--color-ash-gray)" }}>
              You&apos;re all set
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

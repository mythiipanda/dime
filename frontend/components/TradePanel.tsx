"use client";

import { useState } from "react";
import { BACKEND } from "../lib/chat";

interface Verdict {
  team_a: { team: string; out: number; players: string[]; payroll: number; allowed_in?: number; match_rule?: string; over_apron1?: boolean; over_apron2?: boolean };
  team_b: { team: string; out: number; players: string[]; payroll: number; allowed_in?: number; match_rule?: string; over_apron1?: boolean; over_apron2?: boolean };
  legal: boolean;
  issues: string[];
  checks?: { rule: string; checked: boolean; note: string }[];
  salary_date?: string | null;
  disclaimer?: string;
}

function millions(n: number): string {
  return `$${(n / 1_000_000).toFixed(1)}M`;
}

export default function TradePanel() {
  const [a, setA] = useState("LAL");
  const [pa, setPa] = useState("");
  const [b, setB] = useState("DEN");
  const [pb, setPb] = useState("");
  const [out, setOut] = useState<Verdict | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const check = async () => {
    setError("");
    setBusy(true);
    try {
      const res = await fetch(`${BACKEND}/api/v1/trade/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ team_a: a, players_a: pa, team_b: b, players_b: pb }),
      });
      const data = await res.json();
      if (!data.ok) {
        setError(String(data.error || "failed"));
        return;
      }
      setOut(data.rows as Verdict);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <div className="display" style={{ fontSize: 20 }}>Trade checker</div>
      <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 4 }}>
        Simplified 2023 CBA matching. Picks and exceptions stay out of v1.
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
        <input className="field" value={a} onChange={(e) => setA(e.target.value)} placeholder="team A" style={{ width: 80 }} />
        <input className="field" value={pa} onChange={(e) => setPa(e.target.value)} placeholder="players out, comma separated" style={{ flex: 1, minWidth: 200 }} />
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
        <input className="field" value={b} onChange={(e) => setB(e.target.value)} placeholder="team B" style={{ width: 80 }} />
        <input className="field" value={pb} onChange={(e) => setPb(e.target.value)} placeholder="players out, comma separated" style={{ flex: 1, minWidth: 200 }} />
      </div>
      <div style={{ marginTop: 12 }}>
        <button className="pill-cta" style={{ fontSize: 12 }} disabled={busy} onClick={check}>
          {busy ? "Checking" : "Check legality"}
        </button>
      </div>
      {error && <div style={{ color: "var(--color-warm-gray)", marginTop: 8 }}>{error}</div>}
      {out && (
        <div style={{ marginTop: 12 }}>
          <div
            style={{
              display: "inline-block",
              fontSize: 12,
              borderRadius: 9999,
              padding: "4px 12px",
              background: out.legal ? "var(--color-ink-black)" : "var(--color-stone-border)",
              color: out.legal ? "var(--color-pure-white)" : "var(--color-ink-black)",
            }}
          >
            {out.legal ? "Legal" : "Illegal"}
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 13 }}>
            {[
              { side: out.team_a, label: "A" },
              { side: out.team_b, label: "B" },
            ].map(({ side, label }) => (
              <div key={label} style={{ flex: 1 }}>
                <div style={{ fontWeight: 500 }}>
                  {side.team} sends {millions(side.out)}
                </div>
                <div style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
                  {side.players.join(", ") || "nobody"} · payroll {millions(side.payroll)}
                </div>
                {(side.allowed_in != null || side.match_rule) && (
                  <div style={{ fontSize: 12, color: "var(--color-warm-gray)" }}>
                    Takes back up to {side.allowed_in != null ? millions(side.allowed_in) : "n/a"}
                    {side.match_rule ? ` · ${side.match_rule}` : ""}
                    {side.over_apron2 ? " · 2nd apron" : side.over_apron1 ? " · 1st apron" : ""}
                  </div>
                )}
              </div>
            ))}
          </div>
          {out.issues.map((issue) => (
            <div key={issue} style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 4 }}>
              {issue}
            </div>
          ))}
          {out.checks && out.checks.filter((c) => !c.checked).length > 0 && (
            <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 4 }}>
              Not checked: {out.checks.filter((c) => !c.checked).map((c) => c.rule).join(", ")}.
            </div>
          )}
          {out.disclaimer && (
            <div style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 4 }}>
              {out.disclaimer}
              {out.salary_date ? ` Salaries as of ${out.salary_date.slice(0, 10)}.` : ""}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

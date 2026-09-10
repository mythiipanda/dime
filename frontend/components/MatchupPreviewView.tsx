"use client";

import { asList, Caption, Chip, isObj, SectionTitle, str } from "./view-shared";

interface TeamForm {
  record: string;
  last10: string;
  streak: string;
  note: string;
}

interface StarLine {
  name: string;
  ppg: string;
  apg: string;
  rpg: string;
}

interface InjuryList {
  out: { name: string; impact: string }[];
  questionable: string[];
  note: string;
}

interface XFactor {
  player: string;
  line: string;
  delta: string;
  note: string;
}

function parseForm(v: unknown): TeamForm | null {
  if (!isObj(v)) return null;
  if (str(v.note)) return { record: "", last10: "", streak: "", note: str(v.note) };
  const record = str(v.record);
  if (!record) return null;
  const l10 = v.last10;
  const last10 = Array.isArray(l10)
    ? l10.map(String).join(" · ")
    : typeof l10 === "string" || typeof l10 === "number"
      ? String(l10)
      : "";
  return { record, last10, streak: str(v.streak), note: "" };
}

function parseStar(v: unknown): StarLine | null {
  if (!isObj(v)) return null;
  const name = str(v.name);
  if (!name) return null;
  const f = (k: string) => {
    const x = v[k];
    return typeof x === "number" ? x.toFixed(1) : typeof x === "string" ? x : "—";
  };
  return { name, ppg: f("ppg"), apg: f("apg"), rpg: f("rpg") };
}

function parseInjuries(v: unknown): InjuryList | null {
  if (!isObj(v)) return null;
  if (str(v.note)) return { out: [], questionable: [], note: str(v.note) };
  const out = asList(v.out)
    .map((o) => ({ name: str(o.name), impact: str(o.impact) }))
    .filter((o) => o.name);
  const questionable = Array.isArray(v.questionable)
    ? v.questionable.filter((q): q is string => typeof q === "string")
    : [];
  if (!out.length && !questionable.length) return null;
  return { out, questionable, note: "" };
}

function parseXFactor(v: unknown): XFactor | null {
  if (!isObj(v)) return null;
  if (str(v.note)) return { player: "", line: "", delta: "", note: str(v.note) };
  const player = str(v.player);
  const line = str(v.line);
  if (!player || !line) return null;
  const d = v.delta;
  return {
    player,
    line,
    delta: typeof d === "number" ? `${d >= 0 ? "+" : ""}${d.toFixed(1)}` : "",
    note: "",
  };
}

interface Matchup {
  a: StarLine;
  b: StarLine;
  angle: string;
}

export interface PreviewRows {
  alreadyPlayed: boolean;
  playedMatchup: string;
  playedDate: string;
  playedScore: string;
  suggestion: string;
  away: string;
  home: string;
  date: string;
  arena: string;
  formAway: TeamForm | null;
  formHome: TeamForm | null;
  matchups: Matchup[];
  injAway: InjuryList | null;
  injHome: InjuryList | null;
  xfAway: XFactor | null;
  xfHome: XFactor | null;
  whyWatch: string;
}

export function parsePreview(rows: unknown): PreviewRows | null {
  if (!isObj(rows)) return null;
  if (rows.already_played === true) {
    return {
      alreadyPlayed: true,
      playedMatchup: str(rows.matchup),
      playedDate: str(rows.date),
      playedScore: str(rows.score),
      suggestion: str(rows.suggestion),
      away: "",
      home: "",
      date: "",
      arena: "",
      formAway: null,
      formHome: null,
      matchups: [],
      injAway: null,
      injHome: null,
      xfAway: null,
      xfHome: null,
      whyWatch: "",
    };
  }
  const game = isObj(rows.game) ? rows.game : null;
  if (!game) return null;
  const away = str(game.away);
  const home = str(game.home);
  if (!away || !home) return null;
  const form = isObj(rows.form) ? rows.form : {};
  const injuries = isObj(rows.injuries) ? rows.injuries : {};
  const xf = isObj(rows.xfactors) ? rows.xfactors : {};
  const matchups: Matchup[] = [];
  for (const m of asList(rows.matchups)) {
    const a = parseStar(m.a);
    const b = parseStar(m.b);
    if (a && b) matchups.push({ a, b, angle: str(m.angle) });
  }
  return {
    alreadyPlayed: false,
    playedMatchup: "",
    playedDate: "",
    playedScore: "",
    suggestion: "",
    away,
    home,
    date: str(game.date),
    arena: str(game.arena),
    formAway: parseForm(form.away),
    formHome: parseForm(form.home),
    matchups,
    injAway: parseInjuries(injuries.away),
    injHome: parseInjuries(injuries.home),
    xfAway: parseXFactor(xf.away),
    xfHome: parseXFactor(xf.home),
    whyWatch: str(rows.why_watch),
  };
}

function FormCard({ abbr, form }: { abbr: string; form: TeamForm | null }) {
  if (!form) return null;
  return (
    <div
      style={{
        flex: "1 1 200px",
        background: "var(--color-pure-white)",
        border: "1px solid var(--color-stone-border)",
        borderRadius: 10,
        padding: "10px 14px",
      }}
    >
      <div
        style={{ fontWeight: 600, fontSize: 14, color: "var(--color-ink-black)" }}
      >
        {abbr}
      </div>
      {form.note ? (
        <div style={{ fontSize: 12, color: "var(--color-ash-gray)" }}>{form.note}</div>
      ) : (
        <div
          style={{
            fontSize: 12,
            color: "var(--color-warm-gray)",
            marginTop: 4,
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          <span style={{ fontVariantNumeric: "tabular-nums" }}>{form.record}</span>
          {form.last10 && <span>Last 10: {form.last10}</span>}
          {form.streak && <span>{form.streak}</span>}
        </div>
      )}
    </div>
  );
}

function StarRow({ s }: { s: StarLine }) {
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink-black)" }}>
        {s.name}
      </div>
      <div
        style={{
          fontSize: 11,
          color: "var(--color-ash-gray)",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {s.ppg} pts · {s.apg} ast · {s.rpg} reb
      </div>
    </div>
  );
}

export default function MatchupPreviewView({
  rows,
  meta,
}: {
  rows: unknown;
  meta?: Record<string, unknown>;
}) {
  const p = parsePreview(rows);
  if (!p) return null;
  const note = typeof meta?.note === "string" ? meta.note : "";

  if (p.alreadyPlayed) {
    return (
      <div
        style={{
          background: "var(--color-stone-canvas)",
          border: "1px solid var(--color-stone-border)",
          borderRadius: 10,
          padding: "14px 16px",
        }}
      >
        <SectionTitle>{p.playedMatchup || "Already played"}</SectionTitle>
        <div style={{ fontSize: 13, color: "var(--color-ink-black)" }}>
          {p.playedScore}
          {p.playedDate ? ` · ${p.playedDate}` : ""}
        </div>
        {p.suggestion && (
          <div
            style={{
              fontSize: 12,
              color: "var(--color-warm-gray)",
              marginTop: 6,
            }}
          >
            {p.suggestion}
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <div
          className="display"
          style={{ fontSize: 20, color: "var(--color-ink-black)" }}
        >
          {p.away} <span style={{ color: "var(--color-ash-gray)" }}>@</span> {p.home}
        </div>
        <div
          style={{ fontSize: 12, color: "var(--color-warm-gray)", marginTop: 4 }}
        >
          {[p.date, p.arena].filter(Boolean).join(" · ")}
        </div>
      </div>

      {(p.formAway || p.formHome) && (
        <div style={{ marginBottom: 14 }}>
          <SectionTitle>Recent form</SectionTitle>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <FormCard abbr={p.away} form={p.formAway} />
            <FormCard abbr={p.home} form={p.formHome} />
          </div>
        </div>
      )}

      {p.matchups.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <SectionTitle>Star matchups</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {p.matchups.map((m, i) => (
              <div
                key={i}
                style={{
                  border: "1px solid var(--color-stone-border)",
                  borderRadius: 10,
                  padding: "10px 14px",
                  background: "var(--color-pure-white)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                  }}
                >
                  <StarRow s={m.a} />
                  <StarRow s={m.b} />
                </div>
                {m.angle && (
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--color-cyan-edge)",
                      marginTop: 6,
                    }}
                  >
                    {m.angle}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {(p.injAway || p.injHome) && (
        <div style={{ marginBottom: 14 }}>
          <SectionTitle>Injuries</SectionTitle>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {[
              [p.away, p.injAway],
              [p.home, p.injHome],
            ].map(([abbr, inj]) => {
              const list = inj as InjuryList | null;
              if (!list) return null;
              return (
                <div
                  key={abbr as string}
                  style={{
                    flex: "1 1 200px",
                    border: "1px solid var(--color-stone-border)",
                    borderRadius: 10,
                    padding: "10px 14px",
                    background: "var(--color-pure-white)",
                    fontSize: 12,
                    color: "var(--color-warm-gray)",
                  }}
                >
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: 13,
                      color: "var(--color-ink-black)",
                      marginBottom: 6,
                    }}
                  >
                    {abbr as string}
                  </div>
                  {list.note ? (
                    <div>{list.note}</div>
                  ) : (
                    <>
                      {list.out.map((o, i) => (
                        <div key={i} style={{ marginBottom: 4 }}>
                          <span style={{ fontWeight: 500, color: "var(--color-ink-black)" }}>
                            {o.name}
                          </span>
                          {o.impact ? ` — ${o.impact}` : ""}
                        </div>
                      ))}
                      {list.questionable.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          Questionable: {list.questionable.join(", ")}
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {(p.xfAway || p.xfHome) && (
        <div style={{ marginBottom: 14 }}>
          <SectionTitle>X-factors</SectionTitle>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {[
              [p.away, p.xfAway],
              [p.home, p.xfHome],
            ].map(([abbr, xf]) => {
              const x = xf as XFactor | null;
              if (!x) return null;
              return (
                <div
                  key={abbr as string}
                  style={{
                    fontSize: 12,
                    color: "var(--color-warm-gray)",
                    border: "1px solid var(--color-stone-border)",
                    borderRadius: 10,
                    padding: "10px 14px",
                    background: "var(--color-pure-white)",
                    lineHeight: 1.55,
                  }}
                >
                  <span
                    style={{
                      fontWeight: 600,
                      color: "var(--color-ink-black)",
                      marginRight: 6,
                    }}
                  >
                    {abbr as string}
                  </span>
                  {x.note ? x.note : x.line}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {p.whyWatch && (
        <div
          style={{
            background: "var(--color-stone-canvas)",
            border: "1px solid var(--color-stone-border)",
            borderRadius: 10,
            padding: "12px 16px",
          }}
        >
          <SectionTitle>Why watch</SectionTitle>
          <div
            style={{
              fontSize: 13,
              color: "var(--color-ink-black)",
              lineHeight: 1.65,
            }}
          >
            {p.whyWatch}
          </div>
        </div>
      )}
      {note && (
        <div style={{ marginTop: 10 }}>
          <Caption>{note}</Caption>
        </div>
      )}
    </div>
  );
}

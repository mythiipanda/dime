"use client";

import { SourceLine } from "@/components/ds/SourceLine";
import { useEffect, useState } from "react";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";
import type { DimeArtifact } from "@/lib/dime-stream";
import { boardReportHtml, boardReportMarkdown, type BoardReport, type ReportBlock } from "@/lib/board-report";
import { nbaTeams } from "../../../lib/teams";
import PinButton from "../PinButton";
import { Button } from "../../ds/Button";

const money = (v: number | null | undefined) => v == null ? "—" : `$${(v / 1_000_000).toFixed(1)}M`;
const fractionPct = (v: number | null | undefined) => v == null ? "—" : `${(v * 100).toFixed(1)}%`;
const percentPoints = (v: number | null | undefined) => v == null ? "—" : `${v.toFixed(1)}%`;
const per_game = (v: number | null | undefined) => v == null ? "—" : v.toFixed(1);
const TEAM_KEY = "dime_draft_team_v1";

type Provenance = { table?: string; as_of?: string | null };
type Block<T> = { ok?: boolean; error?: string; provenance?: Provenance } & T;

type BoardRow = { board_order?: number; pick: number; name: string; position: string | null; school: string | null; gp: number | null; pts: number | null; reb: number | null; ast: number | null; ts_pct: number | null; usg: number | null };
type AgentRow = { name: string; team: string; fa_type: string; prior_salary: number | null; cap_hold: number | null };
type RoomRow = { team: string; committed: number | null; option_salary: number | null; fa_holds: number | null; roster_charges: number | null; projected_room: number | null };
type Gap = { factor: string; label: string; value: number; rank: number; of: number };
type Target = { name: string; team: string; fa_type: string; prior_salary: number | null; cap_hold: number | null; ppg: number | null; rpg: number | null; apg: number | null; spg: number | null; bpg: number | null; fg3_pct: number | null; gp: number | null };

type Draft = {
  ok: boolean;
  team: string;
  season: string;
  error?: string;
  blocks: {
    board: Block<{ season?: string; board?: "big_board" | "mock_draft"; order_semantics?: "rank" | "pick"; rows: BoardRow[] }>;
    free_agents: Block<{ rows: AgentRow[] }>;
    cap_room: Block<{ rows: RoomRow[] }>;
    fit: Block<{ team: string; gaps: Gap[]; cap: { committed: number | null; option_salary: number | null; fa_holds: number | null; projected_room: number | null } | null; targets: Target[]; errors: string[] }>;
  };
};

const artifact = (title: string, columns: string[], rows: (string | number)[][], provenance?: Provenance): DimeArtifact => ({
  kind: "table",
  title,
  columns: columns.map(label => ({ key: label.toLowerCase().replace(/[^a-z0-9]+/g, "_"), label })),
  rows,
  provenance: { origin: "warehouse", liveSources: [], capability: "product_draft", asOf: provenance?.as_of ?? undefined },
});

function Section({ title, cite, pin, children, wide }: { title: string; cite?: Provenance; pin?: DimeArtifact; children: React.ReactNode; wide?: boolean }) {
  return (
    <section className={`flex min-w-0 flex-col rounded-xl border border-line bg-surface p-5 ${wide ? "sm:col-span-2" : ""}`}>
      <div className="mb-4 flex items-center justify-between gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-wider text-ink-3">{title}</h3>
        {pin && <PinButton artifact={pin} />}
      </div>
      <div className="min-h-12 flex-1">{children}</div>
      <SourceLine table={cite?.table} asOf={cite?.as_of ? String(cite.as_of) : null} />
    </section>
  );
}

function BlockError({ block, empty }: { block: { ok?: boolean; error?: string }; empty: string }) {
  return <p className="py-2 text-[12px] text-ink-3">{block.error ?? empty}</p>;
}

export default function DraftView({ onAsk, initialTeam }: { onAsk?: (text: string, context?: import("@/lib/view-context").ViewContext) => void; initialTeam?: string }) {
  const [team, setTeam] = useState(initialTeam ?? "NYK");
  const [data, setData] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!initialTeam) {
      try {
        const saved = window.localStorage.getItem(TEAM_KEY);
        if (saved && nbaTeams.some(item => item.abbr === saved)) setTeam(saved);
      } catch {}
    }
  }, [initialTeam]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetch(`${BACKEND}${apiPath(`/draft?team=${encodeURIComponent(team)}`)}`)
      .then(response => response.json())
      .then(value => {
        if (!active) return;
        if (!value.ok) { setError(value.error ?? "Could not load the draft workspace"); setData(null); }
        else setData(value);
      })
      .catch(() => { if (active) setError("Could not reach the backend"); })
      .finally(() => { if (active) setLoading(false); });
    try { window.localStorage.setItem(TEAM_KEY, team); } catch {}
    return () => { active = false; };
  }, [team]);

  const blocks = data?.blocks;
  const boardRows = blocks?.board.rows ?? [];
  const agentRows = blocks?.free_agents.rows ?? [];
  const roomRows = blocks?.cap_room.rows ?? [];
  const fit = blocks?.fit;
  const teamName = nbaTeams.find(item => item.abbr === team)?.name ?? team;
  const boardKind = blocks?.board.board;
  const boardIsMock = boardKind === "mock_draft";
  const boardOrderSemantics = blocks?.board.order_semantics ?? (boardIsMock ? "pick" : boardKind === "big_board" ? "rank" : undefined);
  const boardTitle = boardIsMock ? "Mock draft" : boardKind === "big_board" ? "Big board" : "Prospect board";
  const boardOrderLabel = boardOrderSemantics === "pick" ? "Pick" : boardOrderSemantics === "rank" ? "Rank" : "Order";
  const boardPopulation = boardIsMock ? "Mock-draft population" : boardKind === "big_board" ? "Big-board population" : "Board population identity unavailable";
  const boardOrderMeaning = boardOrderSemantics === "pick"
    ? "order is a projected team-placement pick."
    : boardOrderSemantics === "rank"
      ? "order is a talent rank, not team placement."
      : "order semantics are unavailable.";
  const boardSemantics = boardKind ? `${boardPopulation} · ${boardOrderMeaning}` : `${boardPopulation}.`;
  const boardOrder = (row: BoardRow) => row.board_order ?? row.pick;

  const boardPin = () => artifact(
    `${boardTitle} ${blocks?.board.season ?? ""}`,
    [boardOrderLabel.toLowerCase(), "player", "pos", "school", "gp", "pts", "reb", "ast", "ts%", "usg"],
    boardRows.map(row => [boardOrder(row), row.name, row.position ?? "", row.school ?? "", row.gp ?? "", row.pts ?? "", row.reb ?? "", row.ast ?? "", row.ts_pct != null ? fractionPct(row.ts_pct) : "", row.usg != null ? percentPoints(row.usg) : ""]),
    blocks?.board.provenance);

  const agentsPin = () => artifact(
    "2027 free agents",
    ["player", "team", "type", "prior salary", "cap hold"],
    agentRows.map(row => [row.name, row.team, row.fa_type, money(row.prior_salary), money(row.cap_hold)]),
    blocks?.free_agents.provenance);

  const roomPin = () => artifact(
    "2027 cap room",
    ["team", "committed", "options", "fa holds", "roster charges", "projected room"],
    roomRows.map(row => [row.team, money(row.committed), money(row.option_salary), money(row.fa_holds), money(row.roster_charges), money(row.projected_room)]),
    blocks?.cap_room.provenance);

  const fitPin = () => artifact(
    `${team} fit targets`,
    ["player", "team", "type", "prior salary", "ppg", "rpg", "apg"],
    (fit?.targets ?? []).map(row => [row.name, row.team, row.fa_type, money(row.prior_salary), row.ppg ?? "", row.rpg ?? "", row.apg ?? ""]),
    fit?.provenance);

  const buildReport = (): BoardReport => {
    const report: ReportBlock[] = [];
    report.push({
      heading: boardTitle,
      meta: [`season ${blocks?.board.season ?? "—"}`, boardIsMock ? "mock-draft picks" : boardKind === "big_board" ? "big-board ranks" : "board identity unavailable"],
      table: { columns: [boardOrderLabel, "Player", "Pos", "School", "PTS", "REB", "AST", "TS%"], rows: boardRows.map(row => [String(boardOrder(row)), row.name, row.position ?? "—", row.school ?? "—", row.pts != null ? String(row.pts) : "—", row.reb != null ? String(row.reb) : "—", row.ast != null ? String(row.ast) : "—", fractionPct(row.ts_pct)]) },
      lines: [boardSemantics, `Source: ${blocks?.board.provenance?.table ?? "unknown"}${blocks?.board.provenance?.as_of ? ` · as of ${String(blocks.board.provenance.as_of).slice(0, 10)}` : ""}`],
    });
    report.push({
      heading: "2027 free agents",
      table: { columns: ["Player", "Team", "Type", "Prior salary", "Cap hold"], rows: agentRows.map(row => [row.name, row.team, row.fa_type, money(row.prior_salary), money(row.cap_hold)]) },
      lines: [`Source: ${blocks?.free_agents.provenance?.table ?? "unknown"}${blocks?.free_agents.provenance?.as_of ? ` · as of ${String(blocks.free_agents.provenance.as_of).slice(0, 10)}` : ""}`],
    });
    report.push({
      heading: "2027 cap room",
      table: { columns: ["Team", "Committed", "Options", "FA holds", "Charges", "Projected room"], rows: roomRows.map(row => [row.team, money(row.committed), money(row.option_salary), money(row.fa_holds), money(row.roster_charges), money(row.projected_room)]) },
      lines: [`Source: ${blocks?.cap_room.provenance?.table ?? "unknown"}${blocks?.cap_room.provenance?.as_of ? ` · as of ${String(blocks.cap_room.provenance.as_of).slice(0, 10)}` : ""}`],
    });
    if (fit) {
      const lines: string[] = [];
      if (fit.gaps.length) lines.push(`Gaps: ${fit.gaps.map(gap => `${gap.label} #${gap.rank}/${gap.of}`).join(" · ")}`);
      if (fit.cap) lines.push(`Projected room: ${money(fit.cap.projected_room)} · committed ${money(fit.cap.committed)}`);
      lines.push(...fit.errors);
      report.push({
        heading: `${teamName} fit`,
        table: { columns: ["Player", "Team", "Type", "Prior salary", "PPG", "RPG", "APG"], rows: fit.targets.map(row => [row.name, row.team, row.fa_type, money(row.prior_salary), row.ppg != null ? String(row.ppg) : "—", row.rpg != null ? String(row.rpg) : "—", row.apg != null ? String(row.apg) : "—"]) },
        lines: [...lines, `Source: ${fit.provenance?.table ?? "unknown"}${fit.provenance?.as_of ? ` · as of ${String(fit.provenance.as_of).slice(0, 10)}` : ""}`],
      });
    }
    return { title: `Draft & free agency · ${teamName}`, subtitle: "Dime draft workspace", generated: new Date().toISOString(), blocks: report };
  };

  const exportReport = (pdf: boolean) => {
    setExporting(true);
    try {
      const report = buildReport();
      if (pdf) {
        const win = window.open("", "_blank");
        if (!win) { setError("Pop-up blocked. Allow pop-ups to export the PDF report."); return; }
        win.document.write(boardReportHtml(report));
        win.document.close();
        win.print();
      } else {
        const url = URL.createObjectURL(new Blob([boardReportMarkdown(report)], { type: "text/markdown;charset=utf-8;" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = `draft-${team.toLowerCase()}-report.md`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } finally { setExporting(false); }
  };

  const askText = () => `Scout the ${teamName} draft and free agency: the prospect board, the 2027 free agent class against their cap room, and fit targets for their roster gaps.`;

  return (
    <div className="workspace-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[17px] font-medium">Draft & free agency</h1>
          <p className="mt-1 text-[12px] text-ink-3">Prospect board, the 2027 free agent class with cap room, and fit targets for one team's roster gaps.</p>
        </div>
        {data && (
          <div className="flex flex-wrap items-center gap-2">
            {onAsk && <Button size="sm" variant="secondary" onClick={() => onAsk(askText(), { kind: "draft_scout", summary: `${teamName} draft + free agency`, entities: { team: teamName } })}>Ask Dime</Button>}
            <Button size="sm" variant="secondary" disabled={exporting} onClick={() => exportReport(false)}>Report (.md)</Button>
            <Button size="sm" variant="secondary" disabled={exporting} onClick={() => exportReport(true)}>Report (PDF)</Button>
          </div>
        )}
      </div>

      <div className="mb-5 flex items-center gap-2">
        <label htmlFor="draft-team" className="text-[12px] text-ink-3">Fit team</label>
        <select id="draft-team" aria-label="Fit team" value={team} onChange={event => setTeam(event.target.value)} className="h-8 rounded-lg border border-line bg-surface px-2.5 text-[12px] text-ink">
          {nbaTeams.map(item => <option key={item.abbr} value={item.abbr}>{item.abbr} · {item.name}</option>)}
        </select>
      </div>

      {loading && <p role="status" className="py-8 text-[13px] text-ink-3">Loading the draft workspace…</p>}
      {error && !loading && <div role="alert" className="rounded-xl border border-line p-5"><p className="text-[13px] text-red">{error}. No sample data is substituted.</p></div>}

      {!loading && !error && blocks && (
        <div className="grid items-stretch gap-4 sm:grid-cols-2">
          <Section title={`${boardTitle}${blocks.board.season ? ` · ${blocks.board.season}` : ""}`} cite={blocks.board.provenance} pin={blocks.board.ok ? boardPin() : undefined} wide>
            {blocks.board.rows.length ? (
              <div className="space-y-2">
                <p className="text-[12px] text-ink-3">{boardSemantics}</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[12px]">
                    <thead className="border-b border-line text-[10px] text-ink-3">
                      <tr>{[boardOrderLabel, "Player", "Pos", "School", "PTS", "REB", "AST", "TS%", "USG"].map(label => <th key={label} className="pb-2 pr-3 font-normal last:text-right">{label}</th>)}</tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {boardRows.map(row => (
                        <tr key={boardOrder(row)}>
                          <td className="py-2 pr-3 font-mono tabular-nums text-ink-3">{boardOrder(row)}</td>
                          <td className="py-2 pr-3 text-ink">{row.name}</td>
                          <td className="py-2 pr-3 text-ink-2">{row.position ?? "—"}</td>
                          <td className="py-2 pr-3 text-ink-2">{row.school ?? "—"}</td>
                          <td className="py-2 pr-3 font-mono tabular-nums">{per_game(row.pts)}</td>
                          <td className="py-2 pr-3 font-mono tabular-nums">{per_game(row.reb)}</td>
                          <td className="py-2 pr-3 font-mono tabular-nums">{per_game(row.ast)}</td>
                          <td className="py-2 pr-3 font-mono tabular-nums">{fractionPct(row.ts_pct)}</td>
                          <td className="py-2 text-right font-mono tabular-nums">{percentPoints(row.usg)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : <BlockError block={blocks.board} empty="No prospect board rows." />}
          </Section>

          <Section title={`${teamName} fit`} cite={fit?.provenance} pin={fit?.targets.length ? fitPin() : undefined} wide>
            {!fit?.ok && !fit?.gaps.length && !fit?.targets.length ? <BlockError block={fit ?? {}} empty="No fit data." /> : (
              <div className="space-y-4">
                {Boolean(fit?.gaps.length) && (
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[12px] text-ink-3">Roster gaps</span>
                    {fit!.gaps.map(gap => <span key={gap.factor} className="rounded-full border border-line bg-inset px-2.5 py-1 text-[11px]">{gap.label} · #{gap.rank} of {gap.of}</span>)}
                  </div>
                )}
                {fit?.cap && <p className="text-[12px] text-ink-2">{money(fit.cap.projected_room)} projected room · {money(fit.cap.committed)} committed{fit.cap.option_salary ? ` · ${money(fit.cap.option_salary)} options` : ""}</p>}
                {fit?.targets.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[12px]">
                      <thead className="border-b border-line text-[10px] text-ink-3">
                        <tr>{["Player", "Team", "Type", "Prior", "PPG", "RPG", "APG"].map(label => <th key={label} className="pb-2 pr-3 font-normal last:text-right">{label}</th>)}</tr>
                      </thead>
                      <tbody className="divide-y divide-line">
                        {fit!.targets.map(row => (
                          <tr key={row.name}>
                            <td className="py-2 pr-3 text-ink">{row.name}</td>
                            <td className="py-2 pr-3 text-ink-2">{row.team}</td>
                            <td className="py-2 pr-3 font-mono text-[11px] text-ink-3">{row.fa_type}</td>
                            <td className="py-2 pr-3 font-mono tabular-nums">{money(row.prior_salary)}</td>
                            <td className="py-2 pr-3 font-mono tabular-nums">{row.ppg ?? "—"}</td>
                            <td className="py-2 pr-3 font-mono tabular-nums">{row.rpg ?? "—"}</td>
                            <td className="py-2 text-right font-mono tabular-nums">{row.apg ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                {Boolean(fit?.errors.length) && <p className="text-[12px] text-ink-3">{fit!.errors.join(" · ")}</p>}
              </div>
            )}
          </Section>

          <Section title="2027 free agents" cite={blocks.free_agents.provenance} pin={blocks.free_agents.ok ? agentsPin() : undefined}>
            {agentRows.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[12px]">
                  <thead className="border-b border-line text-[10px] text-ink-3">
                    <tr>{["Player", "Team", "Type", "Prior salary", "Cap hold"].map(label => <th key={label} className="pb-2 pr-3 font-normal last:text-right">{label}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {agentRows.map(row => (
                      <tr key={`${row.name}-${row.team}`}>
                        <td className="py-2 pr-3 text-ink">{row.name}</td>
                        <td className="py-2 pr-3 text-ink-2">{row.team}</td>
                        <td className="py-2 pr-3 font-mono text-[11px] uppercase text-ink-3">{row.fa_type}</td>
                        <td className="py-2 pr-3 font-mono tabular-nums">{money(row.prior_salary)}</td>
                        <td className="py-2 text-right font-mono tabular-nums">{money(row.cap_hold)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <BlockError block={blocks.free_agents} empty="No free agent rows." />}
          </Section>

          <Section title="2027 cap room" cite={blocks.cap_room.provenance} pin={blocks.cap_room.ok ? roomPin() : undefined}>
            {roomRows.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[12px]">
                  <thead className="border-b border-line text-[10px] text-ink-3">
                    <tr>{["Team", "Committed", "Options", "Holds", "Charges", "Room"].map(label => <th key={label} className="pb-2 pr-3 font-normal last:text-right">{label}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {roomRows.map(row => (
                      <tr key={row.team} className={row.team === team ? "bg-inset" : ""}>
                        <td className="py-2 pr-3 font-mono text-[11px] text-ink">{row.team}</td>
                        <td className="py-2 pr-3 font-mono tabular-nums">{money(row.committed)}</td>
                        <td className="py-2 pr-3 font-mono tabular-nums">{money(row.option_salary)}</td>
                        <td className="py-2 pr-3 font-mono tabular-nums">{money(row.fa_holds)}</td>
                        <td className="py-2 pr-3 font-mono tabular-nums">{money(row.roster_charges)}</td>
                        <td className="py-2 text-right font-mono tabular-nums">{money(row.projected_room)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <BlockError block={blocks.cap_room} empty="No cap room rows." />}
          </Section>
        </div>
      )}
    </div>
  );
}

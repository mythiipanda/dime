"use client";

import { SourceLine } from "@/components/ds/SourceLine";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiPath } from "@/lib/api";
import { BACKEND } from "@/lib/chat";
import type { DimeArtifact } from "@/lib/dime-stream";
import { boardReportHtml, boardReportMarkdown, type BoardReport, type ReportBlock } from "@/lib/board-report";
import PinButton from "../PinButton";
import ArtifactShotChart from "../ArtifactShotChart";
import ArtifactChart from "../ArtifactChart";
import { Button } from "../../ds/Button";

const PICKS_KEY = "dime_compare_v1";
const DEFAULT_SEASON = "2025-26";
const money = (v: number) => `$${(v / 1_000_000).toFixed(1)}M`;
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const seasonLabel = (year: number) => `${year}-${String((year + 1) % 100).padStart(2, "0")}`;

type Cite = { table?: string; as_of?: string | null };
type Block<T> = { ok?: boolean; error?: string; provenance?: Cite } & T;

type Zone = { zone: string; x: number; y: number; att: number; makes: number; pct: number; league_pct?: number | null; delta_pp?: number | null };
type SeasonLine = { season: number; age: number; team: string; gp: number; mpg: number; ppg: number; rpg: number; apg: number; spg: number; bpg: number; fg_pct: number; fg3_pct: number; ft_pct: number; ts_pct: number; usg_pct: number; off_rating: number; def_rating: number; net_rating: number };
type ArcRow = { season: number; age: number | null; gp: number; pts: number; ts_pct: number; usg_pct: number };

type ComparePlayer = {
  player_id: number;
  name: string;
  season: string;
  season_line: Block<{ row?: SeasonLine }>;
  impact: Block<{ raptor_total?: number; war_total?: number; mp?: number; rank?: number; of?: number }>;
  zones: Block<{ zones?: Zone[] }>;
  contract: Block<{ row?: { team: string; salary: number; contract_type: string; guaranteed: boolean; player_option: boolean; team_option: boolean }; season?: string }>;
  arc: Block<{ rows?: ArcRow[] }>;
};
type CompareData = { ok: boolean; season: string; players: ComparePlayer[]; error?: string };

type Pick = { id: number; name: string; season: string };
type ResolvePlayer = { id: number; full_name: string; is_active?: boolean };

function Section({ title, cite, artifact, children, wide }: { title: string; cite?: Cite; artifact?: DimeArtifact; children: React.ReactNode; wide?: boolean }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-5 ${wide ? "sm:col-span-2 xl:col-span-4" : ""}`}>
      <div className="mb-4 flex items-center justify-between gap-2">
        <h3 className="font-mono text-[10px] uppercase tracking-wider text-ink-3">{title}</h3>
        {artifact && <PinButton artifact={artifact} />}
      </div>
      {children}
      <SourceLine table={cite?.table} asOf={cite?.as_of ? String(cite.as_of) : null} />
    </section>
  );
}

function PlayerSearch({ onPick, disabled }: { onPick: (player: ResolvePlayer) => void; disabled?: boolean }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ResolvePlayer[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  const search = (value: string) => {
    setQuery(value);
    if (timer.current) clearTimeout(timer.current);
    if (value.trim().length < 2) { setResults([]); setOpen(false); return; }
    timer.current = setTimeout(() => {
      fetch(`${BACKEND}${apiPath(`/resolve?q=${encodeURIComponent(value.trim())}`)}`)
        .then(response => response.json())
        .then(value => { setResults((value?.rows?.players ?? []).slice(0, 8)); setOpen(true); })
        .catch(() => setResults([]));
    }, 250);
  };
  return (
    <div className="relative">
      <input
        type="search"
        value={query}
        disabled={disabled}
        onChange={event => search(event.target.value)}
        onFocus={() => results.length && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Search a player to add…"
        aria-label="Search players"
        className="h-9 w-full rounded-lg border border-line bg-surface px-3 text-[13px] text-ink placeholder:text-ink-3 sm:w-72"
      />
      {open && results.length > 0 && (
        <ul role="listbox" className="absolute left-0 right-0 top-10 z-10 max-h-64 overflow-auto rounded-lg border border-line bg-surface py-1 shadow-lg sm:w-72">
          {results.map(player => (
            <li key={player.id}>
              <button type="button" role="option" aria-selected="false" className="flex w-full items-center justify-between px-3 py-2 text-left text-[13px] hover:bg-inset" onMouseDown={event => event.preventDefault()} onClick={() => { onPick(player); setQuery(""); setResults([]); setOpen(false); }}>
                <span>{player.full_name}</span>
                {player.is_active === false && <span className="text-[11px] text-ink-2">retired</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function CompareView({ onAsk, initialPicks }: { onAsk?: (text: string, context?: import("@/lib/view-context").ViewContext) => void; initialPicks?: Pick[] }) {
  const [picks, setPicks] = useState<Pick[]>(initialPicks ?? []);
  const [data, setData] = useState<CompareData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (!initialPicks) {
      try {
        const saved = JSON.parse(window.localStorage.getItem(PICKS_KEY) ?? "[]");
        if (Array.isArray(saved)) setPicks(saved.filter((item): item is Pick => typeof item?.id === "number" && typeof item?.name === "string").slice(0, 4));
      } catch {}
    }
    setHydrated(true);
  }, [initialPicks]);

  useEffect(() => {
    if (!hydrated) return;
    try { window.localStorage.setItem(PICKS_KEY, JSON.stringify(picks)); } catch {}
    if (picks.length < 2) { setData(null); setError(null); return; }
    let active = true;
    setLoading(true);
    setError(null);
    const playersParam = picks.map(pick => `${pick.id}:${pick.season}`).join(",");
    fetch(`${BACKEND}${apiPath(`/compare?players=${encodeURIComponent(playersParam)}`)}`)
      .then(response => response.json())
      .then(value => {
        if (!active) return;
        if (!value.ok) { setError(value.error ?? "Could not load the comparison"); setData(null); }
        else setData(value);
      })
      .catch(() => { if (active) setError("Could not reach the backend"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [picks, hydrated]);

  const addPick = (player: ResolvePlayer) => {
    if (picks.some(pick => pick.id === player.id) || picks.length >= 4) return;
    setPicks([...picks, { id: player.id, name: player.full_name, season: DEFAULT_SEASON }]);
  };
  const setSeason = (id: number, season: string) => setPicks(picks.map(pick => pick.id === id ? { ...pick, season } : pick));
  const removePick = (id: number) => setPicks(picks.filter(pick => pick.id !== id));

  const players = useMemo(() => data?.players ?? [], [data]);

  const metrics: { key: keyof SeasonLine; label: string; fmt: (v: number) => string }[] = [
    { key: "gp", label: "GP", fmt: v => String(v) },
    { key: "mpg", label: "MPG", fmt: v => v.toFixed(1) },
    { key: "ppg", label: "PTS", fmt: v => v.toFixed(1) },
    { key: "rpg", label: "REB", fmt: v => v.toFixed(1) },
    { key: "apg", label: "AST", fmt: v => v.toFixed(1) },
    { key: "spg", label: "STL", fmt: v => v.toFixed(1) },
    { key: "bpg", label: "BLK", fmt: v => v.toFixed(1) },
    { key: "fg_pct", label: "FG%", fmt: pct },
    { key: "fg3_pct", label: "3P%", fmt: pct },
    { key: "ft_pct", label: "FT%", fmt: pct },
    { key: "ts_pct", label: "TS%", fmt: pct },
    { key: "usg_pct", label: "USG%", fmt: pct },
    { key: "off_rating", label: "ORtg", fmt: v => v.toFixed(1) },
    { key: "def_rating", label: "DRtg", fmt: v => v.toFixed(1) },
    { key: "net_rating", label: "Net", fmt: v => `${v > 0 ? "+" : ""}${v.toFixed(1)}` },
  ];

  const pinArtifact = (): DimeArtifact => ({
    kind: "table",
    title: `Player comparison · ${players.map(player => player.name).join(" vs ")}`,
    columns: [{ key: "metric", label: "metric" }, ...players.map(player => ({ key: `p${player.player_id}`, label: `${player.name} (${player.season})` }))],
    rows: [
      ...metrics.map(metric => [metric.label, ...players.map(player => player.season_line.row ? metric.fmt(Number(player.season_line.row?.[metric.key] ?? 0)) : "—")]),
      ["raptor", ...players.map(player => player.impact.raptor_total != null ? player.impact.raptor_total.toFixed(1) : "—")],
      ["impact rank", ...players.map(player => player.impact.rank != null ? `${player.impact.rank}/${player.impact.of}` : "—")],
      ["war", ...players.map(player => player.impact.war_total != null ? player.impact.war_total.toFixed(1) : "—")],
      ["salary", ...players.map(player => player.contract.row ? money(player.contract.row.salary) : "—")],
      ["contract", ...players.map(player => player.contract.row?.contract_type ?? "—")],
    ],
    provenance: { origin: "warehouse", liveSources: [], capability: "product_compare" },
  });

  const buildReport = (): BoardReport => {
    const blocks: ReportBlock[] = [];
    const lineCite = players[0]?.season_line.provenance;
    blocks.push({
      heading: "Season line",
      meta: players.map(player => `${player.name} · ${player.season}`),
      table: {
        columns: ["Metric", ...players.map(player => player.name)],
        rows: metrics.map(metric => [metric.label, ...players.map(player => player.season_line.row ? metric.fmt(Number(player.season_line.row?.[metric.key] ?? 0)) : "—")]),
      },
      lines: lineCite ? [`Source: ${lineCite.table}${lineCite.as_of ? ` · as of ${String(lineCite.as_of).slice(0, 10)}` : ""}`] : [],
    });
    for (const player of players) {
      const blocks_for_player: ReportBlock[] = [];
      if (player.impact.raptor_total != null) blocks_for_player.push({ heading: `${player.name} · impact`, meta: [player.season], lines: [`RAPTOR total: ${player.impact.raptor_total.toFixed(1)} · rank ${player.impact.rank}/${player.impact.of}`, `WAR: ${player.impact.war_total?.toFixed(1)}`, `Source: ${player.impact.provenance?.table}${player.impact.provenance?.as_of ? ` · as of ${String(player.impact.provenance.as_of).slice(0, 10)}` : ""}`] });
      if (player.zones.zones?.length) blocks_for_player.push({ heading: `${player.name} — shooting zones`, meta: [player.season], table: { columns: ["Zone", "Att", "Makes", "FG%", "League", "Delta"], rows: player.zones.zones.map(zone => [zone.zone, String(zone.att), String(zone.makes), `${zone.pct}%`, zone.league_pct != null ? `${zone.league_pct}%` : "—", zone.delta_pp != null ? `${zone.delta_pp > 0 ? "+" : ""}${zone.delta_pp}pp` : "—"]) }, lines: [`Source: ${player.zones.provenance?.table}${player.zones.provenance?.as_of ? ` · as of ${String(player.zones.provenance.as_of).slice(0, 10)}` : ""}`] });
      if (player.contract.row) blocks_for_player.push({ heading: `${player.name} · contract`, meta: [`cap sheet ${player.contract.season}`], lines: [`Salary: ${money(player.contract.row.salary)} (${player.contract.row.contract_type})`, `Guaranteed: ${player.contract.row.guaranteed ? "yes" : "no"}`, `Source: ${player.contract.provenance?.table}${player.contract.provenance?.as_of ? ` · as of ${String(player.contract.provenance.as_of).slice(0, 10)}` : ""}`] });
      if (player.arc.rows?.length) blocks_for_player.push({ heading: `${player.name} — age curve`, lines: [...player.arc.rows.map(row => `${row.season}: age ${row.age ?? "—"} · ${row.pts} pts · ${pct(row.ts_pct)} TS`), `Source: ${player.arc.provenance?.table}${player.arc.provenance?.as_of ? ` · as of ${String(player.arc.provenance.as_of).slice(0, 10)}` : ""}`] });
      blocks.push(...blocks_for_player);
    }
    return { title: `Player comparison: ${players.map(player => player.name).join(" vs ")}`, subtitle: "Dime comparison view", generated: new Date().toISOString(), blocks };
  };

  const exportReport = (pdf: boolean) => {
    setExporting(true);
    try {
      const report = buildReport();
      const base = `compare-${players.map(player => player.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")).join("-vs-")}`;
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
        a.download = `${base}-report.md`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } finally { setExporting(false); }
  };

  const askText = () => `Compare ${players.map(player => `${player.name} (${player.season})`).join(" vs ")}: season lines, impact and rank, shooting zones, contracts, and age curves.`;

  const ageLabels = useMemo(() => {
    const ages = new Set<number>();
    for (const player of players) for (const row of player.arc.rows ?? []) if (row.age != null) ages.add(row.age);
    return [...ages].sort((a, b) => a - b);
  }, [players]);

  const arcSeries = players.map(player => {
    const byAge = new Map((player.arc.rows ?? []).filter(row => row.age != null).map(row => [row.age as number, row.pts]));
    return { name: player.name, values: ageLabels.map(age => byAge.get(age) ?? null) };
  });

  const lineCite = players.find(player => player.season_line.ok)?.season_line.provenance ?? players[0]?.season_line.provenance;
  const impactCite = players.find(player => player.impact.ok)?.impact.provenance ?? players[0]?.impact.provenance;
  const zonesCite = players.find(player => player.zones.ok)?.zones.provenance ?? players[0]?.zones.provenance;
  const contractCite = players.find(player => player.contract.ok)?.contract.provenance ?? players[0]?.contract.provenance;
  const arcCite = players.find(player => player.arc.ok)?.arc.provenance ?? players[0]?.arc.provenance;

  return (
    <div className="workspace-page">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[17px] font-medium">Compare players</h1>
        </div>
        {data && (
          <div className="flex flex-wrap items-center gap-2">
            {onAsk && <Button size="sm" variant="secondary" onClick={() => onAsk(askText(), { kind: "compare", summary: `compare ${players.map(p => p.name).join(" vs ")}`, entities: { players: players.map(p => ({ name: p.name, season: p.season })) } })}>Ask Dime to compare</Button>}
            <PinButton artifact={pinArtifact()} />
            <Button size="sm" variant="secondary" disabled={exporting} onClick={() => exportReport(false)}>Report (.md)</Button>
            <Button size="sm" variant="secondary" disabled={exporting} onClick={() => exportReport(true)}>Report (PDF)</Button>
          </div>
        )}
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-2">
        {picks.map(pick => (
          <span key={pick.id} className="flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-[12px]">
            {pick.name}
            <button type="button" aria-label={`Remove ${pick.name}`} className="text-ink-3 hover:text-ink" onClick={() => removePick(pick.id)}>×</button>
          </span>
        ))}
        <PlayerSearch onPick={addPick} disabled={picks.length >= 4} />
      </div>

      {picks.length < 2 && <p className="rounded-xl border border-dashed border-line-strong bg-inset px-5 py-10 text-center text-[13px] text-ink-3">Add at least two players to compare.</p>}
      {loading && picks.length >= 2 && <p role="status" className="py-8 text-[13px] text-ink-3">Loading the comparison…</p>}
      {error && !loading && <div role="alert" className="rounded-xl border border-line p-5"><p className="text-[13px] text-red">{error}. No sample data is substituted.</p></div>}

      {!loading && !error && data && (
        <div className="space-y-4">
          <div className={`grid items-stretch gap-4 ${players.length === 2 ? "sm:grid-cols-2" : players.length === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2 xl:grid-cols-4"}`}>
            {players.map(player => {
              const seasons = (player.arc.rows ?? []).map(row => seasonLabel(row.season)).reverse();
              return (
                <div key={player.player_id} className="rounded-xl border border-line bg-surface p-5">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-[15px] font-medium leading-snug">{player.name}</p>
                      {player.season_line.row && <p className="mt-0.5 text-[12px] text-ink-3">{player.season_line.row.team} · age {player.season_line.row.age}</p>}
                    </div>
                    <button type="button" aria-label={`Remove ${player.name}`} className="text-ink-3 hover:text-ink" onClick={() => removePick(player.player_id)}>×</button>
                  </div>
                  <select aria-label={`${player.name} season`} value={player.season} onChange={event => setSeason(player.player_id, event.target.value)} className="mt-3 h-8 w-full rounded-lg border border-line bg-surface px-2 text-[12px] text-ink">
                    {!seasons.includes(player.season) && <option value={player.season}>{player.season}</option>}
                    {seasons.map(label => <option key={label} value={label}>{label}</option>)}
                  </select>
                </div>
              );
            })}
          </div>

          <Section title="Season line" cite={lineCite} artifact={pinArtifact()} wide>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12px]">
                <thead className="border-b border-line text-[10px] text-ink-3">
                  <tr><th className="pb-2 font-normal">Metric</th>{players.map(player => <th key={player.player_id} className="pb-2 text-right font-normal">{player.name} · {player.season}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {metrics.map(metric => (
                    <tr key={metric.key}>
                      <td className="py-2 text-ink-2">{metric.label}</td>
                      {players.map(player => <td key={player.player_id} className="py-2 text-right font-mono tabular-nums">{player.season_line.row ? metric.fmt(Number(player.season_line.row[metric.key])) : "—"}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {players.some(player => !player.season_line.ok) && <p className="mt-2 text-[12px] text-ink-3">{players.filter(player => !player.season_line.ok).map(player => `${player.name}: ${player.season_line.error}`).join(" · ")}</p>}
          </Section>

          <Section title="Impact & rank" cite={impactCite}>
            <div className="space-y-3">
              {players.map(player => (
                <div key={player.player_id} className="text-[12px]">
                  <span className="text-ink">{player.name}</span>
                  {player.impact.ok
                    ? <span className="ml-2 text-ink-2">RAPTOR {Number(player.impact.raptor_total).toFixed(1)} · #{player.impact.rank} of {player.impact.of} · WAR {Number(player.impact.war_total).toFixed(1)}</span>
                    : <span className="ml-2 text-ink-3">{player.impact.error}</span>}
                </div>
              ))}
            </div>
          </Section>

          <Section title="Contract" cite={contractCite}>
            <div className="space-y-3">
              {players.map(player => (
                <div key={player.player_id} className="text-[12px]">
                  <span className="text-ink">{player.name}</span>
                  {player.contract.ok && player.contract.row
                    ? <span className="ml-2 text-ink-2">{money(player.contract.row.salary)} · {player.contract.row.contract_type}{player.contract.season ? ` · ${player.contract.season} sheet` : ""}</span>
                    : <span className="ml-2 text-ink-3">{player.contract.error}</span>}
                </div>
              ))}
            </div>
          </Section>

          <Section title="Shooting zones vs league" cite={zonesCite} wide>
            <div className={`grid gap-4 ${players.length === 2 ? "sm:grid-cols-2" : players.length === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2 xl:grid-cols-4"}`}>
              {players.map(player => (
                <div key={player.player_id}>
                  {player.zones.ok && player.zones.zones?.length
                    ? <ArtifactShotChart zones={player.zones.zones} footnote={`${player.name} · ${player.season} · fg% vs league`} />
                    : <p className="py-6 text-center text-[12px] text-ink-3">{player.zones.error ?? `No shot data for ${player.name}`}</p>}
                </div>
              ))}
            </div>
          </Section>

          <Section title="Age curve: points per game" cite={arcCite} wide>
            {arcSeries.some(series => series.values.some(value => value != null))
              ? <ArtifactChart title="Points per game by age" series={arcSeries} xLabels={ageLabels.map(String)} unit="pts" footnote="Career points per game at each age." />
              : <p className="py-6 text-center text-[12px] text-ink-3">No career rows in the warehouse.</p>}
          </Section>
        </div>
      )}
    </div>
  );
}

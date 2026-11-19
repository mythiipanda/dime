import type { Board, BoardCitation } from "./boards";
import type { AiMessage } from "./chat";
import { citationDetails } from "./citation-details";
import { capabilityLabel } from "./evidence";
import type { CellKind, NotebookCell, NotebookDraft, SQLResult } from "./notebooks";

const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const text = (...values: unknown[]) => values.find((value): value is string => typeof value === "string" && !!value.trim()) || "";
const cell = (kind: CellKind, source: string, index: number): NotebookCell => ({ id: (index + 1).toString(16).padStart(32, "0"), kind, source });
const identifier = (name: string) => { if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) throw new Error("The recorded source contains an invalid SQL identifier."); return `"${name}"`; };
function literal(value: unknown): string {
  if (value == null) return "NULL";
  if (typeof value === "boolean") return value ? "TRUE" : "FALSE";
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "string") return `'${value.replaceAll("'", "''")}'`;
  throw new Error("A recorded SQL parameter is not a supported scalar value.");
}

function inlineParameters(query: string, params: unknown): string {
  let position = 0;
  const named = record(params);
  return query.replace(/'(?:''|[^'])*'|"(?:""|[^"])*"|--[^\n]*|\/\*[\s\S]*?\*\/|\$\$[\s\S]*?\$\$|\$(?:[A-Za-z_][A-Za-z0-9_]*|\d+)|(?<!:):[A-Za-z_][A-Za-z0-9_]*|\?/g, (token) => {
    if (!["$", ":", "?"].includes(token[0]) || token.startsWith("$$")) return token;
    const key = token === "?" ? position++ : Array.isArray(params) && /^\$\d+$/.test(token) ? Number(token.slice(1)) - 1 : token.slice(1);
    const values = Array.isArray(params) ? params : named;
    if (!Object.hasOwn(values, key)) throw new Error(`Recorded SQL is missing the parameter ${token}.`);
    return literal((values as Record<string | number, unknown>)[key]);
  }).trim().replace(/;+\s*$/, "");
}

function cachedTable(table: Record<string, unknown>): (SQLResult & { cached: true }) | undefined {
  const nested = record(table.rows), meta = record(table.meta);
  const values = Array.isArray(table.rows) ? table.rows : Array.isArray(nested.rows) ? nested.rows : null;
  if (!values) return;
  const rawColumns = table.columns ?? nested.columns;
  const names = Array.isArray(rawColumns) ? rawColumns.map((column) => typeof column === "string" ? column : text(record(column).name)) : [...new Set(values.flatMap((row) => Object.keys(record(row))))];
  const rows = values.map((row) => Array.isArray(row) ? Object.fromEntries(names.map((name, i) => [name, row[i] ?? null])) : record(row));
  const columns = names.map((name, index) => {
    const value = rows.map((row) => row[name]).find((v) => v != null);
    return { name, type: text(record(Array.isArray(rawColumns) ? rawColumns[index] : null).type) || (value == null ? "UNKNOWN" : typeof value === "number" ? "DOUBLE" : typeof value === "boolean" ? "BOOLEAN" : typeof value === "object" ? "JSON" : "VARCHAR") };
  });
  const preview = rows.slice(0, 100);
  while (preview.length && JSON.stringify({ columns, rows: preview }).length > 60000) preview.pop();
  const truncated = preview.length < rows.length || !!table.truncated || !!nested.truncated || (typeof meta.rows === "number" && meta.rows > preview.length);
  return { columns, rows: preview, page: 0, page_size: 100, has_more: truncated, ms: typeof meta.ms === "number" ? meta.ms : 0, truncated, cached: true };
}

export function notebookFromAnswer(ai: AiMessage, question: string): NotebookDraft {
  const nodes = Object.values(ai.nodes), tables = nodes.flatMap((node) => node.tables).map(record);
  const calls = nodes.flatMap((node) => node.toolCalls).map((call) => ({ ...call, query: text(call.sql, call.args.sql) }));
  const sources = [...new Set(tables.map((table) => {
    const provenance = record(table.provenance), meta = record(table.meta);
    return [capabilityLabel(text(table.tool)), text(provenance.source, meta.source) || "Source not recorded", text(provenance.season, meta.season)].filter(Boolean).join(" · ");
  }))];
  const cells = [cell("markdown", `# ${question || "Answer notebook"}\n\n${ai.text.slice(0, 1800)}${ai.text.length > 1800 ? "…" : ""}\n\n## Sources\n${sources.length ? sources.map((source) => `- ${source}`).join("\n") : "No sources recorded."}\n\nCached tables below are from the original answer. Run SQL cells to query the current warehouse.`, 0)];
  const queries = new Map<string, NotebookCell>();
  const tableQueries = new Set<string>();
  const add = (query: string, params: unknown, table?: Record<string, unknown>) => {
    const source = inlineParameters(query, params);
    let sqlCell = queries.get(source);
    if (!sqlCell) {
      if (cells.length >= 100) throw new Error("This answer has too many SQL queries for one notebook.");
      sqlCell = cell("sql", source, cells.length); queries.set(source, sqlCell); cells.push(sqlCell);
    }
    const cached = table && cachedTable(table);
    if (cached && !sqlCell.outputs) sqlCell.outputs = { kind: "sql", data: cached };
  };
  tables.forEach((table, index) => {
    const details = citationDetails(ai, { key: `table-${index}`, index, subject: "", stat: "", value: "", origin: "" });
    const matching = calls.filter((call) => call.query && call.name === table.tool);
    const query = details.query || (matching.length === 1 ? matching[0].query : "");
    if (!query) return;
    const candidates = calls.filter((candidate) => candidate.query === query);
    const bindings = table.params ?? record(table.provenance).params ?? record(table.meta).params;
    const parameterSets = new Set(candidates.map((candidate) => JSON.stringify(candidate.args.params)));
    if (bindings === undefined && parameterSets.size > 1) return;
    tableQueries.add(query);
    add(query, bindings ?? candidates[0]?.args.params, table);
  });
  calls.filter((call) => call.query && (call.args.params !== undefined || !tableQueries.has(call.query))).forEach((call) => add(call.query, call.args.params));
  {
    const context = "## Data snapshot\n\nNo executable SQL was recorded. These cached tables are context, not reproducible queries.";
    const snapshots = (queries.size ? [] : tables).flatMap((table) => {
      const cached = cachedTable(table);
      return cached ? [{ title: capabilityLabel(text(table.tool)), data: { columns: cached.columns, rows: cached.rows, truncated: cached.truncated } }] : [];
    });
    const cited = cachedTable({ rows: tables.filter((table) => !Array.isArray(table.rows) && typeof table.output_id === "string" && Object.hasOwn(table, "value")).map((table) => ({
      output: text(table.display_name, table.output_id), value: table.value, unit: table.unit ?? null,
      subject: table.subject_id ?? null, subject_type: table.subject_type ?? null,
      source: text(record(table.provenance).source) || "Source not recorded", provenance: record(table.provenance),
    })) });
    if (cited?.rows.length) snapshots.push({ title: "Cited values", data: { columns: cited.columns, rows: cited.rows, truncated: cited.truncated } });
    if (!queries.size && !snapshots.length) cells.push(cell("markdown", `${context}\n\nNo tables with recorded rows were attached to this answer.`, cells.length));
    snapshots.forEach((snapshot, index) => {
      if (cells.length >= 100) throw new Error("This answer has too many snapshot tables for one notebook.");
      cells.push({ ...cell("markdown", `${!queries.size && index === 0 ? `${context}\n\n` : ""}### ${snapshot.title}`, cells.length), outputs: { kind: "snapshot", data: snapshot.data } });
    });
  }
  return { title: (question.trim() || "Answer notebook").slice(0, 160), cells, origin: { kind: "chat", ref: (ai.carry?.run_id || question || "answer").slice(0, 256) } };
}

export function notebookFromBoard(board: Board): NotebookDraft {
  const cells = [cell("markdown", `# ${board.title}\n\nSeason: **${board.season}**\n\n**Players:** ${board.rows.map((row) => `${row.name} (${row.player_id})`).join(", ") || "None selected"}\n\n**Metrics:** ${board.columns.map((column) => column.metric_id).join(", ") || "None selected"}\n\nQueries select only this shortlist and its cited metric columns. Values use the source table's native units (percentage fields may be fractions). Salary keeps its own cited season and exact resolved identity; unresolved matches remain null.`, 0)];
  const groups = new Map<string, { season: string; columns: Set<string>; citations: Map<number, BoardCitation> }>();
  for (const column of board.columns) {
    const citations = board.rows.map((row) => ({ id: row.player_id, citation: board.cells[row.player_id]?.[column.metric_id]?.citation }));
    const citation = citations.find((entry) => entry.citation?.table && entry.citation.column)?.citation;
    if (!citation?.table || !citation.column) {
      if (board.rows.length) throw new Error("Refresh the board before opening it as a notebook; source citations are missing.");
      continue;
    }
    identifier(citation.table); identifier(citation.column);
    let group = groups.get(citation.table);
    if (!group) { group = { season: citation.season, columns: new Set(), citations: new Map() }; groups.set(citation.table, group); }
    if (group.season !== citation.season) throw new Error("This source has conflicting seasons. Refresh the board before opening it.");
    group.columns.add(citation.column);
    for (const entry of citations) if (entry.citation && !group.citations.has(entry.id)) group.citations.set(entry.id, entry.citation);
  }
  let chart: { query: string; metric: string } | undefined;
  for (const [table, group] of groups) {
    const name = { silver_player_season: "PLAYER", silver_advanced: "PLAYER_NAME", silver_cap_players: "player" }[table];
    if (!name) throw new Error(`The board source ${table} is not supported for notebook seeding.`);
    const columns = [...group.columns];
    let query: string;
    if (table === "silver_cap_players") {
      const selected = board.rows.map((row) => {
        const key = group.citations.get(row.player_id)?.row_key || {};
        return `(${literal(row.player_id)}, ${literal(key.player)}, ${literal(key.team)})`;
      }).join(",\n  ");
      query = `WITH selected(PLAYER_ID, player, team) AS (\n  VALUES ${selected}\n)\nSELECT s.PLAYER_ID, p.${identifier(name)} AS "Player", ${columns.map((column) => `p.${identifier(column)}`).join(", ")}\nFROM selected s LEFT JOIN ${identifier(table)} p\n  ON p.player = s.player AND p.team = s.team\n  AND p."_season" = ${literal(group.season)}\nORDER BY s.PLAYER_ID`;
    } else {
      const ids = board.rows.map((row) => { if (!Number.isSafeInteger(row.player_id) || row.player_id < 1) throw new Error("The board contains an invalid player ID."); return row.player_id; });
      query = `SELECT "PLAYER_ID", ${identifier(name)} AS "Player", ${columns.map(identifier).join(", ")}\nFROM ${identifier(table)}\nWHERE "_season" = ${literal(group.season)}\n  AND "PLAYER_ID" IN (${ids.join(", ")})\nORDER BY "PLAYER_ID"`;
    }
    cells.push(cell("sql", query, cells.length));
    chart ||= { query, metric: columns[0] };
  }
  if (chart) cells.push(cell("python", `# Optional chart · trusted local Python must be enabled\nimport matplotlib.pyplot as plt\n\ndf = sql(${JSON.stringify(chart.query)})\ndf = df.drop_nulls([${JSON.stringify(chart.metric)}])\nif df.is_empty():\n    raise ValueError("No values available for this metric and shortlist.")\nfig, ax = plt.subplots(figsize=(8, 3.5))\nax.barh(df["Player"].to_list(), df[${JSON.stringify(chart.metric)}].to_list())\nax.set_xlabel(${JSON.stringify(chart.metric)})\nax.set_title(${JSON.stringify(`${board.title} · ${board.season}`)}, loc="left", pad=16)\nfig.tight_layout()\nshow(df)`, cells.length));
  return { title: board.title.slice(0, 160) || "Board notebook", cells, origin: { kind: "board", ref: board.id.slice(0, 256) } };
}

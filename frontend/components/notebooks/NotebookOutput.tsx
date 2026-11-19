"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { chartable, type CellOutput, type TypedColumn } from "../../lib/notebooks";
import { Button } from "../ds/Button";

const AutoChart = dynamic(() => import("../AutoChart"), { ssr: false });
const scalar = (value: unknown) => value === null || value === undefined ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
export function NotebookTable({ columns, rows, label = "Query result" }: { columns: TypedColumn[]; rows: Record<string, unknown>[]; label?: string }) {
  return <div className="notebook-table-wrap"><table className="notebook-table" aria-label={label}><thead><tr>{columns.map((column) => <th key={column.name} scope="col"><span>{column.name}</span><small>{column.type}</small></th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={i}>{columns.map((c) => <td key={c.name} className={typeof row[c.name] === "number" ? "is-number" : ""}>{scalar(row[c.name])}</td>)}</tr>)}</tbody></table>{!rows.length && <p className="notebook-empty-output">Query complete. No rows matched.</p>}</div>;
}
export function NotebookOutput({ output, paging, onPage }: { output: unknown; paging: boolean; onPage: (page: number) => void }) {
  const [chart, setChart] = useState(false);
  if (!output) return null;
  const value = output as CellOutput;
  if (value.kind === "error") return <div className="notebook-error" role="alert"><strong>Cell could not run</strong><pre>{value.message}</pre><span>Edit the cell and run it again.</span></div>;
  if (value.kind === "sql" && value.data) {
    const result = value.data;
    const cached = "cached" in result && result.cached === true;
    return <div className="notebook-output"><div className="notebook-result-meta"><span className="notebook-result-dot" /><span>{result.rows.length.toLocaleString()} {cached ? "cached rows" : `rows${result.has_more ? " on this page" : " returned"}`}</span>{!cached && <><span>·</span><span>{result.ms.toLocaleString(undefined, { maximumFractionDigits: 1 })} ms</span></>}<span className="notebook-output-label">{cached ? "Answer snapshot" : "Warehouse SQL"}</span>{chartable(result.rows) && <Button variant="quiet" size="xs" aria-pressed={chart} onClick={() => setChart(!chart)}>{chart ? "Table" : "Chart"}</Button>}</div>
      {chart && chartable(result.rows) ? <div className="notebook-chart"><AutoChart table={{ rows: result.rows }} /></div> : <NotebookTable columns={result.columns} rows={result.rows} />}
      {cached && <p className="notebook-note">Cached answer preview. Run this cell to refresh results and enable paging.</p>}
      {!cached && (result.page > 0 || result.has_more || result.truncated) && <div className="notebook-pagination"><span>{result.truncated ? "Output capped at 5,000 rows. " : ""}Page {result.page + 1} · {result.page * result.page_size + (result.rows.length ? 1 : 0)}–{result.page * result.page_size + result.rows.length}</span><Button size="xs" variant="quiet" disabled={paging || result.page === 0} onClick={() => onPage(result.page - 1)}>Previous</Button><Button size="xs" variant="quiet" disabled={paging || !result.has_more} onClick={() => onPage(result.page + 1)}>{paging ? "Loading…" : "Next page"}</Button></div>}
    </div>;
  }
  if (value.kind === "python" && value.data) {
    const result = value.data;
    return <div className="notebook-output"><div className="notebook-result-meta"><span className={`notebook-result-dot${result.ok ? "" : " is-error"}`} /><span>{result.ok ? "Python complete" : "Python stopped"}</span><span className="notebook-output-label">Stateless · trusted local</span></div>
      {result.stdout && <div className="notebook-stream"><small>STDOUT</small><pre>{result.stdout}</pre></div>}
      {result.stderr && <div className="notebook-stream is-stderr"><small>STDERR</small><pre>{result.stderr}</pre></div>}
      {result.warnings?.map((warning, i) => <p className="notebook-note" key={i}>{warning}</p>)}
      {result.tables?.map((table, i) => <div key={i}><div className="notebook-result-meta">DataFrame {i + 1} · {table.row_count.toLocaleString()} rows{table.truncated ? ` · preview of ${table.rows.length}` : ""}</div><NotebookTable columns={table.columns} rows={table.rows} label={`DataFrame ${i + 1}`} /></div>)}
      {result.figures?.filter((figure) => figure.mime_type === "image/png").map((figure, i) => <figure className="notebook-figure" key={i}>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={`data:image/png;base64,${figure.data}`} alt={`Python chart ${i + 1}`} /><figcaption>Figure {i + 1} · PNG</figcaption></figure>)}
      {result.error && <div className="notebook-error" role="alert"><strong>Python exception</strong><pre>{result.error}</pre></div>}
    </div>;
  }
  return <p className="notebook-note">This saved output was reduced to a preview. Run the cell to restore the full result.</p>;
}

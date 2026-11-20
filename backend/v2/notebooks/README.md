# Local notebooks

`/api/notebooks` stores JSON documents with server-generated UUID-hex ids,
integer optimistic-concurrency versions, UTC timestamps, ordered cells, and
optional chat/board origin references. POST creates a document; PUT replaces
its editable fields and requires the current version (409 on conflict).
GET lists full documents; GET/DELETE by id read/remove them. Cell ids default
to generated UUIDs and must be unique within a document.

`DIME_NOTEBOOK_DIR` defaults to `backend/data/notebooks`. Atomic same-directory
temporary-file replacement prevents partial writes. Threads are serialized;
POSIX processes also share a file lock. Do not run multiple writer processes
on platforms without `flock`. Outputs over 256KiB become a bounded preview
with row count where available. Notebook JSON version is the revision counter;
the v1 schema is defined by the input models. JSON export preserves caches;
ipynb export preserves source and omits cached outputs, with `%%sql` cells
(a SQL magic extension must be installed in the receiving Jupyter kernel).

POST `/api/notebooks/sql` accepts DuckDB named placeholders (`$season`) and
`params: {"season": "2025-26"}`, zero-based `page`, and `page_size` (1–500).
It reuses `shared/query.py` AST checks and its bounded timed executor, but
requires the curated table allowlist to import successfully. Connections are
read-only with external access disabled, two threads and 512MB DuckDB memory.
Each page reruns the query, fetching at most 5001 rows. `truncated` means the
5000-row result ceiling was exceeded; `has_more` only refers to accessible rows.
Use a stable ORDER BY; paging is not a cross-request snapshot. Execution is
capped at 30s, but the row cap does not bound scan work or individual row size.

GET `/api/notebooks/capabilities` reports Python availability. Python execution
is disabled (403) unless `DIME_NOTEBOOK_PYTHON=1`. This is **trusted local code
execution, not a sandbox**. Never enable on an exposed/shared deployment or
execute unreviewed imported notebooks. Ordinary Python imports and host-user
permissions remain available: environment scrubbing and resource limits do
not prevent filesystem/network access by trusted Python code.

Each POST `/api/notebooks/python` uses `sys.executable -I` in a fresh temporary
directory with a small, non-inherited environment. The default wall limit is
30s (maximum 60s), with process-group termination on POSIX timeout. Supported
OSes also apply 4GiB address-space, CPU and 8MiB file-size limits. Windows does
not provide equivalent process-tree isolation/resource limits here.
No provider keys are passed. State does not survive calls; clients run-all.

Helpers: `sql(query, **params)` returns a Polars DataFrame via the same SQL
validator/read-only configuration, capped at 5000 rows. `show(frame)` or a
last-expression DataFrame emits up to four tables, each at most 500 rows and
256KiB, with types, row_count and truncated. stdout/stderr are capped at 64K
characters each. Matplotlib Agg emits up to four PNGs, each at most 1MiB,
as `{mime_type, data}` (base64). Errors include a bounded traceback. Matplotlib
is pinned in backend requirements; if unavailable, ordinary cells still run
and the response includes a figure-capture warning.

Check: `python -m pytest tests/test_notebooks.py tests/test_query_warehouse.py -q`

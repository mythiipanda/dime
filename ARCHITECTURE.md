# Architecture

Dime's TypeScript application host (`backend/analyst`) owns HTTP, CLI, model policy, conversation state, projects, workspaces, thread workspaces, and source artifacts. It embeds the Pi SDK (`@earendil-works/pi-coding-agent`) in the Node process and connects over stdio MCP to a Python NBA data and compute engine (`backend/analyst/python_tools.py` + `backend/shared`).

## Request path

1. The frontend posts to `/api/v2/chat/stream`. `backend/analyst/http.ts` validates the request, applies mode and rate checks, creates a run ID, and owns SSE streaming and disconnect cancellation.
2. `createAnalyst().stream()` in `backend/analyst/analyst.ts` resolves the model policy, loads prior conversation turns and source summaries from SQLite, and provisions a scoped workspace directory for the thread (`backend/data/pi-workspaces`).
3. `backend/analyst/pi-execution.ts` and `backend/analyst/runtime.ts` start a Pi `AgentSession` with QuickJS Codemode (`mode: "on"`), semantic tool namespaces across the 96 Python MCP tools, progressive skill disclosure via `load_skill`, prior-run inspection via `read_source`, and structured deliverable submission via `submit_answer`.
4. Python enforces DuckDB immutability at the `READ_ONLY` connection boundary, executes validated SQL and curated NBA domain tools, runs isolated subprocess Python (`duckdb`, `polars`, `numpy`, `scipy`, `scikit-learn`, `statsmodels`, `matplotlib`) inside the thread workspace, and returns structured results with actionable `recovery_hint` diagnostics on failure.
5. The TypeScript host persists source records, full user/assistant turns, and optional provenance anchors, emitting SSE events (`token`, `tool_call`, `tool_result`, `custom_data`, `work_log`, `final_answer`, `graph_end`) consumed by the Next.js frontend and DAB evaluation harness.

## Ownership

| TypeScript application host (`backend/analyst`) | Python data & compute engine (`backend/shared` + `backend/analyst/tools`) | Pi SDK (`@earendil-works/pi-coding-agent`) |
| --- | --- | --- |
| HTTP validation, CORS, rate limits, and SSE | Read-only DuckDB warehouse queries and schema introspection | Agent loop and model turn orchestration |
| Provider catalog, credentials, and token-window policy | Curated NBA metrics, CBA/trade checks, spatial/shot tools, and ratings | QuickJS Codemode multi-tool batching and `store`/`load` |
| SQLite conversations, projects, and workspace tokens | Subprocess `run_python` statistical modeling and artifact generation | Progressive context compaction |
| Source ledger, thread workspace lifecycle, and `load_skill` | Explicit direct product endpoints (`direct_data.py`) | Skill prompt indexing |
| `submit_answer` validation, CLI, and startup manifest | Season/unit metadata and structured error `recovery_hint` payloads | |

## Quality gates

All changes on `dev` enforce `scripts/gate.py`:
- `cccc` cognitive and cyclomatic complexity `<= 40` across every function (`cccc.toml`).
- Tracked non-test source file length `<= 1,000` LOC (`<= 800` LOC target).
- `backend/scripts/no_comments.py` zero restating comments rule.
- Full backend `pytest` suite, `backend/analyst` TypeScript build and test suite, and `frontend` TypeScript typecheck and test suite.

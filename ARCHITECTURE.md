# Architecture

Dime's TypeScript application host owns HTTP, CLI, model policy, conversation state, projects, workspaces and source artifacts. It embeds the published Pi 1.4.0 SDK in the same Node process. A private Python MCP process runs the existing NBA data engine and DuckDB operations.

## Request path

1. The frontend posts to `/api/v2/chat/stream`. `backend/analyst/http.ts` validates the request, applies the mode and rate checks, creates a run ID and owns SSE and disconnect cancellation.
2. `createAnalyst().stream()` in `backend/analyst/analyst.ts` resolves the model, reads the owner/thread ledger and creates a private session directory. Public requests contain questions, model selections and conversation identities; callers do not supply disk paths or MCP descriptors.
3. `pi-execution.ts` embeds a Pi `AgentSession` with QuickJS codemode. The only tools available inside codemode are `sql_exec`, `warehouse_schema` and the Node `read_source` tool.
4. Python retains SQL validation, NBA calculations, source units, season encodings, dataset fetching and ingestion behavior. Direct HTTP data operations use explicit named MCP functions in `direct_data.py`. Their mutators are excluded from Pi's fixed tool list.
5. The TypeScript host records new source rows and prior references, persists successful exchanges and emits the established SSE events. HTTP and the Node CLI consume the same analyst iterable.

Answers carry `verification: unassessed` and `answer_status: unassessed`. The active Pi path does not publish typed verified claims.

## Ownership

| TypeScript application host | Python data engine | Pi SDK |
| --- | --- | --- |
| HTTP validation, statuses, headers, files, CORS and SSE | SQL validation and execution | Model conversation |
| Model selection, credentials and known SDK limits | NBA calculations and season/unit semantics | Tool selection and recovery |
| SQLite conversations, projects and workspace tokens | DuckDB warehouse and existing state-table operations | Context compaction |
| JSON sources and owner/thread lookup | Existing dataset fetching and ingestion | QuickJS codemode |
| CLI and startup manifest | Explicit direct product data operations | |

DuckDB chat/run history still uses the existing `shared.store` functions through named internal MCP operations. No SQLite or DuckDB format conversion is performed. The retained Python conversation, project and workspace modules support independent domain consumers and tests; they do not own the product entrypoint.

## Configuration and persistence

`DIME_RUNTIME_V2` accepts `on`, `action_loop`, `off` and `shadow`. Unset or blank means `on`. Chat, projects, branches and run sources are available only in `on` and `action_loop`. Workspaces retain their separate owner-token rules.

Model selection uses explicit process configuration. Reflection requires both `DIME_ENABLE_REFLECTION` and `REFLECTION_API_KEY` and is never selected automatically. Unsupported selections fail configuration; the host does not choose a fallback provider. Limits come from the pinned SDK catalogue, with Reflection's direct API metadata recorded explicitly. The adapter rejects Nvidia's unsupported request options.

Defaults remain disk-backed under `backend/data`:

- `warehouse.duckdb` and `state.duckdb`, selected by `DIME_WAREHOUSE` and `DIME_STATE_DB`.
- `v2-conversations.sqlite3`, `v2-projects.sqlite3` and `workspaces.sqlite3`, selected by their existing store environment variables.
- `pi-sources` and `pi-private`, selected by `DIME_PI_SOURCES_DIR` and `DIME_PI_PRIVATE_DIR`.

Each successful exchange adds a user turn and an assistant turn with the same run ID. Follow-ups retain branch references to the previous sequence. Sources contain full MCP records, including failed domain results, units and provenance. A follow-up supplies metadata and opaque refs to the model; it does not automatically place raw rows in model context. Run-source retrieval requires the owner/thread association in SQLite. These identities are scoping values, not authentication.

## Runtime boundary

Provider credentials stay in the Node process. Python receives an explicit environment without provider keys and with numerical thread pools set to one. Pi profile resources, extensions, skills, prompt discovery, context files and built-in shell/filesystem tools are disabled. Provider HTTP remains available; this is not a network sandbox.

`backend/analyst/host.ts` is the server, manifest-generation and CLI entrypoint. Docker builds strict TypeScript before pruning development dependencies and starts `node analyst/dist/host.js`. Workspace ownership is in the copied TypeScript assets; startup does not import a Python workspace router. The startup manifest pins executable sources, compiled host modules, data-engine modules, typed argument assets, semantic baseline and warehouse identity.

## Verification limits

Local fixture proofs use actual Node HTTP and CLI, fake provider HTTP/SSE, real Pi/QuickJS, Python MCP and an owned synthetic DuckDB. Paired route fixtures compare old and new HTTP behavior with controlled data dependencies. Static packaging is checked without building an image or reading the production warehouse.

The target is Node 22.19 or later, checked with TypeScript 5.9.3 and Node 22.19 declarations. Current local runtime evidence uses Node 24.13.1. A Node 22 runtime proof, full container execution, broad live-provider compatibility, concurrency and answer quality remain unproved.

The retained typed evidence, calculation and verification domain under `backend/v2` is independent of the active Pi answer path. A source ref is not an evidence envelope or a verified claim.

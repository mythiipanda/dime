# Architecture

Dime answers NBA questions from a DuckDB warehouse. A Python host owns the product interface; a Node sidecar owns the model conversation. Python keeps credentials, persistence, request policy and read-only warehouse access. The pinned Pi SDK runs the agent loop and codemode sandbox.

The source snapshot inspected for this document is `54456bc` on 2026-10-31.

## Request path

1. The frontend posts a question to `POST /api/v2/chat/stream`.
2. `backend/v2/api/routes.py` applies the client rate limit, resolves the selected model, checks that Node is available and creates a run id.
3. The route calls `analyst.product_session.stream_product_session`, the same producer used by `backend/scripts/run_v2_chat.py`.
4. The producer loads prior sources and at most eight persisted turns, creates an owned private directory and spawns `backend/analyst/worker.mjs`.
5. The worker creates a Pi `AgentSession` with codemode as the only active tool. Python MCP exposes `sql_exec` and `warehouse_schema`. `read_source` is a worker-local Node tool over the prior-source catalogue, not a Python MCP tool.
6. The model writes JavaScript in codemode. It may inspect complete tool results, filter them and return chosen rows or values to its own context.
7. The worker sends token, tool and source events. Python validates each source record and relays SSE. On success it persists the exchange and a source artifact. On failure it keeps newly collected sources but does not persist an assistant exchange.

Current answers carry `verification: unassessed` and `answer_status: unassessed`; they do not pass through the typed verification runtime.

## Runtime gate

`DIME_RUNTIME_V2` accepts `on`, `action_loop`, `shadow` and `off`. Unset or empty means `on`; any other value fails configuration.

Only `on` and `action_loop` enable the chat, project, branch and run-source endpoints. `shadow` and `off` return 404 for those routes. Workspaces are mounted separately by `backend/entrypoint.py` and are not behind this flag.

## Ownership split

| Python host | Pi sidecar |
| --- | --- |
| HTTP and SSE | Model conversation |
| Request validation and rate limits | Tool selection |
| Model policy and credentials | Retry and recovery |
| Owner/thread scoping | Context compaction |
| Conversation, project and workspace persistence | Codemode execution |
| Raw source storage | Final answer text |
| Read-only warehouse tools | |

## Process boundary

Credentials cross to the worker over stdin, never argv or logs. The worker uses an in-memory credential store and an explicit provider registration. Python starts one MCP process per worker with an explicit environment; provider credentials are not inherited.

Pi profile resources, extensions, skills, prompts, themes and context files are disabled. Built-in filesystem and shell tools are not exposed; codemode is the only active tool. This is not a network sandbox: provider transport requires outbound HTTP. `allowModelNetwork: false` stops model-catalogue network access, not provider requests.

## Tool and source boundary

Tool results reach codemode as a native structured value:

```text
{ ref, tool, result, isError }
```

`ref` is an opaque lookup id. `result` is the complete tool value, including rows, declared units, season semantics, provenance and domain failures. The full `{ref, callId, tool, response}` record stays in the worker map and the durable source artifact. A source ref is not a citation, an evidence id or proof that a claim is true.

The host does not automatically inject prior rows into a follow-up. It supplies a catalogue of refs, columns, units, season semantics and provenance. The model must call `read_source` inside codemode to read a record, and a script may return chosen rows or values from that record.

`GET /api/v2/runs/{run_id}/sources` returns the stored records only when the run belongs to the supplied owner and thread and the artifact identity matches.

## Seams and module depth

- `stream_product_session` is the producer seam shared by HTTP and CLI. Its interface is broad and keyword-only, so a caller must know many collaborators; that is a locality cost at the product seam.
- The worker protocol is a narrow JSON-lines seam between Python and Pi.
- The Python tool contract is a small interface over SQL validation, schema annotation and read-only warehouse policy. The provider and fixture adapters meet at the Pi seam.
- Storage is split across DuckDB, SQLite and JSON artifacts. A run id links them, but there is no single transactional store.
- The typed evidence and verification modules are outside the active Pi answer path. This document does not establish which retained modules can be deleted; that needs a caller inventory rooted in current product entry points.

## Persistence

- Warehouse: `backend/data/warehouse.duckdb`, selectable with `DIME_WAREHOUSE`; state: `backend/data/state.duckdb`, selectable with `DIME_STATE_DB`.
- Conversation ledger: `backend/data/v2-conversations.sqlite3`.
- Projects: `backend/data/v2-projects.sqlite3`.
- Workspaces: `backend/data/workspaces.sqlite3`, selectable with `DIME_WORKSPACE_STORE`.
- Raw source artifacts: `backend/data/pi-sources/`.
- Private worker home and temp: `backend/data/pi-private/`.

An exchange persists a user turn and an assistant turn that share a run id. Chat, run history, conversation references and source artifacts are separate records; there is no unified atomic Run aggregate. Projects are persisted goal records and are not executed by Pi.

Owner and thread values scope access; they are not authentication. Anonymous requests use request history and do not persist a conversation.

## Retained verification domain

`backend/v2/contracts.py`, `domain/evidence.py`, `domain/calculations.py` and the runtime modules `models.py`, `interfaces.py` and `verifier.py` define typed evidence envelopes, calculation checks, immutable verifier views and mechanical claim verification.

They are retained domain capability, not the active Pi orchestration path. Current product answers contain no verified claims.

- A source record or source ref is not an `EvidenceEnvelope`.
- An `EvidenceEnvelope` is not a verified claim.
- A verified claim requires an admitted binding and a verification result that the current product path does not produce.

## Known gaps

- `backend/Dockerfile` copies `v2`, `shared`, scripts and data but not `workspaces`, while `backend/entrypoint.py` imports `workspaces.routes`. A built image would fail at container startup during import. No Docker image was built or run for this document.
- One bounded Beam diagnostic completed before the latest structured-result change. Its sources supported per-game statistics, but exact totals were unresolved and its answer was unassessed. The structured-result change has fixture proof only. Broader live-provider compatibility, container behavior, concurrency and answer quality remain unproved.
- The runtime consumes the published `@earendil-works/pi-coding-agent` 1.4.0 package. The Dime Pi fork exists for future patches but is not the artifact this runtime builds.

## Data

The warehouse is DuckDB, built from the `dime-data-20260930` pack and exposed read-only. `warehouse_schema` reports declared columns, units and season encodings so the model can write valid SQL without guessing.

## Source map

- [HTTP and SSE routes](backend/v2/api/routes.py)
- [Product session producer](backend/analyst/product_session.py)
- [Pi worker](backend/analyst/worker.mjs)
- [Python MCP tools](backend/analyst/python_tools.py)
- [MCP bridge and structured results](backend/analyst/python-tools.mjs)
- [Source artifact lookup](backend/analyst/sources.py)
- [Conversation ledger](backend/v2/conversations.py)
- [Typed contracts](backend/v2/contracts.py)
- [Runtime decision](docs/adr/0001-pi-analyst-runtime.md)
- [Analyst module notes](backend/analyst/README.md)

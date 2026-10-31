# Chat acceptance contract

This reference describes the current TypeScript product host. See the [architecture](../ARCHITECTURE.md) and [domain glossary](../GLOSSARY.md) for ownership and terminology.

## 1.1 Endpoints and runtime mode

The Node HTTP host serves both `POST /api/v2/chat/stream` and query-style `GET /api/v2/chat/stream`. The `/api` prefix is required. Route behavior is defined in `backend/analyst/http.ts`.

`DIME_RUNTIME_V2` defaults to `on` when unset or empty. `on` and `action_loop` enable the same Pi producer; `off` and `shadow` return 404 for chat and the other gated product routes. Workspaces are not gated by this setting. Unknown mode values fail configuration.

## 1.2 Request body

POST accepts JSON matching `analystRequestSchema` in `backend/analyst/analyst.ts`. Unknown fields return 422. Malformed JSON returns 422 with a structured `detail` array; native parser diagnostic text can vary by Node version.

| Field | Contract |
| --- | --- |
| `q` | Required nonblank string, at most 2,000 characters. |
| `model` | Optional string or null; nonblank when supplied, at most 256 characters. |
| `history` | Optional array of at most eight user or assistant turns. Each turn has `role` and nonblank `content` of at most 2,000 characters. |
| `thread` | Optional string or null; nonblank when supplied, at most 80 characters. |
| `client` | Optional string or null; nonblank when supplied, at most 80 characters. |
| `diagnostics` | Optional boolean, accepted for request compatibility. It does not enable typed claim verification. |

A thread requires a client. A client supplied without a thread does not create an identified conversation. Identified requests load stored history and prior source references; anonymous requests use inline history. A successful identified exchange persists both user and assistant turns, run records and branch references. It does not persist typed per-claim evidence bindings.

Model selection is implemented in `backend/analyst/providers.ts`: request `model`, then `DIME_V2_MODEL`, then a configured provider default. Unsupported selections or missing credentials produce a `configuration` failure stream. There is no silent fallback to another model.

## 1.3 Stream protocol

Events use SSE framing: `event: <name>\ndata: <json>\n\n`. The media type is `text/event-stream; charset=utf-8`. An admitted chat request gets HTTP 200 and an `X-Dime-Run-Id` header; data arrives as events become available. A rate-limited request has its own failure stream and does not allocate a run id.

| Event | Payload |
| --- | --- |
| `token` | `{text}` containing an incremental text delta. |
| `tool_call` | `{node: "tools", name, data: {}}`. |
| `tool_result` | `{node: "tools", name, status}` with optional row count or public error text. Status is `ok` or `fail`. |
| `work_log` | `{run_id, status: "partial"}` identifying the execution attempt. |
| `final_answer` | `{text, carry}` containing the settled answer. |
| `failure` | `{kind, message}` describing configuration, startup, model, transport, timeout or rate-limit failure. |
| `error` | `{message}`, emitted with rate-limit rejection. |
| `graph_end` | `{}`, the terminal event. |
| `ping` | `{ok: true}`, sent after 15 seconds without other output. |

Use `final_answer.text` as the complete answer. A stream that ends before its terminal event must not be treated as a successful complete answer.

`CHAT_RATE_PER_MINUTE` defaults to 20 and applies an in-process window per socket client address. Rate-limit rejection returns HTTP 200 with `failure`, `error` and `graph_end` events. `DIME_V2_RUN_TIMEOUT_S` defaults to 360 seconds; timeout aborts the analysis and terminates the stream. A separately authorized diagnostic may impose a shorter deadline.

## 1.4 Sources and verification

A final answer carries:

```json
{
  "run_id": "run-...",
  "verification": "unassessed",
  "answer_status": "unassessed",
  "source_refs": ["..."]
}
```

These are run-level source references, including records of failed tool calls. They are not claim-level citations or verification results. Completing a run does not establish that its answer is supported.

For an identified conversation, retrieve the raw records through:

```text
GET /api/v2/runs/<run_id>/sources?thread=<thread>&client=<client>
```

The response contains `run_id` and `sources`. Each source record contains `ref`, `callId`, `tool` and its complete MCP `response`. The two Python agent tools are `sql_exec` and `warehouse_schema`; `read_source` reads an existing record inside codemode. Source retrieval checks the conversation's owner/thread/run association. Client and thread values are scoping identifiers, not authentication credentials.

Raw records retain rows, declared units, season semantics, provenance and failures. The host supplies prior-source summaries to the model; scripts choose which results to return from codemode. The current answer path does not emit `verified_claims`, typed per-output provenance or `unverified_numbers`.

## 1.5 Local build and startup

Install Python data dependencies and locked Node dependencies, then build the TypeScript host:

```bash
python -m pip install -r backend/requirements.txt
cd backend/analyst
npm ci --ignore-scripts
npm run build
```

Node 22.19.0 or later and an existing warehouse are required. Configure the desired provider through its existing key and activation settings; select an approved model from `/api/models`. `DIME_WAREHOUSE` overrides the default `backend/data/warehouse.duckdb`. `DIME_PI_PYTHON` can select the Python executable for the data engine.

Generate the asset manifest from `backend/`, outside executable roots:

```bash
node analyst/dist/host.js manifest manifest/expected_asset_manifest.json
```

Start the product host with that manifest:

```bash
DIME_EXPECTED_ASSET_MANIFEST=$PWD/manifest/expected_asset_manifest.json \
  node analyst/dist/host.js
```

`preflight` in `backend/analyst/manifest.ts` rejects a missing manifest or substantive asset mismatch. A revision-label-only mismatch is reported separately. `PORT` defaults to 8000; `CORS_ALLOWED_ORIGINS` configures allowed browser origins. Workspace `PATCH` is included in allowed preflight methods.

The CLI uses the same analyst module without starting an HTTP listener:

```bash
node analyst/dist/host.js chat "What were the top scoring games?" --model provider:model
```

`GET /api/health` reports the host/provider catalogue. `GET /api/healthz` checks warehouse readiness and can return 503. Successful local fixtures do not establish live-provider coverage, container execution or analyst answer quality.

## 1.6 Corpus schema (JSONL; v2 items)

The corpus lives at `acceptance/corpus.jsonl` (written in a later step; this step only
defines and validates the schema). One JSON object per line, keys and types exactly:

```json
{
  "id": "str, unique, e.g. 'qa-0001'",
  "question": "str",
  "category": "exact | compound | citation | honest_gap | scope",
  "expect_numbers": ["str...", "optional list of numbers that must appear in the final text"],
  "must_contain": ["str...", "optional substrings required in the final text"],
  "must_not_contain": ["str...", "optional substrings forbidden in the final text"],
  "expect_refusal": "bool, true => the run SHOULD refuse to answer (no gold)",
  "gold_sql": "str, a single duckdb SQL statement run against backend/data/warehouse-runtime.duckdb",
  "notes": "str, free-form grader hint",
  "expected_category_of_gold": "exact | compound | citation | honest_gap (grader-derived)"
}
```

Rules:
- `expect_refusal=true` ⇒ `gold_sql` must be null/empty and the expected answer is a
  refusal (the warehouse genuinely lacks the data, e.g. future seasons, unknown players).
- Otherwise `gold_sql` must be present, non-empty, valid duckdb SQL, and must return a
  single scalar (or a single-column, single-row set reduced to a scalar by the grader).
  Read-only `SELECT` only.
- `category` must be exactly one of `exact|compound|citation|honest_gap|scope`.
- `expected_category_of_gold` is grader-derived and uses the first four categories only.
- `expect_numbers`, `must_contain`, `must_not_contain` are optional (may be absent).
- No duplicate `id`; `id` must be stable across passes.

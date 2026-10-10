# Chat API contract & corpus schema (acceptance, step 1)

This file is the contract that the acceptance runner (step 2+) codes against. Every
claim below was verified against the source in this repository.

## 1.1 Endpoint inventory

- **HTTP method + path (public URL):** `POST /api/v2/chat/stream`, and a query-style
  `GET /api/v2/chat/stream`.
  The route decorators are declared router-relative as `@router.post("/v2/chat/stream")`
  and `@router.get("/v2/chat/stream")` in `backend/v2/api/routes.py`, and
  `backend/v2/main.py` mounts that router with `app.include_router(v2_router, prefix="/api")`.
  **The `/api` prefix is part of the served path** — the bare `/v2/chat/stream` form is
  not served.
- **Server:** FastAPI. `backend/entrypoint.py` imports `v2.main:app`, so the ASGI target
  is `entrypoint:app` (`uvicorn entrypoint:app` from the `backend/` directory).
- **Runtime mode gate:** `DIME_RUNTIME_V2` selects the mode and defaults to `off`
  (`backend/shared/config.py`, `runtime_v2_mode()`; accepted values `off` | `on` | `shadow`).
  The chat stream is served **only when the mode is `on`**: `quick_answer_stream` calls
  `_require_projects()` first, which raises HTTP 404 `{"detail":"not found"}` unless
  `runtime_v2_mode() == "on"`. `shadow` also 404s on this endpoint — shadow suppresses
  publication of the success path, it does not open the route.
- **Local start (live):** see [1.5](#15-how-to-start-the-backend-locally).
- **Source of truth for the route:** `backend/v2/api/routes.py`.

## 1.2 Request body (JSON)

Body model is `QuickAnswerBody` in `backend/v2/api/routes.py`
(`model_config = ConfigDict(extra="forbid")` — unknown keys are rejected with 422).
Keys are **required** unless marked optional.

| Field | Type / constraints | Meaning |
|---|---|---|
| `q` | string, `min_length=1`, `max_length=2000`, non-blank | the user question |
| `model` | optional string, `max_length=256`, non-blank when present | model id; see resolution order below |
| `history` | optional array of conversation turns, at most **8** items | prior turns supplied inline |
| `thread` | optional string, `min_length=1`, `max_length=80`, non-blank | conversation thread id |
| `client` | optional string, `min_length=1`, `max_length=80`, non-blank | client / conversation owner id |
| `diagnostics` | optional bool, default `false` | include the observability payload |

- `thread` and `client` must be supplied **together**; supplying `thread` alone is a
  validation error (`require_complete_conversation_identity` → HTTP 422).
- **Model-resolution order:** `body.model` → `DIME_V2_MODEL` env var → provider default.
  The route passes `body.model or os.environ.get("DIME_V2_MODEL")` to
  `shared.providers.resolve_model_id`; an unresolvable/unknown id makes the run fail with
  a `startup` failure stream rather than falling back.
- **Conversation behaviour when `thread` and `client` are both given:** the route *reads*
  stored history from the conversation store to seed the model context. On a successful run
  it also *writes* the exchange back (assistant turn, per-turn evidence, an optional branch
  off the parent sequence, and a saved chat/run record). It is not a read-only lookup.

## 1.3 Stream protocol

All events are Server-Sent Events (`event: <name>\ndata: <json>\n\n`).

- **Response media type:** `text/event-stream; charset=utf-8`
  (`StreamingResponse(..., media_type="text/event-stream")`). It is **not**
  `text/plain; charset=utf-8`.
- **Status code:** 200 with an immediate stream; the HTTP body is empty until the first
  event arrives.
- **Response header:** `X-Dime-Run-Id` carries the run id (also present on the startup
  failure stream).
- **Heartbeat:** the stream is wrapped in `with_heartbeat`, which injects a
  `ping` event (`{"ok":true}`) whenever **15s** elapse without backend output. A runner
  must tolerate `ping`.
- **Payload truncation:** every payload passes through
  `backend/v2/api/sse.py` `_public_payload` (which rewrites or drops fields per event
  type) and then `_bounded_public_value` (depth ≤ 8, ≤ 1000 list items, ≤ 256 dict keys,
  ≤ 1000-char keys, strings truncated to 200 000 chars, non-finite floats → `null`).

Event types the runner MUST parse:

| Event | Public fields |
|---|---|
| `node_update` | `{node, status}` — node in `entry`\|`data_retrieval`\|`tools`\|`analytics`\|`presentation`, status `running`\|`complete`\|`error` |
| `status` | `{text}` — short status, max 500 chars |
| `thought_stream` | `{node, text}` — the public payload always replaces `text` with the fixed string `"Working through the evidence..."`; treat it as a progress ping, not real reasoning |
| `tool_call` | `{node, name, data}` — `data` holds `{name, arguments, argument_count, unknown_argument_count}` |
| `tool_result` | `{node, name, status, rows, ms, error}` — `status` is `ok`\|`fail`; `rows` is a row count, not the rows; `error` is non-null only when `status=fail` (always the string `"Tool failed"`) |
| `token` | `{text}` — incremental answer tokens (emitted in ~12-word chunks) |
| `custom_data` | `{node, tables, artifacts, unverified_numbers}` — `node` is always `analytics` on this endpoint |
| `work_log` | `{run_id, status}` — `complete` \| `partial` |
| `final_answer` | `{text, carry}` — the final text plus the `carry` provenance dict |
| `suggestions` | `{items}` — event type is defined in `backend/v2/api/events.py` but is **not emitted** by `/api/v2/chat/stream`; the runner may accept it but must not wait for it |
| `graph_end` | `{}` — always the last event of every terminal stream |
| `failure` | `{kind, message}` — kinds: `startup`, `rate_limited`, `timeout`, `quota`, `provider_error`, `execution_failure` |
| `binding_diagnostic`, `run_diagnostic` | emitted only when `diagnostics=true` |
| `stage_summary`, `plan_update`, `evidence_update`, `verification_update` | emitted from the activity journal when `diagnostics=true` |

- **Startup failure stream** (`setup_error_stream`): `failure` (`kind="startup"`) →
  `error` (`{"message","run_id"}`) → `graph_end`, with HTTP status **200**.
- **Rate-limited stream** (`_rate_limited_stream`): `failure` (`kind="rate_limited"`) →
  `error` (`{"message":"rate limited, retry soon"}`) → `graph_end`, HTTP status 200.
- **Run failure mid-stream** (`failure_chunks`): optional diagnostics and replayed
  `tool_call`/`tool_result` events, then `failure`, `work_log` (`status="partial"`),
  `token` events, and a `final_answer` whose `carry.verification` is `"partial"`, then
  `graph_end`. **A runner must not assume `failure` means there is no final answer.**
- **Rate limiting:** both `POST` and `GET /api/v2/chat/stream` go through
  `_guarded_chat_stream` → `_chat_allowed`. The limiter is **per client IP**, a **60-second
  sliding window**, capped by `settings.chat_rate_per_minute` (default **20**). Exceeding it
  yields the rate-limited stream above rather than an HTTP 429. The limit is in-process and
  per-worker.

## 1.4 Where citations/provenance and final text live

- **Final answer text:** the `text` field of the `final_answer` event. The preceding
  `token` events are the same text streamed in chunks; use `final_answer.text` as the
  authoritative answer.
- **Provenance (`carry`):** the `carry` dict on the same `final_answer` event. Its keys are:

  | Key | Type |
  |---|---|
  | `run_id` | string (`run-<32 hex>`) |
  | `verification` | string (`pass` → `work_log.status=complete`, otherwise `partial`) |
  | `verified_claims` | **integer count** of verified claims (not a list) |
  | `output_statuses` | array of per-output status records |
  | `structural_flags` | array |
  | `gaps` | array of `{kind, blocks}` |
  | `stage_latencies_ms` | object of step id → duration |

  On the mid-stream failure path `carry` is a reduced dict
  (`run_id`, `verification="partial"`, `verified_claims=0`, `structural_flags`, `gaps`,
  `stage_latencies_ms`) with no `output_statuses`.

  The runner only needs the presence of `carry` and of its `verified_claims` / `gaps` keys;
  it must not assume `verified_claims` is a list.
- **Per-claim evidence provenance:** published in the `custom_data` event as
  `tables[].provenance`, one object per cited output:
  `{capability, origin, warehouse_id, season, as_of, live_sources}` where `origin` is
  `warehouse` | `live` | `mixed` | `undeclared`. Each table row also carries
  `output_id`, `display_name`, `subject_type`, `subject_id`, `subject_display_name`,
  `value`, `unit`.
- **Untraceable numbers:** `custom_data.unverified_numbers` — human-readable strings naming
  outputs that could not be traced back to evidence.
- Refusal detection and fabrication flagging are the grader's job in a later step, not part
  of the runner in this step.

## 1.5 How to start the backend locally

- Install Python deps: `pip install -r backend/requirements.txt`
  (includes `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`,
  `pydantic-ai-slim[openai]`, `httpx`, `duckdb`, `polars`, `sqlglot`).
- **Two required environment settings before uvicorn will even start:**

  1. `DIME_EXPECTED_ASSET_MANIFEST` — the FastAPI lifespan in `backend/v2/main.py` calls
     `preflight_runtime_assets()` with no argument, and that function raises
     `RuntimeError("DIME_EXPECTED_ASSET_MANIFEST is required")` when the variable is unset.
     Without it the app **crashes on startup**. The manifest file must live outside
     `backend/app` and `backend/v2`.
  2. `DIME_RUNTIME_V2=on` — any other value (including the default `off` and `shadow`)
     makes the chat stream return HTTP 404.

- Start:

  ```
  cd backend
  DIME_RUNTIME_V2=on DIME_EXPECTED_ASSET_MANIFEST=<path/to/manifest.json> \
    uvicorn entrypoint:app --host 127.0.0.1 --port 8000
  ```

  Set `DIME_V2_MODEL` to pin the model; leave it unset to use the provider default.
- **Health:** `GET /api/health` (`{"ok":true,"providers":{...}}`) and `GET /api/healthz`
  (503 unless the `silver_team_ratings` table is present and non-empty).
- **Smoke check:**

  ```
  curl -N -X POST http://127.0.0.1:8000/api/v2/chat/stream \
    -H 'Content-Type: application/json' -d '{"q":"test"}'
  ```

  Expect a `final_answer` event with non-empty `text` and a `carry` object, terminated by
  `graph_end`.
- **Warehouse:** `backend/data/warehouse-runtime.duckdb` — a duckdb file in the repo used
  to compute gold answers. Gold SQL is read-only (`SELECT` only; open read-only). Do not
  point the runner at a path outside this repository.

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
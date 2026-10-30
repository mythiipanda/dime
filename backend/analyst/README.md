# Pi analyst module

This module implements Pi codemode, a read-only Python tool bridge, and a Python-owned product-session producer. The production `/api/v2/chat/stream` route still uses the existing Python runtime. This slice does not cut over that route.

## Product-session producer

`product_session.py:stream_product_session` owns one Node worker for one request. The caller supplies the resolved model descriptor, absolute Node/Python executables, an explicit isolated environment, private temporary directory, durable source directory, existing ConversationStore, and product storage implementation. The caller must cancel or close the generator on HTTP disconnect. There is no new runtime flag or daemon.

`resolved_provider` accepts the provider and ChatOpenAI client already selected by `shared.providers.resolve_model_id/get_llm`, plus explicit model limits. It reads no configuration files and does no inference. Unsupported extra request bodies fail configuration rather than disappearing silently. The descriptor travels over stdin, never command arguments or logs. The worker uses an in-memory credential store and disables model discovery. Compatibility with actual product providers remains unproved.

The worker creates a real AgentSession with the real Python MCP catalogue. Pi owns model/tool calls and recovery. Python maps tool activity to existing validated SSE events, buffers the answer until the worker settles, and emits exactly one graph_end on completed/error streams. A broken worker EOF produces a transport failure. HTTP EOF without graph_end remains a frontend error. Cancellation requests Pi abort, then disposes the session and closes MCP. A five-second graceful-cleanup deadline falls back to terminating the owned process tree.

Identified conversations read the existing store's latest eight turns, overriding body history. Anonymous context is capped at eight too. These turns seed the in-memory Pi transcript; no durable Pi session is created. Human chat is recorded before startup. After a successful worker outcome, Python stores the complete source envelopes under `<run_id>.json`, writes existing assistant chat/run storage, and appends the conversation exchange with a run reference. Failed model outcomes retain any collected source envelopes and do not append an assistant exchange. Existing storage methods remain separate writes, as in the current route.

Answers carry `verification: unassessed` and `answer_status: unassessed`. No verified_claims count, deterministic/semantic verification result, or complete work-log status is invented. The frontend parses this as unknown verification with an absent claim count. Full source records preserve refs, raw MCP content, domain failures, units and source annotations. The artifact is evidence storage, not an adjudication result or another conversation store.

Source refs are retained in carry but are not rendered as legacy citations. Authenticated retrieval of those artifacts, citation display, branch evidence reuse, domain publication policy, route-level disconnect tests, and actual provider compatibility remain cutover gates. There is no legacy EvidenceEnvelope conversion or fake verification object. The current producer covers only sql_exec/schema and buffers answer text rather than streaming model deltas.

## Product-session fixture commands

Use `python verify_product.py ABSOLUTE_FRESH_DIRECTORY prepare`, then `python verify_product.py SAME_DIRECTORY test_session`. Run each command under the ordinary supervisor independently. Other targets are `test_followup`, `test_startup`, `test_model`, `test_bridge`, and `test_cancel`, each with its own prepared directory. `test_recovery` runs against the directory from a failed request and proves a subsequent normal request can persist an exchange. All environments are isolated before product imports, all databases and product stores are synthetic, and all model responses come from `product_fixture.mjs` through the actual ModelRuntime.

The fixture invokes actual product storage functions in short-lived Python processes between Pi workers to stay within the ordinary memory cap. This proves storage behavior but does not establish memory use of the full production web host with all dependencies resident. The host, Node worker, QuickJS worker and real Python MCP tools execute together. Fixture assertions inspect raw source artifacts, persisted history, provider-observed prior context, terminal counts, failure distinctions and process exit before supervisor cleanup.

`frontend_fixture.mjs` consumes captured `normal-sse.json` using the actual `frontend/lib/api.ts:postChatStream` and `parseCarry`. Run `python verify_product.py CAPTURE_ROOT frontend ABSOLUTE_TSX_LOADER`, where CAPTURE_ROOT is the directory passed to the producer fixture and the loader is the frontend's `node_modules/tsx/dist/loader.mjs`. The launcher isolates its environment too. It checks split SSE frames, terminal success, unterminated EOF error and unknown verification without a fabricated claim count. It does not require a frontend build or live HTTP/model server.

## Session contract

Import createAnalystSession from runtime.mjs. Supply absolute private cwd and agentDir directories, the product-selected model and modelRuntime, trusted Pi tool definitions, and optional in-memory Pi settings. The caller owns model credentials and directory lifetime. Do not supply a developer's profile directories or a runtime initialized from personal credentials.

The factory does no work at import time. It returns a real Pi AgentSession with an in-memory session manager. The caller owns prompt, subscribe, abort, and dispose. Only codemode is active for model declarations. Analysis tools have codemode exposure and remain callable from scripts. The exact same supplied definitions provide schemas and execution. No built-in file, shell, edit, write, network, MCP, classifier, or image tools are enabled.

Settings do not load from disk. Resource discovery disables external extensions, skills, prompts, themes, and context files. The only extension factory is Pi's public createCodemodeExtension. The model runtime is an explicit trusted dependency, so its configuration remains the caller's responsibility.

Pi executes JavaScript in its QuickJS worker. It handles batching, tool validation, output filtering, and cancellation. There is no Dime script executor or workflow manager. Full results and source references belong to the analysis adapter. The bridge retains full MCP responses in a host Map for its lifetime. The product producer writes raw source artifacts; authenticated citation retrieval remains unimplemented.

## Python tools

connectPythonTools in python-tools.mjs starts one explicit Python MCP stdio process using Pi's pinned McpClient and StdioTransport. Supply an absolute Python executable, private cwd, and a minimal environment containing an absolute DIME_WAREHOUSE pointing to an existing database. Environment inheritance is disabled. No MCP configuration files, profile servers, dotenv loader, or old Runtime assembly are used. Call close in the owner's finally block after disposing the session.

Pass the returned tools to createAnalystSession. Only sql_exec and warehouse_schema are accepted. Python generates schemas and descriptions from the same LangChain tool objects it invokes. warehouse_schema uses league._get_warehouse_schema and season_semantics.annotate_schema. sql_exec keeps its existing validation, row cap, timeout, source annotations, and error contract. WAREHOUSE_TOOLS is not exported because it includes mutators and run_python.

Each call returns a JSON text envelope containing ref, Pi callId, tool, and the complete MCP response. results maps each unique ref to that envelope, including domain failures and MCP errors. Domain errors preserve ok:false; invocation/validation exceptions preserve MCP isError and their messages. A script reads response.content[0].text for the original domain result and can filter it before returning to the model. The adapter does not infer units from aliases or rewrite rows. This storage is process-local, not a durable citation registry.

The Python MCP server uses the 2.3.0 constructor-handler API pinned in backend/requirements.txt. Blocking tool implementations run in worker threads so the MCP event loop can receive independent calls and cancellation. AbortSignal reaches the MCP client request; interruption of an already-running DuckDB worker is still governed by the existing SQL timeout. Producer cancellation is fixture-tested. Immediate SQL interruption and HTTP disconnect propagation through the production route remain unproved.

## Reproduce the integration proof

Use Node >=22.19.0 and Python with backend/requirements.txt installed. Install the locked dependencies with npm ci --ignore-scripts in this directory. Run npm test. Run npm run check for session syntax alone.

verify.py resolves Node and the module explicitly, creates private cwd, home, and temp directories, and launches checks and node --test with a minimal environment. Pass a fresh absolute artifact directory to python verify.py to retain its fixture directories. It never loads .env or real model credentials. Tests register a synthetic provider in the real ModelRuntime and exercise real AgentSession.prompt and Pi's actual codemode tool. The provider returns scripted messages without HTTP. This establishes integration behavior, not analyst answer quality.

The proof checks these behaviors:

- Two asynchronous registered tools must both enter before either returns. Promise.all therefore proves overlapping execution without a timing threshold.
- The next provider request contains only the filtered rows and both result refs. Full raw rows remain in the host Map. Per-game and cumulative units and season encodings survive without inference from labels.
- The thrown tool error message survives Promise.allSettled, together with a successful sibling result.
- AgentSession.abort reaches the nested tool's AbortSignal and settles the session.
- Project context and deliberately failing profile extensions are not loaded. Callable tools contain only the supplied catalogue, and the provider sees only the codemode declaration.
- An owned synthetic DuckDB fixture is created before shared tool imports with DIME_WAREHOUSE already set. Direct sql_exec and actual Pi QuickJS calls over MCP return equivalent complete results, excluding only elapsed milliseconds. Tests compare rows, source provenance, column units, and season annotations. PTS AS total_points remains points_per_game for historical rows; cumulative leader PTS remains total_points.
- Six overlapping requests include valid queries, no rows, a missing column, an unavailable table, and a refused write. Every response keeps a distinct ref and Pi call identity. A subsequent successful query in the same Pi script proves recovery. Raw rows stay in the Map while the next provider context sees filtered rows. MCP validation errors also leave the process usable. close is awaited and the Python PID must no longer exist.

Apply the repository's ordinary resource supervisor around verify.py for bounded verification. Limits are 30 seconds, 1 GiB committed memory, 32 processes, and 1 MiB per output stream. Supervisor configuration remains outside this production module.

## Source ownership and dependency pins

Dime's source fork is https://github.com/mythiipanda/dime-pi. Upstream is https://github.com/earendil-works/pi.git under MIT. The selected source tag is v1.4.0 at commit 4a080252f06caf63a525d7873c5d94d3c23887e0. Fork creation was performed by the parent coordinator. This module consumes the published upstream package @earendil-works/pi-coding-agent exactly 1.4.0, with registry integrity in package-lock.json. It does not claim to consume a Dime-built fork artifact.

For a source patch, clone the Dime fork into a separate source checkout, add upstream as a remote, fetch tag v1.4.0, and verify git rev-parse v1.4.0^{commit} against the commit above. Create the patch branch from that commit, retain upstream history and MIT notices, and apply the smallest reviewed patch. Build and test the package with upstream's documented build procedure. Publish or install an immutable Dime artifact only after review, then replace this package pin and regenerate the lock. Record the fork revision, patch rationale, artifact integrity, and this integration proof together. Do not install fork HEAD. There are currently no Dime core patches or Dime package artifacts.

The sole dependency override pins Pi's undici dependency to 8.12.2. Pi 1.4.0 otherwise pins 8.10.2. The patched version keeps the same Node >=22.19.0 requirement. The npm advisory range is >=8.0.0 <8.12.2. See https://github.com/advisories/GHSA-xjj6-f33q-929c for the malformed content-encoding crash and patched version. The same release clears the other findings in the current npm audit. This is a patch-level dependency override, not a Pi downgrade. Codemode integration passes with it; real provider transport validation remains part of product integration.

## Migration plan and architecture decision

Keep Python's HTTP, SSE, authentication, product storage, and existing analysis implementations. Pi owns the conversation, model calls, tool choice, recovery, compaction, and JavaScript execution. Use a narrow local process adapter. Add no shared daemon or multiplexer without a demonstrated product requirement.

1. Establish the SDK slice. Pin source and package provenance, isolate resources and tools, and prove actual parallel scripts, filtered output, raw refs, errors, and cancellation. This module implements that integration gate. Independent parent verification and review remain required.
2. Connect Python domain tools. This module implements the read-only sql_exec/schema slice and synthetic equivalence proof described above. Broader tool selection and durable citation ownership remain for product integration. No real database or model is used by this proof.
3. Preserve product sessions and events. The new producer and synthetic host/worker/MCP fixtures cover a bounded part of this stage. Production route publication, branch reuse and authenticated source retrieval remain open.
4. Cut over the chat caller. Add supported Node packaging and startup, run existing stream checks against Pi events, and route ordinary analyst requests through Pi. Deployment is a separate action.
5. Delete replaced orchestration after caller inventory. Remove staged Runtime, ActionRuntime, PlanExecutor, workflow-only planning and repair prompts, and obsolete tests. Retain shared source facts and product contracts with their consumers.
6. Evaluate actual answers separately. Inspect representative analysis, source limitations, season units, historical scope, mixed evidence, and follow-up. Record completion, grounded claims, unresolved branches, requests, latency, and failures. Synthetic provider tests do not establish answer quality.

The critical path is SDK execution, Python equivalence, product stream compatibility, caller cutover, then deletion. Each stage ends in an observable check. No old planning stages are reintroduced inside the adapter. No migration-complete claim is justified until production caller, packaging, deletion, and representative outcome gates pass.

## Current caller and deletion inventory

`backend/v2/api/routes.py:quick_answer_stream` and `backend/scripts/run_v2_chat.py` still call `v2.runtime.assembly.build_runtime`. The route selects existing Runtime/ActionRuntime behavior and derives publication from legacy execution/verification objects. Assembly constructs Runtime/ActionRuntime and PlanExecutor, implemented in `runtime/loop.py`, `runtime/action_loop.py`, and `runtime/executor.py`. None are rerouted by this slice.

Assembly also exports `declared_schema_for`, consumed twice in `v2/adapters/models.py`, and `capability_catalog`, consumed by `v2/runtime/recording.py`, `evals/validate_typed_argument_binding.py`, and root `scripts/regen-capability-snapshots.py`. The route's publication helper also imports `JUDGE_UNAVAILABLE_BRANCHES` from runtime/loop.py. These dependencies must move or disappear with their actual consumers before deletion. Runtime exports in `v2/runtime/__init__.py` and tests need a final import sweep at cutover. No legacy source has been deleted merely to make old tests disappear.

After route cutover, remove unused staged runtime/ActionRuntime/PlanExecutor, planning and repair prompts, and route-only ledger/verification glue with their callers. Retain existing SSE events, conversation and product stores, provider resolution, SQL/schema implementations, source semantics and frontend consumer. Retained domain publication rules need their own honest representation and tests, not old orchestration inside Pi.

`backend/Dockerfile` is still Python-only and does not copy/install this analyst package. Packaging must provide Node >=22.19.0 and install locked dependencies before route cutover. No warehouse image build is part of this fixture or this slice.

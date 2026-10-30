# Pi analyst module

This module establishes Pi codemode execution and a read-only Python tool bridge for the analyst migration. The production chat caller still uses the existing Python runtime. Product streaming, persistence, packaging, and caller cutover remain to be implemented.

## Session contract

Import createAnalystSession from runtime.mjs. Supply absolute private cwd and agentDir directories, the product-selected model and modelRuntime, trusted Pi tool definitions, and optional in-memory Pi settings. The caller owns model credentials and directory lifetime. Do not supply a developer's profile directories or a runtime initialized from personal credentials.

The factory does no work at import time. It returns a real Pi AgentSession with an in-memory session manager. The caller owns prompt, subscribe, abort, and dispose. Only codemode is active for model declarations. Analysis tools have codemode exposure and remain callable from scripts. The exact same supplied definitions provide schemas and execution. No built-in file, shell, edit, write, network, MCP, classifier, or image tools are enabled.

Settings do not load from disk. Resource discovery disables external extensions, skills, prompts, themes, and context files. The only extension factory is Pi's public createCodemodeExtension. The model runtime is an explicit trusted dependency, so its configuration remains the caller's responsibility.

Pi executes JavaScript in its QuickJS worker. It handles batching, tool validation, output filtering, and cancellation. There is no Dime script executor or workflow manager. Full results and source references belong to the analysis adapter. The bridge retains full MCP responses in a host Map for its lifetime. Durable citation storage remains unimplemented.

## Python tools

connectPythonTools in python-tools.mjs starts one explicit Python MCP stdio process using Pi's pinned McpClient and StdioTransport. Supply an absolute Python executable, private cwd, and a minimal environment containing an absolute DIME_WAREHOUSE pointing to an existing database. Environment inheritance is disabled. No MCP configuration files, profile servers, dotenv loader, or old Runtime assembly are used. Call close in the owner's finally block after disposing the session.

Pass the returned tools to createAnalystSession. Only sql_exec and warehouse_schema are accepted. Python generates schemas and descriptions from the same LangChain tool objects it invokes. warehouse_schema uses league._get_warehouse_schema and season_semantics.annotate_schema. sql_exec keeps its existing validation, row cap, timeout, source annotations, and error contract. WAREHOUSE_TOOLS is not exported because it includes mutators and run_python.

Each call returns a JSON text envelope containing ref, Pi callId, tool, and the complete MCP response. results maps each unique ref to that envelope, including domain failures and MCP errors. Domain errors preserve ok:false; invocation/validation exceptions preserve MCP isError and their messages. A script reads response.content[0].text for the original domain result and can filter it before returning to the model. The adapter does not infer units from aliases or rewrite rows. This storage is process-local, not a durable citation registry.

The Python MCP server uses the 2.3.0 constructor-handler API pinned in backend/requirements.txt. Blocking tool implementations run in worker threads so the MCP event loop can receive independent calls and cancellation. AbortSignal reaches the MCP client request; interruption of an already-running DuckDB worker is still governed by the existing SQL timeout. Immediate SQL interruption and product disconnect ownership need proof at the product-session stage.

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
3. Preserve product sessions and events. Inspect current follow-up and persistence lifetimes, map Pi events to the frontend stream, and prove cancellation and terminal outcomes through the host and bridge. Keep configuration failures distinct from tool failures.
4. Cut over the chat caller. Add supported Node packaging and startup, run existing stream checks against Pi events, and route ordinary analyst requests through Pi. Deployment is a separate action.
5. Delete replaced orchestration after caller inventory. Remove staged Runtime, ActionRuntime, PlanExecutor, workflow-only planning and repair prompts, and obsolete tests. Retain shared source facts and product contracts with their consumers.
6. Evaluate actual answers separately. Inspect representative analysis, source limitations, season units, historical scope, mixed evidence, and follow-up. Record completion, grounded claims, unresolved branches, requests, latency, and failures. Synthetic provider tests do not establish answer quality.

The critical path is SDK execution, Python equivalence, product stream compatibility, caller cutover, then deletion. Each stage ends in an observable check. No old planning stages are reintroduced inside the adapter. No migration-complete claim is justified until production caller, packaging, deletion, and representative outcome gates pass.

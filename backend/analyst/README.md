# Pi analyst module

`/api/v2/chat/stream` uses `stream_product_session`. Pi owns tool selection, recovery, compaction and codemode. Python owns HTTP/SSE, request validation, runtime gating, rate limits, model policy, owner/thread context, product persistence and raw source storage. There is no alternate legacy chat producer.

## Runtime and configuration

The backend Dockerfile installs locked analyst dependencies in the `analyst-deps` stage using `node:22.19.0-bookworm-slim`, then copies Node and the analyst assets into the Python image. It does not copy `backend/workspaces`, although `backend/entrypoint.py` imports `workspaces.routes` unconditionally; a built image would fail at container startup during import. No image build or deployment was performed for this document. `packaging_fixture.py` checks the analyst boundary and imports the installed SDK without building an image or opening a database.

The route resolves the selected model through `resolve_product_model`. Reflection retains its explicit activation and key policy. No fallback provider is added. Other supported model limits come from the pinned SDK catalogue; absent metadata is a configuration failure.

Resolved credentials travel over worker stdin, never argv, logs or source artifacts. The worker uses an in-memory credential store with discovery disabled. MCP receives an explicit environment without provider credentials. The isolated session disables profile resources, extensions, skills, prompts, themes and built-in filesystem/shell tools. This is not a network sandbox: provider transport still needs outbound HTTP, and `allowModelNetwork: false` only stops model-catalogue network access. The Python MCP catalogue is exactly `sql_exec` and `warehouse_schema`; the worker adds `read_source` separately. Native Pi retry defaults remain intact.

One bounded live-provider Beam run completed before the latest structured-result change. Its sources supported per-game statistics; exact totals were unresolved and its answer was unassessed. The structured-result change has fixture proof only. Broad provider compatibility, container behavior, concurrency and answer quality remain open.

## Sessions, sources and events

Identified turns load the latest eight turns from ConversationStore. Client/thread values provide the existing owner scoping; they do not establish authentication. Anonymous turns use request history. Successful turns persist assistant chat, run and both conversation turns. Follow-ups create a branch linked to the prior turn and load prior source records for the catalogue through the same owner/thread run references. Failed turns never append an assistant exchange or publish a successful final answer.

`GET /api/v2/runs/{run_id}/sources?thread=...&client=...` requires the same owner/thread ledger association before opening an artifact, and validates artifact run identity. A guessed run id or a different owner cannot retrieve it. Source records preserve MCP content, rows, units, season annotations, provenance and domain failures. They are not EvidenceEnvelope objects or claim adjudication.

The worker forwards Pi text deltas as Token events when emitted. The settled answer remains the final authoritative text. Providers that supply only a complete message use the buffered Token fallback. Failed runs can have partial token text but never a successful final_answer. Carry preserves opaque source_refs, with unassessed verification and no verified_claims count. The frontend retrieves the owner-scoped artifact, renders source tables with declared units and full provenance, and retains the existing unknown verification state.

Starlette disconnect cancels the heartbeat owner. Its cleanup await is shielded from the response cancellation scope, so the producer can abort/dispose Pi and close MCP before returning. The existing five-second graceful cleanup deadline falls back to killing the owned process tree. The existing product run timeout remains in the route.

## Bounded verification

Run each command under the ordinary supervisor separately, with 30 seconds, 1 GiB, 32 processes and 1 MiB per output stream. `python verify_product.py ABS_ROOT prepare` creates an owned synthetic DuckDB before imports. Then use `route_normal`, `route_model`, `route_configuration` or `route_disconnect`, each with a separately prepared root. `route_followup` uses the successful normal root. These tests drive the actual ASGI route with real Pi, QuickJS and Python MCP plus a synthetic provider. Product storage remains resident in the web host.

The shipped worker_environment sets OPENBLAS_NUM_THREADS, OMP_NUM_THREADS and POLARS_MAX_THREADS to one after the unrestricted pools exceeded the ordinary cap. Each session supplies a private home and temp directory. Verification imports that same policy, and the route fixture injects only the synthetic provider entrypoint, model and capture path into the actual worker environment. Normal and disconnect proofs keep product storage resident. Multiple web workers and concurrent requests remain unproved.

`frontend` takes the successful normal capture root and an absolute tsx loader path. It exercises actual postChatStream, split frames, source retrieval, unknown carry, source-table/provenance rendering and incomplete EOF failure. `packaging` checks packaging without DB use. Existing producer-only targets remain available. Synthetic proofs do not establish live-provider compatibility or answer quality.

## CLI

`python backend/scripts/run_v2_chat.py "question" --model provider:model` consumes the same `stream_product_session` as HTTP and resolves models through `resolve_product_model`. It prints the settled answer to stdout, source refs and run identity to stderr, and returns nonzero on failure. Anonymous CLI runs write raw source artifacts without creating a conversation.

`/api/revision` fingerprints Pi product code and its lock, and the `pi_runtime` prompt hash covers the session module containing the system prompt. `DIME_EXPECTED_ASSET_MANIFEST` is required; the manifest must match the deployed assets.

Shared contracts remain because the capability adapters, domain evidence rules, conversation/activity APIs and persisted project records consume them. The three retained runtime modules (`models`, `interfaces`, `verifier`) contain typed evidence binding, immutable views and mechanical source checks. They expose no conversation loop or runtime factory and are not on the Pi product path.

`verify_product.py ABS_ROOT cli_normal`, `cli_model_immediate`, `cli_configuration` and `cli_cancel` exercise the CLI with an injected synthetic provider, owned warehouse and real Pi/MCP. Prepare a separate root before each worker target. The injection is a Python fixture argument, not a production mode or environment flag. Current HTTP normal, follow-up, model/configuration failures and disconnect cleanup also pass with real Pi and synthetic inference.

Retained domain and API checks run in capped batches. Broader tools, representative analyst outcomes, production memory and deployment remain separate work. The dependency pins remain Pi 1.4.0 and undici 8.12.2.

## Source ownership and dependency pins

Dime's source fork is https://github.com/mythiipanda/dime-pi. Upstream is https://github.com/earendil-works/pi.git under MIT. The selected source tag is v1.4.0 at commit 4a080252f06caf63a525d7873c5d94d3c23887e0. This module consumes the published upstream package @earendil-works/pi-coding-agent exactly 1.4.0, with registry integrity in package-lock.json. It does not consume a Dime-built fork artifact.

For a source patch, clone the Dime fork into a separate source checkout, add upstream as a remote, fetch tag v1.4.0, and verify git rev-parse v1.4.0^{commit} against the commit above. Create the patch branch from that commit, retain upstream history and MIT notices, and apply the smallest reviewed patch. Build and test the package with upstream's documented build procedure. Publish or install an immutable Dime artifact only after review, then replace this package pin and regenerate the lock. Record the fork revision, patch rationale, artifact integrity and this integration proof together. Do not install fork HEAD.

The sole dependency override pins Pi's undici dependency to 8.12.2. Pi 1.4.0 otherwise pins 8.10.2. The patched version keeps the same Node >=22.19.0 requirement. The npm advisory range is >=8.0.0 <8.12.2. See https://github.com/advisories/GHSA-xjj6-f33q-929c for the malformed content-encoding crash and patched version. This is a patch-level dependency override, not a Pi downgrade. Codemode integration passes with it; broad real-provider transport validation remains open.

Prior raw records stay in the host map and durable artifacts. Follow-ups receive a catalogue of refs, columns, source units and provenance, not an automatic dump of rows. The codemode-only `read_source` tool reads a ref from the authorized current-conversation catalogue; scripts filter raw rows before returning model-visible output and may return chosen rows. New run artifacts store only newly collected raw records plus source_refs, so follow-ups do not duplicate historical rows. The source API resolves those refs using authorized ledger artifacts, including older artifacts that stored full records.

## Codemode source values

`sql_exec` and `warehouse_schema` from the Python catalogue, and the worker-local `read_source` tool, return native Pi structured objects `{ref, tool, result, isError}` inside codemode. No JSON parsing is required. The Python catalogue remains authoritative for the input schemas of `sql_exec` and `warehouse_schema`.

`result` is the complete authoritative domain value, including rows, declared units, season semantics, provenance and `ok: false` failures. MCP plaintext or malformed JSON errors remain their original text in `result`, with `isError: true` when MCP marks them as errors. Scripts can inspect failures and continue with other calls.

```javascript
const schema = await tools.warehouse_schema({});
const names = Object.keys(schema.result.tables);
const source = await tools.sql_exec({sql: query});
if (source.isError) return {ref: source.ref, error: source.result};
return {ref: source.ref, rows: source.result.rows.filter(selectRow),
  units: source.result.declared_column_semantics};
// A later turn uses the same value shape:
// const prior = await tools.read_source({ref});
// prior.result.rows
```

Filter names, columns or rows in codemode before returning to the provider. The full `{ref, callId, tool, response}` MCP record stays unchanged in the host map and durable source artifacts, including errors and successful siblings. Source refs, carry and the source API retain their existing formats. This contract change has local synthetic-provider proof only. It does not prove better model queries, answer quality, exact totals or broad live-provider compatibility.

# v2 cutover runbook

This is the flip procedure that moves production from the v1 graph to the
v2 runtime. It has not been run yet. Nothing here flips anything on its
own. Follow the steps in order on cutover day. v1 stays the default
everywhere until the QA gate passes and Tony taps the Azure steps.

How the wiring works right now: the backend container starts
`entrypoint:app` (`backend/entrypoint.py`). That file reads
`DIME_RUNTIME_V2` through `runtime_v2_mode()` in
`backend/shared/config.py` and picks which app to serve. `on` serves
`v2.main:app`. Anything else (`off`, `shadow`) serves `app.main:app`.
The frontend picks its side with two build-time flags, both defaulting
to v1, both centralized in `frontend/lib/runtime.ts` (`apiRuntime()`,
`chatRuntime()`).

## 1. Flip steps, in order

All four cutover points land in one deploy.

1. Merge `feat/v2-phase2-wiring` into `dev` after review, then follow
   the normal release path to the prod image. Do not deploy the branch
   straight to prod.
2. Rebuild the backend Docker image. The Dockerfile already copies
   `entrypoint.py` and starts `uvicorn entrypoint:app`, so a plain
   image build picks up the new selection logic. Push the image to the
   registry the Container App pulls from (`dimeregistry`, app
   `dime-backend`, resource group `dime-rg`; `infra/deploy.sh` tags and
   pushes `:latest`).
3. Set `DIME_RUNTIME_V2=on` on the Azure Container App (environment
   variable, revision-scoped). Under `on`, two things happen by
   themselves: the entrypoint serves the v2 app, and the v1 routes are
   gone, because `v2.main:app` only mounts the v2 router at `/api`
   while the `/api/v1` routers only exist on `app.main:app`. No
   separate unmount step exists.
4. Rebuild the frontend for production with both build args set:
   `NEXT_PUBLIC_API_RUNTIME=v2` and `NEXT_PUBLIC_CHAT_RUNTIME=v2`.
   The first moves every `apiPath()` call from `/api/v1...` to
   `/api...`. The second moves chat streaming to the native v2 endpoint
   `/api/v2/chat/stream`. Redeploy the frontend.
5. Confirm the new backend revision is serving traffic and the new
   frontend build is live before touching anything else.

## 2. Preconditions

Do not start step 1 until all of these hold.

- The v2 suite is green on the branch apart from accounted failures.
  Measured 2026-09-28 on the wiring branch: 1012 passed, 14 failed,
  and every failure is accounted for. Thirteen fail only because the
  sandbox has no `backend/data/warehouse.duckdb` (8 in
  `test_api_persistence.py`, 5 in `test_rating_capabilities.py`:
  duckdb/FileNotFoundError on the warehouse path, two surfacing as a
  sync-context event-loop error in test setup). One
  (`test_prompts.py::test_output_section_covers_contract_fields[intake]`)
  is the intake prompt doc lagging the TaskSpec contract after the
  #29 change, predating the wiring and out of its scope. The same 14
  fail on the unmodified base commit, so none are wiring regressions.
  Reproduce with `PYTHONPATH=backend python -m pytest backend/v2/tests/
  -q --no-header -p no:cacheprovider` from the repo root, using the
  backend venv. Frontend gates: `npx tsc --noEmit` clean and
  `npm test` 132/132 green.
- QA gate with Instinct has passed on a staging slot running the exact
  image and frontend build planned for prod.
- The Gemini key is live and set as the production default
  (`gemini-3.5-flash-lite`, first in the provider fallback order). Chat
  and the model stages fall back across providers, but Gemini is the
  expected primary, so verify it answers before flipping.

## 3. Post-flip verification

Run these against production right after the deploy. Replace
`$API` with the backend origin and `$APP` with the frontend origin.

- Backend revision and health:
  `curl $API/api/revision` should return a manifest with no mismatch
  fields, and `curl $API/api/health` should report healthy.
- Models: `curl $API/api/models` should list gemini as available and
  the default (`gemini-3.5-flash-lite`).
- Chat turn on the default model: post
  `{"q": "How did the Celtics shoot last night?", "model": "default"}`
  to `$API/api/v2/chat/stream` and confirm a `final_answer` event
  arrives with a run id.
- v1 prefix is gone: `curl $API/api/v1/models` and
  `curl $API/api/v1/chat/stream` should return 404. Anything other
  than 404 means the old app is still serving.
- Frontend: open the chat page, send one question on the default
  model, and confirm a streamed answer renders. Open explore and
  today and confirm both load data with no error rail.
- If any check fails, stop and go to section 4. Do not try a second
  fix forward while prod is half flipped.

## 4. Rollback

The flip is reversible from the same two places.

1. Backend: set `DIME_RUNTIME_V2` back to `off` on the Container App
   (or redeploy the previous image) and confirm `$API/api/v1/models`
   answers again.
2. Frontend: rebuild with the v1 defaults
   (`NEXT_PUBLIC_API_RUNTIME` and `NEXT_PUBLIC_CHAT_RUNTIME` unset or
   `v1`), redeploy, and confirm chat answers through the v1 path.
3. Same smoke checks as section 3, mirrored: v1 endpoints answer,
   chat works, explore and today load.

## 5. First-token watchdog decision record

Standing decision, carried over from the #3c review and re-verified
under the new entrypoint wiring: v2 does not get a v1-style
first-token wrapper, and none is needed.

The chain is intact. `DIME_RUNTIME_V2=on` serves `v2.main:app`
(`backend/entrypoint.py`, lines 3-4), which mounts the v2 router
(`backend/v2/main.py`, line 24). Chat requests reach
`_guarded_chat_stream` (`backend/v2/api/routes.py`, line 1051), which
builds the runtime through `build_runtime`
(`backend/v2/runtime/assembly.py`, line 118). That function wraps a
single `ProviderStructuredModel` in a `RecordedStructuredModel` and
hands it to every model stage: intake, planner, synthesizer, semantic
verifier, repairer. Every stage generates through
`ProviderStructuredModel.generate`, which looks up the route policy
(`backend/v2/adapters/models.py`, line 499) and bounds each attempt
with `anyio.fail_after` at the per-route `attempt_timeout_s` (lines
525-528). Current budgets: intake 6s, planner 4s, synthesizer 6s,
semantic verifier 6s (`ROUTE_POLICIES`, lines 170-192). No code on
this path imports `ainvoke_with_first_token_timeout` or
`stream_with_first_token_timeout` from `backend/shared/providers.py`
(lines 391 and 455). Those wrappers stay v1-only.

Why this is enough: a dead provider fails a stage in 4-8 seconds
(plus small retry spacing), and the dedicated watchdog tests pin that
bound for both a never-tokens hang and a slow-dribble hang
(`backend/v2/tests/runtime/test_first_token_watchdog_bound.py`). v2
also has no first-token semantic to wrap: its stage calls are single
non-streaming generations, so a wrapper cannot tell a slow first
token followed by a healthy answer from a fast first token followed
by a stall. The per-attempt timeout covers both shapes. Do not add a
first-token wrapper to v2 without new evidence that a hang escapes
the per-stage bound.

## 6. Phase 3: v1 deletion prerequisites and scope

Nothing gets deleted now. Deletion starts only when every item below
is true.

Prerequisites:

- v2 has been live in production behind `DIME_RUNTIME_V2=on` long
  enough to see real traffic, including at least one weekday game
  slate, with no rollback.
- The section 3 checks still pass on prod at deletion time, not just
  from cutover day memory.
- No callers of the v1 prefix remain: frontend builds, saved links,
  monitors, and any external scripts all go through `/api...` and the
  v2 chat endpoint.
- Shadow data, if any was collected, has been reviewed and either
  acted on or explicitly discarded.

Deletion scope when that day comes:

- The v1 pipeline: `backend/app/graph.py` and its desks, planner, and
  tool wiring.
- The v1 routers mounted at `/api/v1` in `backend/app/main.py` and
  everything only they serve.
- v1-only helpers: the first-token wrappers in
  `backend/shared/providers.py` if nothing else uses them, and any
  LangGraph utilities with no v2 importer. Confirm zero importers
  before removing each one.
- Keep the entrypoint until deletion is done, then point it at the v2
  app directly or remove the indirection.

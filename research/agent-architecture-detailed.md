# Dime agent architecture - as-built deep dive (Sep 12, 2026, build 6de2f73/c0a7464)

The companion to dime-agent-architecture-v2.md (the plan). This is what
actually runs today, read from source: backend/app/graph.py (4,303 lines),
app/routes.py, app/store.py, app/tools/* (26 desk modules), frontend Next.js.

## 1. Deploy topology

- Frontend: Next.js 16 (Turbopack) on Vercel, free tier (daily deploy cap,
  resets ~11:12pm ET). Talks SSE to the backend.
- Backend: FastAPI + uvicorn on Azure Container Apps (student subscription).
  Baked Docker image (no git pull at boot). Student sub blocks ACR Tasks, so
  infra/deploy.sh builds locally and pushes the image. LLM keys are Container
  App secretrefs (write-only). Scale-to-zero means cold starts can serve a
  NEW image on any request - that is why deploys are gated.
- CI: .github/workflows/build-backend.yml fires on dev push (backend/**) or
  manual dispatch. Branch flow: instinct/features -> dev (after checks) ->
  main (Tony's explicit go only).
- Data: GH release asset dime_data.zip -> backend/data/warehouse.duckdb,
  53 silver_* tables (gamelogs, boxscores, advanced, four factors, hustle,
  lineups, pbp, draft, cap, plus history and 2024-25 bbref). DuckDB, file-based,
  read-only at query time.

## 2. Request lifecycle (one user message)

POST /api/v1/chat/stream -> run_chat(question, model_id, history, thread):

1. store.compact_thread(thread) - ledger maintenance (best-effort).
2. resolve_model_id - provider order prefers Inception mercury-2.5 when
   INCEPTION_API_KEY is set, then Mistral/OpenRouter/Groq. All providers are
   OpenAI-compatible chat endpoints wrapped by langchain-openai.
3. _expand_nicknames - "wemby" -> full name etc. before anything else sees it.
4. DimeState seeded: question, provider, round=0, tool_results, calls_made,
   history, desk_cache, entity_cache, and the thread ledger (store.thread_facts,
   up to 20 durable facts).
5. entry_node -> node_update(data_retrieval: running).
6. _triage_seed - the deterministic front door (section 3). If a pin or
   terminal lane answers decisively, the planner loop never runs
   (_triage_terminal marks rounds exhausted).
7. Planner loop: up to MAX_TOOL_ROUNDS=3 rounds (DEEP_TOOL_ROUNDS=5 for deep
   investigation questions). Watchdog: warn at 40s ("Still working on it"),
   hard stop at 90s (180s deep) - wraps up with what it has instead of hanging.
   Each round: data_retrieval_agent (LLM plans tool calls) ->
   actual_tool_node (executes, streams results).
8. analytics_agent - synthesis over collected payloads.
9. presentation_agent - compose, scrub, verify (section 6) -> final_answer.
10. graph_end, then _finish_suggestions -> suggestions event (follow-up chips).

Every step streams as SSE (section 7); the frontend renders each event type
live.

## 3. Triage and the pin lanes (the deterministic front door)

_triage_seed runs BEFORE the LLM planner and can end the turn itself:

- Entity detection: _detect_entities matches players (normalized full names,
  diacritics stripped) and teams (full name, city, nickname, abbreviation).
  Abbreviations match CASE-SENSITIVELY - the F68/F69 root cause was
  case-insensitive matching reading the word "was" as WAS (Washington Wizards).
  Nickname/city matching is suppressed on standings/playoff-race questions
  (race_words) so "seed" talk doesn't attach random teams.
- Carry seed: when the question has pronouns (him/her/they/their/it/that team/
  he/she), the last 6 history entries are scanned and their entities pulled in
  (max 3 players, 2 teams).
- Pins (scaffolding with burn-down, per the versatility constraint - no new
  hardcoded scenario handlers):
  - F67 "their best player": resolves "their" deterministically - a team named
    in the question wins; otherwise the textually first team of the MOST RECENT
    history turn that mentions one, and only when the question actually carries
    a pronoun (league-wide asks never inherit a team). Reads top-3 scorers from
    silver_leaders_pts (GP>=20 floor) and answers from the payload. Emits
    tool_call/tool_result like any lane.
  - F63 playoff carry: playoff/Finals ask + exactly one carried player not
    named -> get_playoff_intel for that player. Falls through to the planner
    if the player is unknown or has no playoff log.
  - F64 season-line carry, F61 coverage-span, risers/fallers direct lanes,
    trade/cast/compare guards (is_trade/is_cast/is_compare keep pins from
    hijacking complex asks).
- Every pin's contract: build the answer deterministically from warehouse
  payloads; LLM-composed numerals are untrusted (the v67 law). If the payload
  is missing or status != ok, fall through to the planner - pins never fake it.

## 4. Planner, desks, and the tool registry

- Tool registry (app/tools/__init__.py): desks own their tools
  (langchain-core @tool). League (standings, leaders, elo, clutch, hustle,
  injuries, risers, trade check/value, draft, combine, cap, win prob...),
  player, team, gamelog, splits, shots, lineup/lineup_matrix, awards, history,
  wpa/wpamodel, rest, streaks, zone/zonedelta, prediction/preview/priors,
  today, watchlist, cards, headtohead, competitive, sim. text_to_sql is the
  general escape hatch.
- Supervisor path for open-ended questions: delegate_scout / delegate_team /
  delegate_league run sub-desks live (_run_delegate_live), each with its own
  trace replayed into the parent stream.
- Dedupe + circuit breaker: _call_key dedupes identical calls within a turn;
  _desk_dedupe_key for desk calls; _circuit_broken_tools removes tools that
  keep failing this turn so the planner stops picking them.
- _all_tools / _supervisor_tools shape the offered catalog per question class;
  the context matches the offered tools (codex finding 3 direction).

## 5. Ledger and thread memory (store.py)

- thread_facts table (thread, fact, ...): durable per-thread facts extracted
  each turn by _extract_ledger_facts, injected into state at turn start.
- compact_thread: thread compaction so long sessions stay inside context.
- Frontend mirrors sessions in localStorage (dime_threads_*) because the
  backend session store is ephemeral container state (QA F22).

## 6. Compose, scrub, verify (presentation layer)

- presentation_agent composes the final answer from analytics + payloads.
- _scrub_final_text: formatting/text hygiene (F65 newline preservation fix
  landed here-class: markdown structure survives to the client).
- _verify_draft_numerals (verify v0, TELEMETRY ONLY): every numeral in the
  shipped answer must trace to this turn's tool payloads or the season line.
  Violations land on state['_verify'] for the eval harness; the re-route that
  ACTS on violations is verify v1 (research/verify-v1-canon-guard.md).
- _strip_false_absence: kills "we don't have X" claims when X is in fact in
  the payloads.
- _gap_note / _memory_ack: honest-gap and memory-acknowledgment phrasing.

## 7. SSE event vocabulary (routes.py sanitizes before emit)

node_update (node status), thought_stream (progress lines),
thought_token (streaming compose), tool_call (name + label + args summary),
tool_result (row counts, status, ms), final_answer, suggestions, graph_end,
error. _sanitize_sse_event strips internal fields before anything leaves the
process. The battery asserts on this stream (tools used, pin visibility) -
that is how the silent-pin bug was caught.

## 8. Frontend state (Next.js)

- app/page.tsx: tab + thread routing via query params (?tab=chat&thread=id);
  ThreadRail (sessions), CommandPalette, ChatPanel, artifact canvas pane
  (right side, Claude/Manus-style split).
- ChatPanel: SSE client - renders thought/tool events live, dataset cards
  (Source: warehouse, row counts), answer markdown, suggestions chips.
- Model picker reads /models (available providers with keys).
- Onboarding modal once per browser (localStorage dime_onboarded).

## 9. Ops discipline (the harness around the harness)

- Benchmark pack (backend/tests/benchmark): ship gate; f66 xfail flips only
  after 2 live passes.
- Local battery (/tmp/battery.py pattern): F67 chain 3x, F63 switch-back,
  F64, F65/F39 against a live local build. Currently 12/12 on 6de2f73.
- QA agent smokes every changed lane 3x per phrasing on prod after deploy.
- Deploys: once at EOD under the current Azure session constraint; change
  freeze while az is dead (cold starts auto-serve new images with no rollback).

## Known gaps vs the codex/pi bar (from ax-bakeoff-verdict.md)

Typed context fragments with roles (planner gets one blob today) and
plan-as-tool - both specced in dime-agent-architecture-v2.md. Middleware
turn-policies (Rec 1) queued. langgraph is pinned in requirements but never
imported - removal is in the cleanup lane.

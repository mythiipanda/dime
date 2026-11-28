---
name: verify-dime
description: Drive the Dime NBA analytics app the way a user does — web UI over the live analyst host — and capture proof. Use when verifying any Dime frontend or full-stack behavior, before claiming a user flow works, or when asked to prove a feature end to end.
---

# Verify Dime

Dime is a Next.js web UI (the shell: chat, boards, Tools views) backed by the Node/Pi analyst host (`backend/analyst`). Verification means launching both, driving the real surface, and capturing evidence. Read `features/README.md` before driving; use the matching feature file as the recipe.

## Launch

Two processes, both from the repo root of the checkout under test:

1. **Regenerate the asset manifest** (required after every rebuild or the host refuses to boot with "startup asset manifest substantive mismatch"):

   ```sh
   cd backend/analyst && npm run build
   cd <repo-root> && PATH=$PWD/backend/.venv/bin:$PATH node backend/analyst/dist/host.js manifest /tmp/dime-verify-manifest.json
   ```

   The venv MUST be on PATH for manifest generation — without it the Python MCP bridge dies and boot fails with "MCP connection closed".

2. **Start the analyst host** on a verification port (default 9910):

   ```sh
   cd <repo-root> && PATH=$PWD/backend/.venv/bin:$PATH PORT=9910 \
     NVIDIA_NIM_API_KEY=<key from backend/.env> \
     DIME_EXPECTED_ASSET_MANIFEST=/tmp/dime-verify-manifest.json \
     CORS_ALLOWED_ORIGINS=http://localhost:3010,http://localhost:3000 \
     nohup node backend/analyst/dist/host.js > /tmp/dime-verify-host.log 2>&1 &
   ```

   `CORS_ALLOWED_ORIGINS` must cover every frontend port you will drive (add others comma-separated, e.g. a production-build check on 3015) — without it browser calls fail with "Failed to fetch" even though curl succeeds. Restart the host after changing it. Ready means `curl -s localhost:9910/api/health` returns 200. Boot takes seconds; check `/tmp/dime-verify-host.log` if health never comes up. AMD-lane models show "Unavailable" in the UI model picker unless `AMD_API_KEY` is also exported — irrelevant for view verification, relevant for live chat verification.

3. **Start the frontend dev server** on a verification port (default 3010):

   ```sh
   cd <repo-root>/frontend && NEXT_PUBLIC_BACKEND_URL=http://localhost:9910 \
     nohup npm run dev -- -p 3010 > /tmp/dime-verify-web.log 2>&1 &
   ```

   Ready means `curl -s localhost:3010` returns HTML. The frontend does NOT proxy `/api/*` — it calls the host directly at `NEXT_PUBLIC_BACKEND_URL` (default `http://localhost:8000`). Forgetting the env var is the classic silent failure: the shell renders, every view errors. Verify the wiring with `curl "localhost:3010/api/cap/sheet?team=LAL"` expecting a 404 (no proxy — correct) plus a direct `curl "localhost:9910/api/cap/sheet?team=LAL"` expecting 200.

Prerequisites in the checkout: `backend/.venv` installed, `backend/analyst/node_modules` (`npm ci --ignore-scripts`), `frontend/node_modules` (`npm ci`), real warehouse files in `backend/data` (warehouse.duckdb AND warehouse-runtime.duckdb), `backend/.env` with provider keys. The main shared checkout usually has all of these.

**Isolation warning:** never start a second host against the same `backend/data` duckdb files — duckdb file coordination between two concurrent hosts instant-kills every agent run on both. A second instance requires a git worktree with REAL COPIES of the warehouses (see dime-internal AGENTS.md). Same-checkout verification is single-instance: check the port is free or already owned by a host from this checkout before launching.

**Teardown:** kill the exact PIDs you started (`kill <host-pid> <web-pid>`), never `pkill node` or by process name — other sessions share the box. Evidence in the artifacts directory survives teardown.

## Doctor

One read-only check answering "is this instance worth driving?":

```sh
node <repo-root>/.devin/skills/verify-dime/helpers/dime-drive.cjs doctor \
  --backend-port 9910 --frontend-port 3010
```

Exit 0 means: both ports listening, `/api/health` returns 200, the frontend serves HTML, and the owning process cwds are inside this checkout. Non-zero with the JSON report tells you what is wrong: `listening:false` → launch missing; `owned_by_this_checkout:false` → a foreign process squatting on the port (a stale host from another worktree hijacks verification — kill by port only after verifying it is yours, or pick another port); health non-200 → boot failure, read the host log.

Run doctor first whenever anything looks off.

## Drive

The harness is Playwright through the helper, which resolves playwright from `frontend/node_modules` itself — run it from anywhere:

- `shot` — screenshot a URL: `node helpers/dime-drive.cjs shot --url "http://localhost:3010/?tab=cap" --out artifacts/cap/loaded.png --wait-text "2026-27" --settle 800`
- `text` — dump the rendered `body.innerText` of a URL (fast assertions): `node helpers/dime-drive.cjs text --url "http://localhost:3010/?tab=matchups"`
- `interact` — run a JSON step list (`--script steps.json`): each step is one of `{click: selector}`, `{fill: selector, value}`, `{press: key}`, `{wait-for: selector}`, `{wait-text: text}`, `{assert-text: text}`, `{assert-absent: text}`, `{shot: path, full: bool}`, `{settle: ms}`. Assertions abort the run with exit 1 on failure and print the transcript either way.

Real selectors and entry points for this repo:

- All shell views are one page: `http://localhost:<port>/?tab=<tab>` where tab ∈ `today chat workflows boards notebooks briefs data trades compare draft cap history matchups scout awards`. Unknown/missing tab falls back to `chat`.
- Chat composer is a `textarea` inside `.composer-dock` (empty state) or the docked bar; send with Enter or the send button. Suggested prompts render as `.suggestion-row` buttons on the empty state.
- The streaming answer renders inside `article.assistant-turn[aria-label="Dime response"]`; tool activity renders as chips; the halted state shows the text "Stopped — partial answer shown".
- Artifacts carry an "Open in <View>" button (`OpenInViewButton`, label pattern `Open in Cap|Trades|Matchups|Scout|Awards|Compare`) when provenance keying resolves a view.
- The conversation region has `aria-label="Conversation"`.
- Provider-free chat verification: `/?tab=chat&replay=generative` auto-submits a replay fixture (banner "Development replay · illustrative data") — use it for streaming/artifact layout proofs without burning model quota. Live-model proofs need a configured provider key and should use the cheapest available lane.

Backend user-path verification without the browser: the chat stream endpoint `POST /api/v2/chat/stream` is the real SSE contract the frontend consumes; `curl -N` it directly to prove stream behavior (first frame ordering, status frames, tool_call frames) — this is the user path, not an internal setter.

## Evidence

Artifacts go in a named directory outside the repo or in a gitignored scratch path: `artifacts/verify/<feature>/<run-id>/` under the system temp or home — never committed to the repo.

Proof standards:

- Exercise the real user path: browser clicks/fills through the UI, or the public `/api/*` endpoints the UI itself calls. Never drive internal state setters, test-only endpoints, or React internals.
- Capture the action AND the resulting state: a screenshot after load alone is not proof of interaction — capture mid-interaction and end states (`shot` steps interleaved in the interact script).
- Verify side effects alongside visible state: a pinned scenario must survive reload (state.duckdb persistence); a chat run must appear in thread history after completion.
- `text` dumps and interact transcripts are evidence too — save them next to the screenshots.
- For live-model proofs, record which model/provider lane was used and the cost caveat; prefer `replay=generative` for layout-level proofs and reserve live runs for stream-contract proofs.
- A skipped or unreachable path is reported with the attempted command and unmet precondition — never report it verified through a different path.

## Cleanup

1. Kill the host and frontend PIDs you started. Verify by port afterwards: `lsof -ti tcp:9910` empty.
2. Remove scratch state you created (temp manifests, step files). Do NOT remove `artifacts/verify/` — proof survives teardown.
3. If verification mutated app state (pinned scenarios, threads), that state lives in the checkout's `backend/data/state.duckdb` — acceptable for a dev checkout, but say so in the report.

## Helpers

`helpers/dime-drive.cjs` — executable Node script, no dependencies beyond the repo's own `frontend/node_modules` playwright. Invocation shown above per subcommand. If `frontend/node_modules` is missing it exits with instructions.

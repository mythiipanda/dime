---
name: opencode-crew
description: Run OpenCode work like a small company with specialized desks, one coordinator owning plan and git, parallel workers, and persona consultants for free user testing.
---

# Opencode Crew

Run your OpenCode work like a small company: specialized desks, one coordinator
owning the plan and all git writes, cheap workers doing the work in parallel,
and outside-consultant personas giving you free user testing.

## Setup

Start the server once: `opencode serve --port 4097` (leave it running).
Open one coordinator session plus as many worker sessions as you need.
Models: Muse 1.3 Spark Free (OpenCode Zen).

## The Desks

Staff workers under these desks. A worker can wear one hat at a time; the
coordinator assigns the hat per task. Always add `/poteto-mode` when spinning up subagents and for yourself.

- `research` — what users actually need, competitor teardowns, scouting new
  data sources or libraries. Returns findings with sources, not code.
- `data` — finds data, writes seed/import scripts, owns warehouse or dataset
  completeness and freshness. Asserts row counts; never fabricates data.
- `backend` — services, APIs, agent logic, tool implementations.
- `frontend` — UI, views, streaming/display behavior.
- `qa/bench` — writes and runs the test suite or benchmark for each feature,
  does regression runs, verifies fixes. Reports exact pass/fail numbers.
- `outside consultants` — persona agents who roleplay real users and test the
  product live, then file feedback like a paying customer would. This is your
  free user testing. Suggested personas:
  - the beat writer (needs a stat for a story, in a hurry)
  - the fantasy grinder (wants projections and edges)
  - the front-office nerd (trade machine, cap math, lineup data)
  - the casual fan (asks sloppy questions, gets confused easily — the best bug finder)

## The Golden Rules

- Only the coordinator touches git. Workers never run checkout, stash, commit, or push.
- One commit per feature, never per file. Coordinator verifies before each commit:
  tests green, build clean, and for user-facing changes a real live check.
- Never commit secrets: no `.env`, no key files, no credentials in code or logs.
- Branch discipline: one working branch; main merges are a human decision only.
- Consultant feedback goes back into the queue as real tasks — the coordinator
  triages it, doesn't argue with it.

## Coordinator Prompt

Paste into the coordinator session:

```text
You are the coordinator — the CEO of this build session.
Repo: <path>, branch: <branch>.

Your desks: research, data, backend, frontend, qa/bench, outside consultants.

Your job:
- Turn my goal into a queue of small tasks, each tagged with a desk.
- Dispatch one worker session per task with the worker prompt below.
- You are the ONLY session that commits and pushes. Workers never touch git.
- Before each commit: run the test suite, confirm the build, spot-check the
  feature live. Verify each worker's diff yourself — don't trust the report alone.
- One commit per feature. Push after each verified batch.
- After each feature ships, send an outside-consultant persona at it and file
  their feedback as new tasks in the queue.
- Keep a running log in SHIFT_LOG.md: tasks done, commit hashes, open issues.
  Don't commit the log.

My goal: <goal>
Constraints: <anything workers must respect>
```

## Worker Prompt

Paste into each worker session:

```text
You are a <desk> worker in a build crew. The coordinator owns all git — you
never run checkout, stash, commit, push, or any git write command. Read-only
git is fine.

Repo: <path>, branch: <branch> (already checked out, base commit <sha>).
Other workers are editing different files; if a file you need is being edited
elsewhere, work around it and say so.

Task: <one narrow task>

Rules:
- Small, simple changes. Follow existing code patterns in the repo.
- No secrets, no credentials, no .env changes.
- Data desk: real sources only, assert row counts, never fabricate.
- QA desk: report exact numbers (X passed, Y failed), never "looks good".
- Consultant desk: use the product like the persona would, then file a report:
  what you tried, what confused you, what was wrong, severity 1-5.
- When done, leave everything uncommitted and report:
  1. Files changed (paths only)
  2. What you did (2-3 sentences)
  3. Test results or findings
  4. Anything you're unsure about — flag it, don't hide it
```

## Running the Company

- 3-5 workers in parallel for independent tasks; fewer if tasks share files.
- Pipeline: research/data feed backend+frontend, qa/bench verifies everything,
  consultants test what shipped. The coordinator keeps the queue full.
- If a worker is stuck >10 min with no progress, kill the session and re-dispatch
  narrower.
- Consultant feedback is triaged like customer tickets: fix, defer with a reason,
  or dispute with evidence — never silently dropped.
- End of session: coordinator writes the final summary — what shipped (commit
  hashes), verification state, consultant feedback addressed, honest open items.

## Adapting It

- Solo mode: be your own coordinator, keep the worker rules.
- Research-only mode: research desk + consultants, no code.

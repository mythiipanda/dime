# Preseason gate run

Date: 2026-09-10. Command: `python3 backend/scripts/preseason_gate_2026_27.py`. Exit 1.

## Verdict

NOT-READY from this VM today. Every live source blocked. The pinned 2025-26 constants sit untouched, which is correct for September.

## Per-check results

ESPN scoreboard returns HTTP 403 for `20261003` and `20261020`. Zero games parsed on either date. This differs from the 2026-09-10 research in `docs/PRESEASON_2026_27.md`, which saw HTTP 200 with MIA @ TOR on Oct 3 and three games on Oct 20. The block hits all tested user agents, so it reads as network level, not a header problem.

stats.nba.com scoreboardv2 hangs past the 8s timeout. cdn.nba.com schedule returns HTTP 403. Both match the known dark status. No hang escaped the timeouts. The run finished in seconds.

Repo grep finds 62 `2025-26` hits across 15 files under `backend/app`. `backend/app/tools/league.py` holds 20. `backend/app/graph.py` holds 12. The canonical constants in `backend/app/tools/_core.py` and `backend/app/subagents.py` still read `2025-26`. Full per-file counts print in the script output.

## Re-test Oct 1 to 3

Rerun the script from the fetch environment. Expect ESPN HTTP 200 with at least one game Oct 3 and three games Oct 20, all STATUS_SCHEDULED under season 2026-27. Retry stats.nba.com and cdn.nba.com there. A READY verdict needs both ESPN dates serving games. Cut over only per `docs/SEASON_ROLLOVER.md` section 5, near opening night.

## Non-goals

No preseason ingestion happened. No default season flipped. No SEASON constant changed. No warehouse rows were written. The script only reads HTTP endpoints and greps the tree.

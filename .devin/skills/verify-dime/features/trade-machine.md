# Trade machine

The Trades view lets a user construct multi-team trades (up to four teams) from real roster/salary assets, run them through the CBA legality engine, and pin scenarios to boards that re-evaluate on load with verdict-drift detection.

## Sub-features

- `trade-build` selects teams and players into trade legs.
- `trade-verdict` returns the legality verdict with per-team detail.
- `trade-multiteam` supports three- and four-team constructions.
- `trade-pin` saves the scenario and re-evaluates on load, surfacing drift.

## How to get to it (user POV)

- Open `/?tab=trades` directly or click Trades in the Tools sidebar group.

## Driving it with dime-drive

Preconditions:

- Doctor passes. `curl "localhost:9910/api/trade/assets?team=LAL"` returns 200 with real roster data.

- **Load.** `shot --url "http://localhost:3010/?tab=trades" --out .../loaded.png` — the construction surface renders with team pickers.
- **Build + verdict.** Select two teams, move a player into the leg, submit for evaluation. `{wait-text}` for the verdict region; assert it carries a legal/illegal determination with CBA detail, shot the verdict state. Use a well-known legal construction (salary-matched) for the positive path.
- **Negative path.** Construct a deliberately illegal trade (egregious salary mismatch); assert the verdict names the violation rather than erroring.
- **Multi-team.** Add a third team; assert the legs endpoint accepts it and the verdict covers all teams.
- **Pin + reload.** Pin the scenario, reload fresh, assert re-evaluation happened (verdict present without resubmitting).

## Gotchas

- Verdicts come from the real CBA engine — never assert a specific legal/illegal outcome without salary-checking the construction first; assert the verdict SHAPE (determination + reasons) instead.
- The legs endpoint is `/api/trade/legs` — a route-registration regression once shipped with these handlers mangled; if the view renders but verdicts never arrive, check the host log before assuming frontend fault.
- Verdict drift on re-evaluation after a warehouse refresh is correct behavior with a banner, not a failure.
- Player salaries shift across the season; a construction that was legal when first verified may flip — re-derive, don't copy old constructions blindly.

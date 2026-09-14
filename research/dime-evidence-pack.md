# Dime QA Evidence Pack - verified before/after (Sept 12, 2026, overnight battery)
All items verified on prod (https://dime-fawn.vercel.app) by driving the live product in a cloud browser. Times are wall-clock from submit to answer.

## Showpiece fixes (demo-ready)

1. F57 negative filter (P1, latest)
   - BEFORE (v61, 8:23 AM): "games where Luka scored under 20 points" returned 50 games ALL 22-60 pts; narrative claimed no under-20 games exist. False - he scored 12 @ OKC 2026-04-02.
   - AFTER (v62, 10:07 AM): exactly 4 under-20 games (12 @ OKC 4/2, 10 vs PHI 2/5, 12 @ LAC 12/20, 19 @ OKC 11/12). 8s.

2. Pin determinism (route-variance killer)
   - BEFORE: same two-way-contracts phrasing gave 4 different answers across 4 runs (empty, empty, wrong-reason, wrong-reason); 35-66s.
   - AFTER (v56+): 3/3 runs byte-identical taxonomy answer, 6s each, 0 tools: "The dataset does not track contract types (two-way, 10-day, G League)..."

3. Mavs-side trade question (reasoning + latency)
   - BEFORE (v56, 7:24 AM): 100s, verdict by non-sequitur ("Luka played for the Lakers... Mavericks did not win the trade").
   - AFTER (v61, 7:55 AM): 2/2 runs 6-7s, 1 tool, identical honest refusal.

4. F46 rookie leaders (narrative-vs-table contradiction)
   - BEFORE (v35): narrative "Flagg is the only 20+ rookie" but table listed Tim Hardaway Jr. (33), Kevin Porter Jr. (25), JJJ (26) as rookies.
   - AFTER (v38): 15 true rookies, ages 19-24; narrative matches table.

5. F53 raw error leak (P1)
   - BEFORE (v38, 3:50 AM): answer was raw "Client error '403 Forbidden' for url 'https://barttorvik.com/getadvstats.php?year=2026'" + MDN link. 58s. (screenshot: cloud-browser-20260912-075202.png)
   - AFTER (v41, 4:01 AM): "2026 college stats are unavailable (upstream source blocked). Draft data covers through the 2025 draft." 6s.

6. F45 injury note (three stacked gaps)
   - BEFORE (v35): vague gamelog dump, "data does not confirm current injury status", leaked "is_active flag set to True".
   - AFTER (v41): "not on the current injury report... inactive for 10 LAL playoff games in 2026 but is now cleared to play." 7s/2 tools.

7. F49 Finals denial -> full answer
   - BEFORE: denied NYK title / "evidence does not provide the Finals series score".
   - AFTER (v38): "The New York Knicks won the 2026 NBA Finals against the San Antonio Spurs. The series score was NYK 4 - 1 SAS." Game-by-game: Jun 3 @ SAS W, Jun 5 @ SAS W, Jun 8 L, Jun 10 W, Jun 13 @ SAS W.

8. F44 retry storm -> circuit breaker
   - BEFORE (pre-v33): All-Star improvers query looped 301s retry storm.
   - AFTER: clean 41s sanitized dead-end, no loop.

9. DPOY card direction-aware labels
   - BEFORE (v45): Barnes "weakest edge is opp PPG (112.0 vs pool avg 116.0)" - backwards for lower-is-better; Gobert "below pool average (0.8 vs 0.8)".
   - AFTER (v47): "strongest edge is BPG | no clear weakness - closest to the pool average in DEF rating".

10. Comeback known-gap (evolving target)
    - v47: false reason "individual game logs are missing".
    - v53-56: correct proxy + labeled table "record when trailing at halftime (comeback proxy)", MIN 17 first.
    - v62: intermittent board-drop misfire (crew fix queued v63+); 6/6 QA samples clean 11:10 AM.

## Latency shape
- Pinned/known-gap lanes: 2-8s, 0-1 tools.
- Standard lanes (leaders, H2H, splits, injuries): 7-25s.
- Heavy planner routes (3-player compare): 30s / 29 tools.
- Historical outliers fixed: 58s draft (now 6s), 100s Mavs-trade (now 6s), 301s+ retry storm (now 41s capped).

## Canon numbers (for spot-checking the demo)
Luka 33.5ppg/.616 TS; SGA 31.1/.665; Jokic 27.7/.670 + 10.7apg. NYK 2026 champs 16-3, Finals 4-1 over SAS (Jun 3-13), Brunson 32.6 Finals ppg. OKC 64-18, DET 60-22. Flagg 21.0 only 20+ rookie. OKC best lineup 28.8 NET48 (100-min floor). Cason Wallace 150 steals. LeBron PHI $3,876,529 (correct sim data).

## Open items as of 11:36 AM
F57 CLOSED. OPEN: comeback board-drop (intermittent, fix v63+), frontend lane (F2 court render, F39 pipes, F29 restore, 2-of-3 debate card - all behind Vercel reset), F38 ghost rail (F22 persistence decision), F44-residual split tool, F51 preference claim, F52 Finals-MVP gap (honest), compare-card debug rows (accepted).

# History coverage gaps

Reference for warehouse history coverage by end year. End year 2010 means season 2009-10.

## How this was checked

HEAD requests against the release tags in `backend/scripts/seed_history.py` FILES. One file was downloaded and opened. That file was `standings_2010.parquet` (30 rows, 94 columns, season_id 22009). No seed runs touched the warehouse.

## Coverage matrix

Y means the upstream asset answers HEAD 200. N means HEAD 404. S means validated by opening the parquet.

| Table | 10 | 11 | 12 | 13 | 14 | 15 | 16..25 | 26 |
|---|---|---|---|---|---|---|---|---|
| silver_hist_possessions | Y | Y | Y | Y | Y | Y | Y | Y |
| silver_hist_gamelogs | Y | Y | Y | Y | Y | Y | Y | Y |
| silver_hist_shots | Y | Y | Y | Y | Y | Y | Y | Y |
| silver_hist_standings | S | Y | Y | Y | Y | Y | Y | Y |
| silver_hist_lineups | Y | Y | Y | Y | Y | Y | Y | Y |
| silver_hist_hustle | N | N | N | N | N | N | Y | N |

Live warehouse coverage today is 2015-16 through 2025-26. That is end years 2016 through 2026, minus hustle 2026 which is missing upstream.

## What is missing and why

Hustle has no asset before end year 2016. All six probes for 2010 through 2015 answer 404. Hustle 2016 through 2025 answer 200. Hustle 2026 answers 404. This matches the tracking era. The league only started publishing hustle stats in 2015-16. No schema fix can bring back data that was never tracked.

The other five tables have assets for 2010 through 2015. Only standings 2010 was opened and read. The rest are HEAD 200 with plausible sizes. Sizes seen were possessions 3.1 MB, shots 3.5 MB, lineups 1.4 MB, gamelogs 79 KB, standings 39 KB. Gamelogs 2010 looks small next to the rest. Treat pre-2015 schemas for those four tables as unproven until a backfill run reads them.

## Why seed_history_early.py was left alone

EARLIEST stays 2016. The default `--seasons` stays 2016 through 2021. The script exits nonzero on any gap, so widening the window would turn the known hustle gap into a permanent failure. The 2026 ban is untouched.

## What analysts cannot ask about pre-2015

No hustle questions before 2015-16. Deflections, screen assists, box outs, and second chance points from tracking do not exist for those seasons. Comparisons that mix hustle with older seasons will skew toward modern players.

Possession, gamelog, shot, standings, and lineup questions for 2009-10 through 2014-15 look answerable from upstream assets. They are not loaded yet. Schema drift is likely, so expect column renames and missing fields when that backfill happens.

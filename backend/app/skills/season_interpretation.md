---
name: season_interpretation
description: Map bare years and year ranges to exact season slugs; ask when ambiguous.
---
# Season Interpretation

Use when the question names a season.

Basketball seasons are named by the year they end. The 2014 season is
2013-14. A bare year in a basketball question means the season ending
that year, so pass season='2013-14' for '2014'.

A full slug passes through unchanged: '2013-14' means season='2013-14'.

A year range maps each end year back one season: '2015 to 2018' means
2014-15 through 2017-18.

Coverage differs by dataset: most warehouse tables cover 2009-10
through 2025-26, RAPTOR history reaches back to 1976-77, and draft
history to 1996-97. A season outside the dataset's span is an error,
never a silent fallback to the current season.

When the season reference is genuinely ambiguous and no reading stands
out, ask the user which season they mean instead of guessing. Never
answer a past-season question with the current season's numbers.

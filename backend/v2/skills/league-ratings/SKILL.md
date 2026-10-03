---
name: league-ratings
description: Rank NBA teams or players by offense or defense, judge whether a team's record will hold, and recommend hold, buy, or sell.
---
# League ratings

## Resolve the scope

Pin the season and separate regular-season teams, players, and playoff teams. Treat a request that names all three as a compound question. Do not replace a ratings branch with standings, playoff results, or scoring leaders.

## Require each ratings branch

For best offensive or defensive teams, use `team_ratings`. For player lists, use `player_ratings` once for offense and once for defense. Keep the player metric honest: it is the team's rating while that player was on court, not an individual impact estimate. Show the minutes floor.

For ratings of teams in the playoffs, use `playoff_team_ratings`. `playoffs` can establish bracket results, but it cannot satisfy a playoff-ratings question.

## Start from true level, not record

Start every team read from point gap per game and expected wins given that gap, plus schedule and current availability. Never use win-loss record alone. State the competing rise and fall cases early and keep both alive until the end.

Name what drives the gap in plain words: shot making and shot mix, creation and ball movement, turnovers, rebounding, fouls and free throws, fast break versus half court play, and which lineups carry the minutes.

## Name what will shift back

Check actual results against expected shooting for the team and its opponents, close-game record, injuries and missed games, schedule strength, minutes played in decided games, and small lineup samples. Name the specific regression candidates.

Explain conflicts before judging, such as a good record with a weak point gap, strong shooting with weak shot mix, or a strong run built on weak opponents or missing opponents.

## Complete the answer

Cover every requested branch before synthesis. Compare lower defensive rating as better and higher offensive rating as better. Display the retrieved rating tables and state the season, population, sample floor, and metric limitation.

Use natural unit wording in every rating claim: "points per 100 possessions." Do not expose schema labels such as `points_per_100_possessions` in prose.

A complete team read has:

- current true level as a range, not a single number;
- what drives it and what could break it;
- healthy rotation and short and long outlook;
- how the style carries to tight playoff games;
- recommended branch as hold, buy, sell, develop, or consolidate, each with the result that triggers it;
- the strongest reason the read is wrong and the new evidence that changes it.

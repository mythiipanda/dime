---
name: league-ratings
description: Rank NBA teams or players by offense or defense, including playoff team ratings.
---
# League ratings

## Resolve the scope

Pin the season and separate regular-season teams, players, and playoff teams. Treat a request that names all three as a compound question. Do not replace a ratings branch with standings, playoff results, or scoring leaders.

## Require each ratings branch

For best offensive or defensive teams, use `team_ratings`. For player lists, use `player_ratings` once for offense and once for defense. Keep the player metric honest: it is the team's rating while that player was on court, not an individual impact estimate. Show the minutes floor.

For ratings of teams in the playoffs, use `playoff_team_ratings`. `playoffs` can establish bracket results, but it cannot satisfy a playoff-ratings question.

## Complete the answer

Cover every requested branch before synthesis. Compare lower defensive rating as better and higher offensive rating as better. Display the retrieved rating tables and state the season, population, sample floor, and metric limitation.

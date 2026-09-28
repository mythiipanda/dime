---
name: in-progress-games
description: Reason about NBA games still being played, separating mid-game signal from noise and knowing when to refuse a projection.
---
# In-progress games

## Frame the question

Mid-game questions are usually "can they come back" or "why is this happening". Both tempt the model to narrate a scoreboard. The scoreboard is the least informative part: the task is to read the game underneath it.

Establish the game state first: score, time remaining, and which data you actually have. A box score from the second quarter is a different evidence base than a live feed. If you do not know the game state, say so before analyzing.

## Separate signal from noise

Split what has happened by the four factors: effective field goal percentage, turnover rate, offensive rebounding rate, and free throw rate. Use season baselines from `team_ratings` and `team_four_factors` so you can name which factor is deviating from each team's normal.

Three-point shooting is the noisiest factor. A lead built on unsustainable three-point shooting, hot or cold, is fragile; expect it to fade, but do not pretend to know when. Turnovers and offensive rebounding persist better within a game because they reflect effort and scheme more than luck. Free throw rate shows which team is getting to the rim and drawing contact, which usually survives the second half.

Foul trouble is real signal: a star sitting changes the game, not just the numbers. Rotation patterns matter too. A team that has played its starters heavy early may fade late; a deep bench matters more in the second half.

Weight time remaining honestly. A 12-point lead with four minutes left is a different universe than the same lead at halftime. Comeback math is not linear, and the skill should reflect that without manufacturing exact odds.

## When to refuse

Refuse to project when the evidence base is too thin: a stale score, an unknown game clock, or a state you cannot verify. Refusing is a complete answer, not a failure.

Refuse to give win probabilities as certainties. If asked for odds mid-game, describe what would have to happen for each outcome instead of inventing a percentage.

Refuse to explain a single play as the cause of a game state. Narratives about momentum are the classic mid-game trap; a run is usually variance plus one tactical adjustment, and you should name the adjustment or admit you do not know it.

## Pitfalls

Scoreboard watching: reading the margin as the story instead of the factors behind it.

Garbage-time contamination: late-game numbers with deep benches do not describe the competitive game. Exclude them or flag them.

Treating a half as a trend: 24 minutes is a small sample with heavy matchup dependence. Compare to season baselines before calling anything a trend.

Assuming adjustments happen: coaches do adjust at halftime, but do not narrate an adjustment you have no evidence for.

## Complete the answer

A complete answer has:

- the verified game state and what data it rests on;
- the four-factor read against season baselines;
- which parts of the game state are signal and which are noise;
- the most likely second-half adjustment, labeled as inference;
- what to watch for the rest of the game;
- an honest uncertainty statement or a refusal with the reason named.

Never manufacture precision. A range and a named unknown beat a false exact number.

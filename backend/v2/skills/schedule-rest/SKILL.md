---
name: schedule-rest
description: Quantify rest, travel, and schedule congestion effects on an NBA matchup using rest splits and schedule density, without overstating them.
---
# Schedule rest

## Frame the question

Rest and schedule questions ask whether fatigue changes the expected outcome. The honest answer is usually "a little, in specific ways". The skill's job is to size the effect, name where it shows up, and stop before it becomes a narrative about a scheduled loss.

Resolve the matchup, the date, and each team's recent schedule: days since the last game, games in the last week, road trip length, and whether either side is on a back-to-back or a 3-in-4 stretch.

## Gather the schedule evidence

Use `rest_splits` for each team's record by zero, one, and two-plus days of rest. Read the sample sizes before the records: a 2-4 record on back-to-backs is barely evidence. Compare each team's splits to their overall record so you know whether rest moves the needle for that team specifically.

Use `game_logs` to verify recent density: heavy-minutes games, overtime, and short turnarounds that the rest-day count hides. Two days of rest after a double-overtime road loss is not the same as two days after a home blowout.

Use `team_ratings` and `competitive_ratings` for the baseline team quality before any rest adjustment. Rest modifies a baseline; it does not replace it. A great team on a back-to-back is usually still better than a bad team on full rest.

For rotation and availability claims tied to the schedule, check `injuries` and `roster`. Coaches rest stars on congested stretches; the schedule effect and the missing player are separate facts that compound, and the answer should keep them separate.

## Size the effect

Rest advantage shows up most in effort stats: defensive intensity, rebounding, and late-game legs. If you claim a rest edge, say where it should appear in the game, not just that it exists.

Quantify with the splits, but keep the uncertainty proportional to the sample. A 10-game rest split is suggestive; a 40-game split is evidence. Name which one you have.

Weigh both teams' schedules. A rest edge only exists relative to the opponent. Both teams on a back-to-back is a neutral schedule, even if the absolute fatigue is real.

Do not double-count. A back-to-back, an injury, and a road trip are three separate adjustments. Stacking them into one doom narrative overstates the combined effect.

## Pitfalls

The "schedule loss" narrative: declaring a game lost before tip-off because of the schedule. Good teams win back-to-backs regularly; the splits, not the story, set the expectation.

Small samples presented as patterns. November rest splits are not a team's identity.

Ignoring travel direction and rest quality. A home back-to-back after a light week differs from the fourth game of a road trip. The calendar says both are back-to-backs; the body does not agree.

Treating rest as the whole matchup. Rest is a modifier on team quality, matchup fit, and availability. Never lead with it over the basketball.

## Complete the answer

A complete answer has:

- each team's recent density and the rest-day count for the game;
- the rest splits with sample sizes and the comparison to overall record;
- where the rest edge should show up in the game;
- the baseline team-quality read before the rest adjustment;
- the sized effect with its uncertainty;
- the schedule facts that would change the read.

Keep schedule, availability, and matchup as separate adjustments. Label the sized effect as an estimate, not a verdict.

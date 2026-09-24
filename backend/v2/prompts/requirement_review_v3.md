# Requirement review

## Objective
Independently turn every distinct evidence clause in the user's question into a typed requirement ledger, while auditing the draft TaskSpec for omitted subquestions and skills.

## Input
- The user's verbatim question.
- The draft TaskSpec from intake.
- The current capability and skill catalogs.

## Output
One JSON object matching RequirementReview:
- requirements: every evidence clause as {id, description, capability_options, capability_arguments, metric_ids, requested_outputs}. IDs are stable short snake_case names. capability_options lists catalog capabilities that can satisfy that clause. capability_arguments contains provider-facing argument constraints shared by those options, such as stat_category, season, season_type, qualification, or entity id. Use separate requirements when the user asks for separate populations, metrics, scopes, seasons, or phases.
- calculation_requirements: one `{id, description, metric_ids, requested_outputs}` row per explicitly requested independent arithmetic result. Three requested metric changes require three rows; do not collapse them into one generic comparison.
- missing_subquestions: requested answer branches absent from the draft.
- missing_skills: catalog skill names directly required by those branches.

## Invariants
Every calculation named by the request must have its own stable requirement id. Use an empty list only when its category is complete or absent. Never invent catalog names. Distinguish populations, phases, metrics, vintages, and comparison sides named by the user. Preserve explicit requested values in capability_arguments using the selected capability schema's exact argument names and enum spellings. For every ranked request, carry the requested metric, ranking direction, and numeric qualification or volume floor; never reduce a percentage board to a generic scoring-leader requirement. A generic nearby capability or wrong argument does not cover a requested metric, population, or vintage. Each requirement must be satisfiable by one selected capability; if two capabilities are both required, make two requirement rows. Never invent an argument absent from every listed capability schema.

## Stop condition
Stop after every evidence clause in the original request has exactly one requirement row and every omitted analytical branch or skill is listed.

## V3 typed capability-local output amendment
For every capability option, emit exactly one capability_argument_set keyed by that capability ID. Each set contains `arguments.entries` in the provider wire all-slots shape: key, kind, and every value slot; exactly the active slot is non-null (the null kind uses value:null) and all inactive slots are null. Use null for `arguments` or `entries` only to mean an empty set. Never intersect or merge alternatives. Do not emit the legacy shared capability_arguments map.

## Ranked team ratings: typed enum arguments
For a `team_ratings` requirement, the ranked form is two closed enums, both model-authored:
- `requested_metric`: one of OFF_RATING, DEF_RATING, NET_RATING, PACE, TS_PCT, TM_TOV_PCT. Emit the enum ID, never a synonym or display label.
- `ranking_direction`: `asc` or `desc`, the direction the request asks to rank. Emit it explicitly; never omit it on a ranked request.

Map the request's ranking intent to the enum pair deterministically from the words the user used, for example:
- "best defense" or "lowest defensive rating" → DEF_RATING, asc
- "worst offense" → OFF_RATING, asc
- "best net rating" → NET_RATING, desc
- "highest pace" → PACE, desc
- "fewest turnovers" → TM_TOV_PCT, asc

A ranked request without a stated ranking direction is incomplete: leave `ranking_direction` empty rather than guessing. A direct team question (a named team, no ranking) leaves both enums empty. The direction is never inferred from request text by anything downstream.

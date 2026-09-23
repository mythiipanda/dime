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

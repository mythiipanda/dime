# Requirement review

## Objective
Independently turn every distinct evidence clause in the user's question into a typed requirement ledger, while auditing the draft TaskSpec for omitted subquestions and skills.

## Input
- The user's verbatim question.
- The draft TaskSpec from intake.
- The current capability and skill catalogs.

## Output
One JSON object matching RequirementReview:
- requirements: every evidence clause as {id, description, capability_options}. IDs are stable short snake_case names. capability_options lists catalog capabilities that together are required for that clause; use separate requirements when the user asks for separate populations, metrics, scopes, or phases.
- missing_subquestions: requested answer branches absent from the draft.
- missing_skills: catalog skill names directly required by those branches.

## Invariants
Use an empty list only when its category is complete or absent. Never invent catalog names. Distinguish populations, phases, metrics, and comparison sides named by the user. A generic nearby capability does not cover a requested metric or population. Each requirement must be satisfiable by one selected capability; if two capabilities are both required, make two requirement rows.

## Stop condition
Stop after every evidence clause in the original request has exactly one requirement row and every omitted analytical branch or skill is listed.

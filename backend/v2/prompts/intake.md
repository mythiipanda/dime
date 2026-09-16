# Intake

## Objective
Turn the user's question into one structured TaskSpec that fixes what is
being asked, about which entities, and for which season, before any
planning begins. Runs exactly once per turn.

## Input
- The user's current question, verbatim.
- Prior conversation context, when present: up to eight earlier user/assistant turns. Use it only to resolve references, entities, season, and the current goal. It is context, not admitted factual evidence.
- The current date, supplied by the runtime as current_date. Use it only to resolve as_of and the current in-progress season.

## Output
A single JSON object matching the TaskSpec contract, and nothing else.
Fields:
- goal (str): the question restated in one sentence.
- mode ("quick" | "deep_dive" | "project"): the cheapest mode that can
  satisfy the goal.
- deliverable (str): what the answer must contain to satisfy the goal.
- entities (list of {id, type, display_name}): canonical NBA entities;
  type is "player" | "team" | "game" | "league".
- season ({value, source, confidence}) or null: the resolved NBA season,
  e.g. "2025-26"; source is "user" | "context" | "default" | "resolved".
- as_of (ISO date) or null: the date the answer should speak as of.
- subquestions (list of str): the distinct questions inside the goal.
- required_evidence (list of str): capability names the answer needs.
- skills (list of str): applicable names from the supplied skill catalog; [] when none applies.
- assumptions (list of str): interpretations you fixed without being told.
- open_questions (list of str): ambiguities you could not resolve.

## Invariants
- Resolve entities to canonical identity using the context; never invent
  an id.
- Resolve season and as_of explicitly. If neither the question nor the
  context names a season, use the current in-progress season and mark
  source "default".
- Resolve follow-up words such as "that", "he", and "that team" against conversation context when the referent is clear; preserve the resolved entity and prior analytical goal.
- Never copy a factual claim from conversation context into required evidence or treat prior assistant text as proof; plan fresh admitted evidence for the current answer.
- Carry ambiguity into assumptions or open_questions; never silently guess
  on identity, season, metric, or qualification.
- required_evidence names capabilities from the catalog, not prose wishes.
- Select skills automatically by matching the question to each description. Choose only direct matches, never invent a skill name, and use [] when none applies.
- Skills guide later work; they do not change the user goal or replace evidence.
- Do not answer the question. Do not plan tool calls.

## Stop condition
Stop when every field is filled or explicitly null and each unresolved
ambiguity is recorded in open_questions. One pass only.

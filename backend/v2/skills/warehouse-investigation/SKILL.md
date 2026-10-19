---
name: warehouse-investigation
description: Investigate an open-ended NBA question end to end by scoping it, discovering legitimate capabilities and real fields, planning dependent queries, and grounding every claim in issued evidence.
---
# Warehouse investigation

## When to use

Open-ended or multi-step questions where you must decide what evidence is needed, which warehouse capabilities and fields are legitimate, and how the queries depend on each other. Prefer a domain skill (player comparison, team offense, injury impact, playoff translation, trade analysis, and so on) when one already fits the question; reach for this skill when the question spans domains or no single domain skill answers it. Drop to direct SQL only when no capability exposes the needed slice.

## Scope the question first

Restate the decision and the entities, seasons, and constraints it involves. List the sub-questions that must be answered and the evidence that would settle each. Separate what the data can answer from what it cannot. Do not start querying before the question is scoped.

## Discover legitimate capabilities and fields

Enumerate the capabilities that could produce the needed slice, then confirm the real fields, tables, units, and entity identifiers before relying on them. Read the actual column names and value ranges instead of assuming a field exists. If a needed field is absent, say so rather than substituting an unrelated one.

## Plan necessary dependent queries

Order the queries so each one consumes the verified output of the previous one. Run the queries the question actually requires, not a fixed number. Never scan the entire warehouse or run tools to appear thorough; volume of queries is not evidence.

## Check units, entities, season, and completeness

Confirm units, the entity behind each identifier, the season scope, and the completeness of the sample (games, minutes, missing rows) before comparing or concluding. Match seasons and entities across sources. A rate, a season total, and a per-game figure are not interchangeable.

## Reconcile independent counterevidence

Look for evidence that contradicts the emerging answer and explain the disagreement before concluding. Prefer independent lenses over repeated rows from one source. State the strongest counterargument to the answer you are leaning toward.

## Cite issued evidence

Ground every claim in the envelopes actually returned by the tools you ran, and cite the specific envelope and field. Freshness stamps and list-only output do not prove that a metric exists across the warehouse; report what the query returned, not what it implies. Never invent a derived statistic or a measurement that no tool produced, and keep the work read-only.

## Scope unknowns and limitations

Name what remains unknown, which limitations bound the answer, and what evidence would change it. Do not present a partial check as a complete one.

## What NOT to do

- Never treat a short list, a freshness stamp, or an empty query as proof of global availability or absence.
- Never invent a derived stat or a measurement that no tool returned.
- Never run a full-warehouse scan or pad the answer with a fixed number of tools or citations.
- Never substitute an unrelated field for a missing one.
- This is read-only NBA research assistance, not legal advice; make no claims about product features the platform does not have.

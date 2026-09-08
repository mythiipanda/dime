# SPEC-002: Compare composite tool

Problem: comparisons fan out across intel, on-off, and four factors over
several rounds. Top demand pattern at 10 of 40 questions.

Change: `get_compare(a, b)` runs intel plus on-off plus four factors for
both ids in parallel and returns side-by-side rows with deltas.

Surface: one tool call, one table, one chart. Chat renders the existing
leaders-style bars per category.

Verify: scenario asserts Luka versus SGA rows carry both names plus
efficiency deltas. Chat test shows one composite call, not six.

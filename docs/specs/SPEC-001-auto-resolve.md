# SPEC-001: Auto-resolve names inside id tools

Problem: 32 of 69 tool calls are `resolve_entity`. Every run spends a full
LLM round just turning a name into an id. Comparisons need two.

Change: id params accept names or numbers. `get_player_intel("Luka Doncic")`
resolves internally through static tables. Integers pass through untouched.

Surface: same tool names, widened schemas. Planner prompt drops the
resolve-first rule for single entities. Comparisons still resolve once
each, inside the composite.

Verify: eval asserts name and id inputs return identical rows. Scenario
replays a compare with zero explicit resolve calls.

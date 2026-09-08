# SPEC-005: Trade checker

Problem: trade season drives daily questions. Legality needs payroll
math, not opinions.

Change: `get_trade_check` resolves names to salaries from the vendored
cap table and applies simplified 2023 CBA rules. 125 percent plus 250k
matching below the second apron. Full matching above it. No aggregation
above the second apron. Picks and exceptions stay out of v1.

Surface: Explore tab panel with two team blocks plus verdict badge.
Chat answers through the same tool.

Verify: eval asserts a verdict with issues list. Browser shows the badge.

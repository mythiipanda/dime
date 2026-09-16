# Repair

## Objective
Produce the smallest follow-up Plan that satisfies a VerificationReport's
repair instructions. One targeted repair per turn; never a full replan.

## Input
- The TaskSpec.
- The VerificationReport: repair_instructions, missing_branches,
  contradictions.
- The evidence already collected (evidence_ids and capabilities), so
  repair does not refetch it.
- The capability catalog: name and one-line description of each available
  capability.

## Output
A single JSON object matching the Plan contract, and nothing else:
{ "nodes": [PlanNode, ...] }. Each PlanNode:
- id (str): short, unique slug.
- description (str): what evidence this node produces.
- depends_on (list of str): ids that must complete first; [] if independent.
- capability_hints (list of str): names from the supplied catalog only.
- covers_requirement_ids (list of str): TaskSpec requirement IDs this node satisfies.
- arguments (object): explicit tool arguments grounded in the TaskSpec; never invent ids.
- max_attempts (int, 1-5, default 1).
- status: leave as "pending"; the executor owns it.

## Invariants
- Every node traces to one specific repair_instruction or missing branch;
  no speculative nodes.
- Do not repeat a capability whose evidence is already collected unless an
  instruction names staleness or contradiction in that evidence.
- If an instruction is a drafting problem, not a data problem, plan no
  node for it; re-synthesis handles drafting fixes.
- Keep the DAG valid, minimal, and parallel. Stay within the turn's repair
  budget.

## Stop condition
Stop when every repair instruction is covered by exactly one planned node
or explicitly left for re-synthesis.

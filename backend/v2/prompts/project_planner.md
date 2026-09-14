# Project planner

## Objective
Turn a project-mode TaskSpec, such as a one-team season outlook, into a
persistent Plan the executor can run node by node, checkpoint after each,
and resume without replaying completed work.

## Input
- The project TaskSpec, including its deliverable sections.
- The capability catalog: name and one-line description of each available
  capability.
- Prior plan state and collected evidence_ids, when resuming.

## Output
A single JSON object matching the Plan contract, and nothing else:
{ "nodes": [PlanNode, ...] }. Each PlanNode:
- id (str): short, unique slug.
- description (str): what evidence this node produces.
- depends_on (list of str): ids that must complete first; [] if independent.
- capability_hints (list of str): names from the supplied catalog only.
- arguments (object): explicit tool arguments grounded in the TaskSpec; never invent ids.
- expected_schema (object): the shape of the EvidenceEnvelope rows this
  node should return.
- completion_test (str): a checkable condition for when the node is done.
- max_attempts (int, 1-5, default 1).
- status ("pending" | "running" | "complete" | "failed" | "skipped"):
  "pending" for new nodes; preserved from prior state when resuming.

## Invariants
- One node per deliverable evidence need. A worker receives one node plus
  the evidence it depends on, never the full transcript.
- depends_on expresses real data dependence, so the executor can
  checkpoint and resume node by node.
- Separate observed facts, assumptions, and projections: baseline and
  continuity nodes produce observed evidence; scenario nodes produce
  declared calculations with parent evidence_ids, never freeform
  forecasts.
- Projections are explicit low/central/high scenario calculations, not
  trained-model claims.
- On resume, keep completed nodes untouched; plan only pending or failed
  nodes and new instructions.
- Every deliverable section maps to at least one node.

## Stop condition
Stop when the DAG covers every deliverable section, with observed-evidence
nodes upstream and scenario nodes downstream.

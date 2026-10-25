# Action loop

Return exactly one action.

- action=tool: supply a complete Plan DAG whose nodes together cover every task
  requirement and required evidence. Declare covers_requirement_ids, depends_on,
  capability_hints, and arguments explicitly. Use dependency nodes such as
  entity_resolution when a later capability needs a resolved identity. Do not
  send a single bare capability for a multi-step task.
- action=answer: supply a cited DraftReport using only evidence already admitted.
  Answer only from the evidence you have actually received.

Use only the listed tools. Do not assume a requirement is covered unless a plan
node declares it.

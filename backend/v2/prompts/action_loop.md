# Action loop

Return exactly one action.

- action=tool: supply a complete Plan DAG whose nodes together cover every task
  requirement and required evidence. Declare covers_requirement_ids, depends_on,
  capability_hints, and arguments explicitly. Use dependency nodes such as
  entity_resolution when a later capability needs a resolved identity. Do not
  send a single bare capability for a multi-step task.
- action=answer: supply a cited DraftReport using only evidence already admitted.
  Answer only from the evidence you have actually received.

Binding shape:
- Selectors are canonical evidence paths with no JSONPath prefix:
  rows[0].PTS and row_selector rows[0], never $.rows[0].PTS.
- For a row subject, subject_selector must name its identity column, for example
  rows[0].TEAM_ID, never the row object rows[0].
- Cite the exact evidence_id and output_id returned by the tool.
- A calculation binding is allowed only for an id listed in
  task.calculation_requirements. When that list is empty, bind the observed
  output directly (for example MEAN_PPG or POINTS_PER_GAME to rows[0].PPG);
  do not invent calculation authority or a denominator.
- If defects is non-empty, correct every listed defect in the next action.

Use only the listed tools. Do not assume a requirement is covered unless a plan
node declares it.

# Dime NBA analysis

Dime answers basketball and open-ended analytical questions through a domain platform layer built on top of the Pi agent runtime. This vocabulary separates the agent platform, the measurements it retrieves or computes, the artifacts it produces, and how deliverables are evaluated.

## Language

### Platform and runtime

**Domain platform layer**:
Dime's thin adapter, tool, workspace, skill, and artifact platform around a single Pi `AgentSession`. It supplies NBA warehouse access, Python execution, domain tools, and rich UI artifacts without forcing multi-stage DAG pipelines or brittle refusal gates.
_Avoid_: v2 pipeline, codemode cage

**Thread workspace**:
The persistent, isolated filesystem directory scoped to a conversation thread where `run_python` scripts, intermediate datasets, and generated plots survive across follow-up turns.
_Avoid_: ephemeral temp folder

**Structured artifact**:
A typed visual or tabular deliverable (`table`, `compare`, `chart`, `shot_chart`, `scatter`, or file/plot output) emitted alongside an answer and rendered interactively by the frontend.

### Investigations

**Conversation**:
An ordered dialogue pursuing an investigation, identified by an owner and a thread.
_Avoid_: analyst session

**Thread**:
The conversation stream to which questions, answers, workspace files, and source references belong.

**Turn**:
One user or assistant message in a conversation, stored in full without character slicing.
_Avoid_: exchange, run

**Exchange**:
A user question and the assistant response to it, comprising two turns.

**Run**:
One execution attempt to answer a question. A follow-up question or another attempt can produce a different run in the same conversation.
_Avoid_: conversation, turn

**Branch**:
A conversation path with an origin at an earlier turn.

**Analyst session**:
The working context used to answer a question, including compacted conversation history, thread workspace state, and source observations.
_Avoid_: conversation

**Workspace**:
A named collection of conversation and brief references shared under an owner token.
_Avoid_: project, thread workspace

**Project**:
A saved analysis goal with tracked progress and an outcome.
_Avoid_: conversation, workspace, run

### Measurements

**Metric**:
A named basketball quantity, such as points, rebounds, or true shooting.

**Measurement**:
A value for a metric concerning a subject and scope, interpreted through its unit, basis, and provenance.

**Unit**:
The quantity or scale in which a value is expressed, such as points, games, a fraction, or a percentage.
_Avoid_: basis

**Basis**:
The aggregation or normalization of a measurement, such as a cumulative total, per game, or per 100 possessions.
_Avoid_: unit

**Total**:
An accumulated quantity within a stated scope. A total over available rows need not cover a full season.

**Per-game value**:
A quantity divided by games played in the stated scope. It is distinct from the cumulative total.

**True shooting fraction**:
A dimensionless scoring-efficiency ratio, calculated as points divided by twice the sum of field-goal attempts and 0.44 times free-throw attempts. A fraction of 0.637 displays as 63.7%.

**Derived value**:
A value calculated from source measurements through SQL or Python execution.

**Estimate**:
A value carrying approximation or uncertainty. Multiplying a rounded per-game value by games played produces an estimate rather than an exact total.

**Season**:
A canonical NBA season, such as 2024-25. A source may encode that same season using a different label or identifier.

**Phase**:
The part of a season covered by a measurement, such as regular season or playoffs. A season label alone does not establish phase.

**Coverage**:
The subjects, fields, time windows, and populations addressed by a source, including declared limits.

**Provenance**:
The origin and collection context of an observation, attached as advisory metadata rather than a hard submission blocker.

**Source vintage**:
The version or time associated with the source content. It is distinct from when Dime obtained it.

**As of**:
The effective date or cutoff declared by a source for its content.

**Fetched at**:
The time Dime retrieved source content.

**Observed at**:
The time Dime recorded an observation. It does not establish the effective date of the underlying fact.

### Sources and answers

**Source record**:
The preserved outcome of consulting a tool, SQL query, or Python script, including returned data, metadata, or an empty result. Zero rows is a valid observation, not a tool failure.

**Source reference**:
A stable handle identifying a source record that an answer may cite as provenance.
_Avoid_: verified citation, mandatory cell anchor

**Gap**:
A requested part of an analysis that remains unresolved after consulting available warehouse tables and tools.

### Evaluation (Dime Agent Benchmark / DAB)

**Deliverable**:
The complete final output of an agent run on a benchmark task, including prose synthesis, tables, visual artifacts, and workspace outputs.

**Binary rubric criterion**:
An atomic, expert-authored pass/fail check verifying a required factual extraction, statistical calculation, cap/CBA rule application, or methodological caveat in a deliverable.

**Hallucination-gated all-pass rate**:
The primary Harvey-LAB-inspired headline metric in DAB. A task scores 100% only when every required rubric criterion passes and zero fabricated numbers or ungrounded claims appear; otherwise the task scores 0%.

**Criterion pass rate**:
The secondary diagnostic metric tracking the fraction of individual rubric criteria satisfied across all tasks.

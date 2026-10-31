# Dime NBA analysis

Dime answers basketball questions using source observations. This vocabulary separates an investigation, the measurements it finds and the claims made about them.

## Language

### Investigations

**Conversation**:
An ordered dialogue pursuing an investigation, identified by an owner and a thread.
_Avoid_: analyst session

**Thread**:
The conversation stream to which questions, answers and source references belong.

**Turn**:
One user or assistant message in a conversation.
_Avoid_: exchange, run

**Exchange**:
A user question and the assistant response to it, comprising two turns.

**Run**:
One execution attempt to answer a question. A follow-up question or another attempt can produce a different run in the same conversation.
_Avoid_: conversation, turn

**Branch**:
A conversation path with an origin at an earlier turn.

**Analyst session**:
The working context used to answer a question, including available conversation history and source observations.
_Avoid_: conversation

**Workspace**:
A named collection of conversation and brief references shared under an owner token.
_Avoid_: project

**Project**:
A saved analysis goal with tracked progress and an outcome.
_Avoid_: conversation, workspace, run

### Measurements

**Metric**:
A named basketball quantity, such as points, rebounds or true shooting.

**Measurement**:
A value for a metric concerning a subject and scope, interpreted through its unit, basis and provenance.

**Unit**:
The quantity or scale in which a value is expressed, such as points, games, a fraction or a percentage.
_Avoid_: basis

**Basis**:
The aggregation or normalization of a measurement, such as a cumulative total, per game or per possession.
_Avoid_: unit

**Total**:
An accumulated quantity within a stated scope. A total over available rows need not cover a full season.

**Per-game value**:
A quantity divided by games played in the stated scope. It is distinct from the cumulative total.

**True shooting fraction**:
A dimensionless scoring-efficiency ratio, calculated as points divided by twice the sum of field-goal attempts and 0.44 times free-throw attempts. A fraction of 0.637 displays as 63.7%.

**Derived value**:
A value calculated from source measurements through a stated operation.

**Estimate**:
A value carrying approximation or uncertainty. Multiplying a rounded per-game value by games played produces an estimate rather than an exact total.

**Season**:
A canonical NBA season, such as 2024-25. A source may encode that same season using a different label or identifier.

**Phase**:
The part of a season covered by a measurement, such as regular season or playoffs. A season label alone does not establish phase.

**Coverage**:
The subjects, fields, time windows and populations addressed by a source, including declared limits.

**Provenance**:
The origin and collection context of an observation.

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
The preserved outcome of consulting a source, including returned data, metadata or a failure. A record alone does not establish support for a claim.

**Source reference**:
A stable handle identifying a source record.
_Avoid_: verified citation, evidence identifier

**Evidence**:
Source observations that support a particular claim within their declared scope.
_Avoid_: every source record

**Evidence envelope**:
A structured observation carrying source identity, measurements, scope, lineage and qualifications.
_Avoid_: raw source record

**Claim**:
A statement in an answer, including an observed value, a derived value, an estimate or a judgment.

**Verified claim**:
A claim whose support has passed the applicable evidence and calculation checks.
_Avoid_: completed run

**Unassessed**:
An answer or claim whose support has not been verified. It does not mean the claim is false.

**Gap**:
A requested part of an analysis that remains unresolved. A failed or empty query alone does not establish that the information is absent from all sources.

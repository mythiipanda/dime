# Eval trace schema (v1, 2026-09-28)

Structured trace logging starts now. Every harness run writes one JSONL
file to `backend/evals/traces/<run-id>.jsonl`. One JSON object per line.
When the product later logs live analyst traffic, it must use the same
event names and field names so a monthly crew pass can mine recurring
failures into skill revisions.

## Events

- `run_started` {flags}
- `suite_started` {suite, mode}
- `suite_finished` {suite, mode, passed, failed, skipped, seconds}
- `question_asked` {suite, qid, question, generation}
- `skills_selected` {qid, skills, entity_level, source}
  (`source`: recorded | live-llm | production)
- `tools_called` {qid, tools: [names in call order]}
- `answer_received` {qid, answer_chars, latency_s}
- `verdict` {qid, criterion, score_1_10 | pass_bool, detail}
- `escalation` {qid, from_judge, to_judge, reason}
- `calibration_bucket` {bucket, n, hit_rate}
- `frontier_candidate` {qid, kept_bool, reason}

## Field rules

- `qid` is stable across runs (e.g. `g1`, `sf07`, `f-mining-012`).
- `skills` lists v1 skill names exactly as the finder returned them.
- `tools` lists tool names in call order, duplicates kept.
- Scores are 1-10 integers per the judge rubric, never 1-5.
- A `verdict` with `pass_bool: false` must carry `detail` naming the
  expected-vs-got gap. No bare fails.
- Never log raw credentials, request bodies with keys, or warehouse
  file paths outside the sandbox.

## Monthly mining pass (process)

Once a month a crew run reads the traces and distills recurring
failures into skill revisions: same wrong-skill picks, same verifier
gaps, same hedging patterns. Findings land as SKILL.md edits, not as
more prose in this file.

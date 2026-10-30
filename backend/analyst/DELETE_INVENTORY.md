# Pi deletion inventory

Base: origin/dev `8dd87c3f1151088df21873e455d276fe0d08284d`. This is an uncommitted deletion wave for parent review.

## Deleted implementation

- `backend/evals/schema_conformance.py`
- `backend/evals/validate_typed_argument_binding.py`
- `backend/scripts/capability_probe.py`
- `backend/scripts/schema_conformance_probe.py`
- `backend/v2/adapters/endpoint_capabilities.json`
- `backend/v2/adapters/model_budgets.json`
- `backend/v2/adapters/models.py`
- `backend/v2/adapters/structured.py`
- `backend/v2/prompts/__init__.py`
- `backend/v2/prompts/action_loop.md`
- `backend/v2/prompts/intake.md`
- `backend/v2/prompts/planner.md`
- `backend/v2/prompts/planner_v3.md`
- `backend/v2/prompts/project_planner.md`
- `backend/v2/prompts/repair.md`
- `backend/v2/prompts/repair_answer.md`
- `backend/v2/prompts/requirement_review.md`
- `backend/v2/prompts/requirement_review_v3.md`
- `backend/v2/prompts/synthesizer.md`
- `backend/v2/prompts/verifier.md`
- `backend/v2/runtime/action_loop.py`
- `backend/v2/runtime/analysis_execution.py`
- `backend/v2/runtime/assembly.py`
- `backend/v2/runtime/budget.py`
- `backend/v2/runtime/checkpoints.py`
- `backend/v2/runtime/executor.py`
- `backend/v2/runtime/failures.py`
- `backend/v2/runtime/fakes.py`
- `backend/v2/runtime/fast_path.py`
- `backend/v2/runtime/ledger.py`
- `backend/v2/runtime/loop.py`
- `backend/v2/runtime/policy.py`
- `backend/v2/runtime/presentation.py`
- `backend/v2/runtime/projections.py`
- `backend/v2/runtime/recording.py`
- `backend/v2/runtime/subsumption.py`
- `backend/v2/skills.py`

The two eval drivers and capability probe exclusively exercised the removed staged provider/planner path. Their deletion makes no assertion about Pi evaluation results. The schema/capability snapshot data remains consumed by revision preflight. Snapshot contents and captured pins are unchanged.

## Remaining callers

- HTTP and CLI use `analyst.product_session.stream_product_session` and `analyst.configuration.resolve_product_model`.
- The catalogue regeneration script uses `adapters.capabilities.capability_catalog`, with the same authoritative tool schemas and values as before.
- `adapters.core`, `adapters.web`, `domain`, projects, conversations and API activity retain shared contracts. SQL execution, warehouse annotation, historical units and season implementations are unchanged.
- `ConversationStore.resolve_user_turns` compares the persisted `turn_start` value directly; it no longer imports the stage ledger for an enum value. Branch/activity data remains intact.
- Typed binding admission, immutable evidence views and mechanical checks remain in `runtime/models.py`, `runtime/interfaces.py` and `runtime/verifier.py`. RuntimeResult publication validation, orchestration interfaces and task-output propagation were removed.

## Test retirement

Only assertions tied to the replaced runtime, stage adapters, prompts, provider recovery, typed publication and stage-specific diagnostics were retired. Mixed files retain independent SQL, source, unit, season, ownership and admission checks. The remaining ratings-tool source checks still inspect the actual tool implementation. Obsolete stage-source pins were retired with their implementations, not rewritten to assert Pi behavior. Shared durability checks remain.

The following test files had no surviving independent tests after their removed dependencies were retired. Mixed-file changes are visible in the diff.

- `backend/tests/test_schema_conformance.py`
- `backend/tests/test_scope_gate_fallback.py`
- `backend/v2/adapters/tests/test_draft_domain_normalization.py`
- `backend/v2/adapters/tests/test_plan_output_vocabulary.py`
- `backend/v2/adapters/tests/test_relative_season.py`
- `backend/v2/adapters/tests/test_skill_selection.py`
- `backend/v2/adapters/tests/test_warehouse_investigation_skill.py`
- `backend/v2/runtime/tests/test_action_loop.py`
- `backend/v2/runtime/tests/test_action_loop_provider_route.py`
- `backend/v2/runtime/tests/test_action_runtime.py`
- `backend/v2/runtime/tests/test_completeness_repair.py`
- `backend/v2/runtime/tests/test_loop.py`
- `backend/v2/runtime/tests/test_period_scope_admission.py`
- `backend/v2/runtime/tests/test_plan_coverage_repair.py`
- `backend/v2/runtime/tests/test_plan_output_repair.py`
- `backend/v2/runtime/tests/test_recording.py`
- `backend/v2/runtime/tests/test_replan.py`
- `backend/v2/runtime/tests/test_replan_lineage.py`
- `backend/v2/runtime/tests/test_run_budget.py`
- `backend/v2/runtime/tests/test_task_output_propagation.py`
- `backend/v2/tests/compatibility/harness.py`
- `backend/v2/tests/compatibility/test_pack.py`
- `backend/v2/tests/compatibility/test_revision.py`
- `backend/v2/tests/runtime/test_absence_grounding_prompt_routing.py`
- `backend/v2/tests/runtime/test_advisory_semantic_review.py`
- `backend/v2/tests/runtime/test_answer_source_line.py`
- `backend/v2/tests/runtime/test_contradicting_tails.py`
- `backend/v2/tests/runtime/test_failure_classification.py`
- `backend/v2/tests/runtime/test_failures.py`
- `backend/v2/tests/runtime/test_fast_path.py`
- `backend/v2/tests/runtime/test_first_token_watchdog_bound.py`
- `backend/v2/tests/runtime/test_gap_names_quantity.py`
- `backend/v2/tests/runtime/test_groq_retry_policy.py`
- `backend/v2/tests/runtime/test_intake_no_gate.py`
- `backend/v2/tests/runtime/test_ledger.py`
- `backend/v2/tests/runtime/test_ledger_hardening.py`
- `backend/v2/tests/runtime/test_mode_capability_profiles.py`
- `backend/v2/tests/runtime/test_model_input_replay.py`
- `backend/v2/tests/runtime/test_nim_thinking_off.py`
- `backend/v2/tests/runtime/test_planner_metric_agreement.py`
- `backend/v2/tests/runtime/test_planner_ranked_agreement.py`
- `backend/v2/tests/runtime/test_planner_ranked_subject_agreement.py`
- `backend/v2/tests/runtime/test_policy.py`
- `backend/v2/tests/runtime/test_projections.py`
- `backend/v2/tests/runtime/test_prose_covered_kind_tail.py`
- `backend/v2/tests/runtime/test_publication_selector_resolution.py`
- `backend/v2/tests/runtime/test_published_answer.py`
- `backend/v2/tests/runtime/test_published_citations.py`
- `backend/v2/tests/runtime/test_published_prose_scrub.py`
- `backend/v2/tests/runtime/test_q8_strip_repro.py`
- `backend/v2/tests/runtime/test_reasoning_content_fallback.py`
- `backend/v2/tests/runtime/test_recording.py`
- `backend/v2/tests/runtime/test_recording_projection_compatibility.py`
- `backend/v2/tests/runtime/test_reflection_reasoning_effort.py`
- `backend/v2/tests/runtime/test_requirement_review_timeout_policy.py`
- `backend/v2/tests/runtime/test_single_llm_retry.py`
- `backend/v2/tests/runtime/test_slow_model_route_timeouts.py`
- `backend/v2/tests/runtime/test_stage_schema_portability.py`
- `backend/v2/tests/runtime/test_structured_output_ladder.py`
- `backend/v2/tests/runtime/test_subsumption.py`
- `backend/v2/tests/test_artifact_resolution.py`
- `backend/v2/tests/test_mixed_metric_coverage.py`
- `backend/v2/tests/test_open_question_outputs.py`
- `backend/v2/tests/test_prompts.py`
- `backend/v2/tests/test_provider_failure_kind.py`
- `backend/v2/tests/test_public_tool_call_arguments.py`
- `backend/v2/tests/test_runtime_timeout_wiring.py`
- `backend/v2/tests/test_skills.py`
- `backend/v2/tests/test_status_lines.py`

## Verification limits

Synthetic SDK/HTTP/CLI execution proves integration, sources, terminal errors and cleanup. It does not prove live-provider behavior or analyst answer quality. Existing absent frontend source files and stale frontend source assertions are disclosed in the handoff. No frontend changes, real warehouse, real inference, deployment, frozen evaluation changes or full Docker/Next build were performed.

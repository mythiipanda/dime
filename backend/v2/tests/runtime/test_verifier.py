from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from v2.contracts import Claim, ClaimKind, DraftReport, EntityRef, SeasonRef, TaskSpec, VerificationReport, VerificationStatus
from v2.domain.calculations import Calculation, CalculationInput, CalculationOperation
from v2.runtime.verifier import merge_verification_reports, validate_semantic_report, verify_mechanical


def task(season="2025-26"):
    from v2.contracts import RunMode
    return TaskSpec(goal="Rank Boston", mode=RunMode.QUICK, deliverable="answer",
        entities=[EntityRef(id="BOS", type="team", display_name="Boston Celtics")],
        season=SeasonRef(value=season, source="user", confidence=1), as_of=date(2026, 4, 15))


def evidence(**changes):
    from v2.contracts import EvidenceEnvelope
    values = dict(evidence_id="standings", capability="standings", source="warehouse:standings",
        observed_at=datetime(2026, 4, 15, 12, tzinfo=UTC), season="2025-26", as_of=date(2026, 4, 15),
        entities=[EntityRef(id="BOS", type="team", display_name="Boston Celtics")],
        rows=[{"TEAM": "Boston Celtics", "W": 61, "WIN_PCT": 0.744},
              {"TEAM": "New York Knicks", "W": 52, "WIN_PCT": 0.634}],
        units={"W": "wins", "WIN_PCT": "percent"},
        metric_definitions={"W": "regular-season wins", "WIN_PCT": "wins divided by games"},
        qualification="All teams with 82 games", coverage="All 30 NBA teams")
    values.update(changes)
    return EvidenceEnvelope(**values)


def report(claim):
    return DraftReport(sections=[claim.text], claims=[claim])


def test_observed_claim_passes_with_number_date_season_entity_and_units():
    claim = Claim(text="As of 2026-04-15, the Boston Celtics had 61 wins in 2025-26.",
                  kind=ClaimKind.OBSERVED, evidence_ids=["standings"])
    result = verify_mechanical(task(), report(claim), [evidence()])
    assert result.status == VerificationStatus.PASS
    assert result.claim_results[0].supported


def test_rejects_uncited_numeral_date_and_season():
    claim = Claim(text="As of 2026-04-14, Boston had 62 wins in 2024-25.",
                  kind=ClaimKind.OBSERVED, evidence_ids=["standings"])
    reasons = verify_mechanical(task(), report(claim), [evidence()]).claim_results[0].reasons
    assert "uncited numeral 62" in reasons
    assert "uncited date 2026-04-14" in reasons
    assert "uncited season 2024-25" in reasons


def test_percent_scaling_and_declared_constant_are_supported():
    claim = Claim(text="Boston won 74.4% across 82 games.", kind=ClaimKind.OBSERVED,
                  evidence_ids=["standings"])
    assert verify_mechanical(task(), report(claim), [evidence()], allowed_constants=[82]).status == VerificationStatus.PASS


def test_maximum_rejected_claims_do_not_overflow_repair_report():
    claims = [Claim(
        text=f"Unsupported value {index + 1000}.", kind="judgment",
    ) for index in range(128)]
    draft = DraftReport(sections=["Also 999999."], claims=claims)

    result = verify_mechanical(task(), draft, [])

    assert result.status == VerificationStatus.REPAIR
    assert len(result.claim_results) == 128
    assert len(result.repair_instructions) == 128
    assert all(not item.supported for item in result.claim_results)


def test_entity_season_and_as_of_mismatches_fail():
    bad = evidence(entities=[EntityRef(id="NYK", type="team", display_name="New York Knicks")],
                   season="2024-25", as_of=date(2026, 4, 16))
    claim = Claim(text="Boston had 61 wins.", kind=ClaimKind.OBSERVED, evidence_ids=["standings"])
    reasons = verify_mechanical(task(), report(claim), [bad]).claim_results[0].reasons
    assert "cited evidence entities do not match the task entities" in reasons
    assert any("does not match task season" in r for r in reasons)
    assert any("after task as-of" in r for r in reasons)


def test_rank_requires_qualification_and_coverage():
    claim = Claim(text="Boston ranks 1st with 61 wins.", kind=ClaimKind.OBSERVED, evidence_ids=["standings"])
    result = verify_mechanical(task(), report(claim), [evidence(qualification=None, coverage=None)], allowed_constants=[1])
    assert "rank claim lacks qualification evidence" in result.claim_results[0].reasons
    assert "rank claim lacks coverage evidence" in result.claim_results[0].reasons
    assert "rank claim lacks a recomputable rank calculation" in result.claim_results[0].reasons


def test_derived_claim_recomputes_calculation_and_lineage():
    from v2.contracts import EvidenceEnvelope
    raw = evidence()
    derived = EvidenceEnvelope(evidence_id="derived", capability="calculation", source="runtime",
        observed_at=datetime(2026, 4, 15, tzinfo=UTC), season="2025-26", entities=raw.entities,
        rows={"win_gap": 9}, lineage=["standings"])
    calc = Calculation(calculation_id="gap", operation=CalculationOperation.SUBTRACT,
        inputs=[CalculationInput(evidence_id="standings", path="rows[0].W"),
                CalculationInput(evidence_id="standings", path="rows[1].W")],
        result=Decimal("9"), unit="wins")
    claim = Claim(text="Boston's lead was 9 wins.", kind=ClaimKind.DERIVED,
                  evidence_ids=["derived"], calculation_id="gap")
    assert verify_mechanical(task(), report(claim), [raw, derived], [calc]).status == VerificationStatus.PASS


def test_bad_calculation_and_unknown_evidence_fail_closed():
    calc = Calculation(calculation_id="gap", operation=CalculationOperation.SUBTRACT,
        inputs=[CalculationInput(evidence_id="standings", path="rows[0].W"),
                CalculationInput(evidence_id="standings", path="rows[1].W")], result=Decimal("10"))
    claim = Claim(text="The gap was 10 wins.", kind=ClaimKind.DERIVED,
                  evidence_ids=["missing"], calculation_id="gap")
    result = verify_mechanical(task(), report(claim), [evidence()], [calc])
    assert result.status == VerificationStatus.REPAIR
    assert any("unknown evidence ids" in r for r in result.claim_results[0].reasons)
    assert any("does not recompute" in r for r in result.claim_results[0].reasons)


def test_semantic_contract_rejects_replacement_facts():
    assert validate_semantic_report({"status": "pass", "claim_results": []}).status == VerificationStatus.PASS
    with pytest.raises(ValueError, match="forbidden fields"):
        validate_semantic_report({"status": "repair", "replacement_facts": ["Boston won 61"]})
    with pytest.raises(ValueError, match="one VerificationReport"):
        validate_semantic_report("[]")


def test_report_merge_preserves_both_verifiers_failures():
    mechanical = VerificationReport(status="repair",
        claim_results=[{"claim_index": 0, "supported": False, "reasons": ["number"]}])
    semantic = VerificationReport(status="partial",
        claim_results=[{"claim_index": 0, "supported": False, "reasons": ["inference"]}],
        missing_branches=["risks"])
    merged = merge_verification_reports(mechanical, semantic)
    assert merged.status == VerificationStatus.REPAIR
    assert merged.claim_results[0].reasons == ["number", "inference"]
    assert merged.missing_branches == ["risks"]


def test_rank_recomputation_passes_with_complete_population():
    calc = Calculation(
        calculation_id="rank", operation=CalculationOperation.RANK_DESC,
        inputs=[CalculationInput(evidence_id="standings", path="rows[0].W"),
                CalculationInput(evidence_id="standings", path="rows[1].W")],
        subject_input=0, result=Decimal("1"),
    )
    claim = Claim(text="Boston ranks 1st with 61 wins.", kind=ClaimKind.DERIVED,
                  evidence_ids=["standings"], calculation_id="rank")
    assert verify_mechanical(task(), report(claim), [evidence()], [calc]).status == VerificationStatus.PASS


def test_uncited_section_fact_is_rejected():
    claim = Claim(text="Boston led the table.", kind=ClaimKind.OBSERVED,
                  evidence_ids=["standings"])
    draft = DraftReport(sections=["Boston won 62 games."], claims=[claim])
    result = verify_mechanical(task(), draft, [evidence()])
    assert result.status == VerificationStatus.REPAIR
    assert "62" in result.repair_instructions[-1]


def test_observation_time_does_not_support_an_as_of_claim():
    claim = Claim(text="As of 2026-04-15, Boston had 61 wins.",
                  kind=ClaimKind.OBSERVED, evidence_ids=["standings"])
    result = verify_mechanical(
        task(), report(claim),
        [evidence(as_of=None, observed_at=datetime(2026, 4, 15, 12, tzinfo=UTC))],
    )
    assert "uncited date 2026-04-15" in result.claim_results[0].reasons


def test_ordered_list_labels_are_not_factual_numerals():
    claim = Claim(text="Boston had 61 wins.", kind=ClaimKind.OBSERVED,
                  evidence_ids=["standings"])
    draft = DraftReport(sections=["1. Boston had 61 wins."], claims=[claim])
    assert verify_mechanical(task(), draft, [evidence()]).status == VerificationStatus.PASS


def test_percent_metric_accepts_human_unit_not_internal_unit_name():
    claim = Claim(text="Boston's WIN PCT was 74.4%.", kind=ClaimKind.OBSERVED,
                  evidence_ids=["standings"])
    assert verify_mechanical(task(), report(claim), [evidence()]).status == VerificationStatus.PASS


def test_bare_list_ordinals_are_not_factual_numerals():
    from v2.runtime.verifier import _number_tokens

    text = "1. Oklahoma City\n2. Boston\n3. Cleveland"
    assert _number_tokens(text) == []


def test_mixed_source_claim_requires_provenance_label():
    from v2.contracts import EvidenceEnvelope

    sga = EvidenceEnvelope(
        evidence_id="sga", capability="player_report",
        source="warehouse:silver_player_season",
        observed_at=datetime(2026, 4, 15, tzinfo=UTC), season="2025-26",
        rows={"player": "SGA", "ppg": 31.1})
    luka = EvidenceEnvelope(
        evidence_id="luka", capability="player_report",
        source="fallback:basketball-reference",
        observed_at=datetime(2026, 4, 15, tzinfo=UTC), season="2025-26",
        rows={"player": "Luka", "ppg": 33.5})
    unlabeled = Claim(
        text="SGA averaged 31.1 PPG and Luka averaged 33.5 PPG.",
        kind="observed", evidence_ids=["sga", "luka"])
    failed = verify_mechanical(task(), report(unlabeled), [sga, luka])
    assert "mixed-source claim does not label differing provenance" in (
        failed.claim_results[0].reasons)

    labeled = unlabeled.model_copy(update={
        "text": ("Warehouse data has SGA at 31.1 PPG; according to the "
                 "Basketball-Reference fallback, Luka averaged 33.5 PPG.")})
    assert verify_mechanical(task(), report(labeled), [sga, luka]).status == "pass"

def test_source_ranked_leader_does_not_require_duplicate_calculation():
    ranked = evidence(
        rows=[{"RANK": 1, "PLAYER": "Boston Celtics", "W": 61}],
        units={"W": "wins"},
        qualification="Qualified teams", coverage="Source-ranked full population")
    claim = Claim(text="Boston is the leader with 61 wins.",
                  kind=ClaimKind.OBSERVED, evidence_ids=["standings"])
    assert verify_mechanical(task(), report(claim), [ranked]).status == VerificationStatus.PASS


def test_multi_vintage_trade_evidence_supports_salary_and_season_claim() -> None:
    from v2.contracts import EvidenceEnvelope

    trade = EvidenceEnvelope(
        evidence_id="trade", capability="trade_value", source="warehouse:trade_value",
        observed_at=datetime(2026, 4, 15, tzinfo=UTC),
        season=None,
        vintages={"production_season": "2025-26", "salary_season": "2026-27"},
        task_season_scoped=False,
        rows={"player": "Jaylen Brown", "salary_26_27": 57_100_000,
              "disclaimer": "2025-26 production versus 2026-27 salaries"},
    )
    claim = Claim(
        text="Jaylen Brown's 2026-27 salary is $57.1M.",
        kind=ClaimKind.OBSERVED, evidence_ids=["trade"],
    )
    assert verify_mechanical(task(), report(claim), [trade]).status == VerificationStatus.PASS


def test_task_season_scope_still_rejects_statistical_vintage_mismatch() -> None:
    wrong = evidence(season="2024-25", task_season_scoped=True)
    claim = Claim(text="Boston had 61 wins.", kind=ClaimKind.OBSERVED,
                  evidence_ids=["standings"])
    result = verify_mechanical(task(), report(claim), [wrong])
    assert any("does not match task season" in reason
               for reason in result.claim_results[0].reasons)


def test_empty_evidence_cannot_support_a_factual_claim() -> None:
    empty = evidence(rows=[])
    claim = Claim(
        text="Boston remains the best team.", kind=ClaimKind.OBSERVED,
        evidence_ids=["standings"],
    )
    result = verify_mechanical(task(), report(claim), [empty])
    assert "factual claim cites evidence with no values" in (
        result.claim_results[0].reasons)


def test_mechanical_verifier_revalidates_copied_inputs() -> None:
    valid = DraftReport(sections=["Answer"], claims=[])
    invalid = valid.model_copy(update={"sections": [" "]})
    with pytest.raises(ValueError, match="sections must not contain empty"):
        verify_mechanical(
            TaskSpec(goal="answer", mode="quick", deliverable="text"),
            invalid, [],
        )


def test_undeclared_source_identity_cannot_support_factual_claim():
    unknown = evidence(warnings=["source identity not declared by tool"])
    claim = Claim(
        text="Boston had 61 wins.", kind=ClaimKind.OBSERVED,
        evidence_ids=["standings"],
    )

    result = verify_mechanical(task(), report(claim), [unknown])

    assert result.status == VerificationStatus.REPAIR
    assert "factual claim cites evidence without declared source identity" in (
        result.claim_results[0].reasons)


def test_entity_alias_ids_match_on_canonical_display_name():
    from v2.contracts import EvidenceEnvelope
    task_with_slug = task().model_copy(update={"entities": [EntityRef(
        id="boston-celtics", type="team", display_name="Boston Celtics")]})
    for evidence_entity in (
        EntityRef(id="1610612738", type="team", display_name="boston-celtics"),
        EntityRef(id="BOS", type="team", display_name="bos"),
    ):
        evidence_with_alias = evidence(entities=[evidence_entity])
        for text in ("The Boston Celtics finished with 61 wins.",
                     "The team's win total was 61."):
            claim = Claim(text=text, kind="observed", evidence_ids=["standings"])
            result = verify_mechanical(
                task_with_slug, report(claim), [evidence_with_alias])
            assert result.status == VerificationStatus.PASS


def test_observed_rank_accepts_matching_explicit_rank_value():
    ranked = evidence(rows={"player": "Jaylen Brown", "usage_rank": 3},
                      qualification="qualified players", coverage="league pool")
    claim = Claim(text="Brown had usage rank #3.", kind="observed",
                  evidence_ids=["standings"])
    result = verify_mechanical(task(), report(claim), [ranked])
    assert not any("rank claim" in reason for reason in result.claim_results[0].reasons)


def test_player_alias_ids_match_on_canonical_identity():
    from v2.contracts import EvidenceEnvelope
    player_task = task().model_copy(update={"entities": [EntityRef(
        id="jaylen-brown", type="player", display_name="Jaylen Brown")]})
    player_evidence = evidence(entities=[EntityRef(
        id="1627759", type="player", display_name="Jaylen Brown")],
        rows={"player": "Jaylen Brown", "player_id": "1627759", "ppg": 28.7})
    for text in ("Jaylen Brown averaged 28.7 points.",
                 "He averaged 28.7 points."):
        claim = Claim(text=text, kind="observed", evidence_ids=["standings"])
        result = verify_mechanical(player_task, report(claim), [player_evidence])
        assert result.status == VerificationStatus.PASS


def test_natural_language_rating_unit_matches_declared_machine_unit():
    ev = evidence(units={"OFF_RATING": "points_per_100_possessions"})
    ev = ev.model_copy(update={"rows": [{"TEAM": "Denver", "OFF_RATING": 126.1}]})
    claim = Claim(text="Denver's offensive rating was 126.1 points per 100 possessions.", kind="observed", evidence_ids=[ev.evidence_id])
    result = verify_mechanical(TaskSpec(goal="ratings", mode="quick", deliverable="answer"), report(claim), [ev], allowed_constants=[1])
    assert result.status == "pass"
    assert result.claim_results[0].supported


def test_nested_prediction_metrics_match_declared_units():
    ev = evidence(
        rows={"estimate": {"win_prob": {"BOS": 0.548},
                           "projected_score": {"BOS": 113.6}}},
        units={"win_prob": "fraction_0_1", "projected_score": "points"},
    )
    claim = Claim(
        text="Boston had a 54.8 percent win probability.", kind="observed",
        evidence_ids=[ev.evidence_id],
    )
    report = verify_mechanical(task(), DraftReport(sections=[], claims=[claim]), [ev])
    assert report.claim_results[0].supported is True

def test_prediction_probability_with_nested_metric_is_publishable():
    ev = evidence(
        rows={"estimate": {"win_prob": {"BOS": 0.548, "NYK": 0.452}}},
        units={"win_prob": "fraction_0_1"},
    )
    claim = Claim(
        text="Boston has a 54.8 percent win probability.", kind="observed",
        evidence_ids=[ev.evidence_id],
    )
    result = verify_mechanical(task(), report(claim), [ev])
    assert result.status == "pass"


def test_qualification_numeral_is_supported_for_population_claim():
    ev = evidence(rows={"PLAYER": "Nikola Jokic", "OFF_RATING": 126.1})
    ev = ev.model_copy(update={
        "qualification": "1,000+ total minutes",
        "units": {"OFF_RATING": "points_per_100_possessions"},
    })
    claim = Claim(
        text=("Among players with 1,000+ total minutes, Nikola Jokic led with "
              "a 126.1 points per 100 possessions offensive rating."),
        kind="observed", evidence_ids=[ev.evidence_id],
    )
    result = verify_mechanical(task(), report(claim), [ev])
    assert result.status == "pass"


def test_cross_evidence_comparison_requires_declared_calculation():
    regular = evidence(evidence_id="regular", capability="team_ratings",
        rows=[{"TEAM": "Boston Celtics", "OFF_RATING": 120.0}],
        units={"OFF_RATING": "points_per_100_possessions"})
    playoffs = evidence(evidence_id="playoffs", capability="playoff_team_ratings",
        rows=[{"TEAM": "Boston Celtics", "OFF_RATING": 111.4}],
        units={"OFF_RATING": "points_per_100_possessions"})
    claim = Claim(
        text="Boston's offensive rating dropped from 120.0 to 111.4 points per 100 possessions.",
        kind="observed", evidence_ids=["regular", "playoffs"])
    result = verify_mechanical(task(), report(claim), [regular, playoffs])
    assert "cross-evidence comparison lacks a declared calculation" in result.claim_results[0].reasons


def test_universal_cross_evidence_claim_requires_declared_calculation():
    regular = evidence(evidence_id="regular", rows=[{"TEAM": "Boston Celtics", "OFF_RATING": 120.0}])
    playoffs = evidence(evidence_id="playoffs", rows=[{"TEAM": "Boston Celtics", "OFF_RATING": 111.4}])
    claim = Claim(text="Every playoff team declined.", kind="judgment",
                  evidence_ids=["regular", "playoffs"])
    result = verify_mechanical(task(), report(claim), [regular, playoffs])
    assert "cross-evidence comparison lacks a declared calculation" in result.claim_results[0].reasons


def test_population_claim_numerals_must_match_named_entity_row():
    table = evidence(
        rows=[
            {"TEAM_NAME": "Boston Celtics", "OFF_RATING": 111.4, "DEF_RATING": 108.8},
            {"TEAM_NAME": "Cleveland Cavaliers", "OFF_RATING": 109.7, "DEF_RATING": 112.3},
        ],
        units={"OFF_RATING": "points_per_100_possessions",
               "DEF_RATING": "points_per_100_possessions"},
    )
    wrong = Claim(
        text="Cleveland Cavaliers had an offensive rating of 111.4 points per 100 possessions.",
        kind="observed", evidence_ids=[table.evidence_id],
    )
    result = verify_mechanical(
        TaskSpec(goal="Cleveland rating", mode="quick", deliverable="answer"),
        report(wrong), [table],
    )
    assert result.status == VerificationStatus.REPAIR
    assert any("named entity row" in reason
               for reason in result.claim_results[0].reasons)


def test_population_claim_accepts_numeral_from_named_entity_row():
    table = evidence(
        rows=[
            {"TEAM_NAME": "Boston Celtics", "OFF_RATING": 111.4},
            {"TEAM_NAME": "Cleveland Cavaliers", "OFF_RATING": 109.7},
        ],
        units={"OFF_RATING": "points_per_100_possessions"},
    )
    right = Claim(
        text="Cleveland Cavaliers had an offensive rating of 109.7 points per 100 possessions.",
        kind="observed", evidence_ids=[table.evidence_id],
    )
    result = verify_mechanical(
        TaskSpec(goal="Cleveland rating", mode="quick", deliverable="answer"),
        report(right), [table],
    )
    assert result.status == VerificationStatus.PASS


def test_metric_name_digit_is_not_treated_as_an_asserted_measurement():
    table = evidence(
        rows=[
            {"team": "LEAGUE", "corner_3_efg": 0.5746},
            {"team": "BOS", "corner_3_efg": 0.6043},
        ],
        units={"corner_3_efg": "fraction_0_1"},
    )
    claim = Claim(
        text="Boston's corner 3-point efficiency was 60.43%.",
        kind="observed", evidence_ids=[table.evidence_id],
    )
    result = verify_mechanical(
        TaskSpec(goal="Boston shot zones", mode="quick", deliverable="answer"),
        report(claim), [table],
    )
    assert result.status == VerificationStatus.PASS


def test_hyphenated_metric_labels_do_not_hide_real_measurements():
    table = evidence(
        rows=[
            {"team": "LEAGUE", "corner_3_efg": 0.5746},
            {"team": "BOS", "corner_3_efg": 0.6043},
        ],
        units={"corner_3_efg": "fraction_0_1"},
    )
    claim = Claim(
        text="Boston's 3-point efficiency was 61.00%.",
        kind="observed", evidence_ids=[table.evidence_id],
    )
    result = verify_mechanical(
        TaskSpec(goal="Boston shot zones", mode="quick", deliverable="answer"),
        report(claim), [table],
    )
    assert result.status == VerificationStatus.REPAIR
    assert any("61.00%" in reason for reason in result.claim_results[0].reasons)


def test_named_entity_values_can_span_multiple_population_envelopes():
    totals = evidence(
        evidence_id="totals",
        rows=[
            {"TEAM": "Atlanta Hawks", "AST": 2462, "GP": 82, "PER_GAME": 30.0},
            {"TEAM": "Boston Celtics", "AST": 2021, "GP": 82, "PER_GAME": 24.6},
        ],
    )
    standings = evidence(
        evidence_id="standings",
        rows=[
            {"team": "Atlanta Hawks", "WINS": 42, "LOSSES": 40},
            {"team": "Boston Celtics", "WINS": 56, "LOSSES": 26},
        ],
    )
    claim = Claim(
        text="Atlanta Hawks led with 2462 assists in 82 games, or 30.0 per game.",
        kind="observed", evidence_ids=["totals", "standings"],
    )
    result = verify_mechanical(
        TaskSpec(goal="team assist leader", mode="quick", deliverable="answer"),
        report(claim), [totals, standings],
    )
    assert not any("named entity row" in reason
                   for reason in result.claim_results[0].reasons)


def test_named_entity_values_still_reject_adjacent_rows_across_envelopes():
    totals = evidence(
        evidence_id="totals",
        rows=[
            {"TEAM": "Atlanta Hawks", "AST": 2462},
            {"TEAM": "Boston Celtics", "AST": 2021},
        ],
    )
    standings = evidence(
        evidence_id="standings",
        rows=[
            {"team": "Atlanta Hawks", "WINS": 42},
            {"team": "Boston Celtics", "WINS": 56},
        ],
    )
    claim = Claim(
        text="Atlanta Hawks had 2021 assists and 56 wins.",
        kind="observed", evidence_ids=["totals", "standings"],
    )
    result = verify_mechanical(
        TaskSpec(goal="Atlanta totals", mode="quick", deliverable="answer"),
        report(claim), [totals, standings],
    )
    assert any("named entity rows" in reason
               for reason in result.claim_results[0].reasons)


def test_draft_declared_calculation_is_recomputed_by_assembly_verifier():
    import asyncio
    from v2.runtime.assembly import MechanicalVerifier
    ev = evidence(rows=[{"player": "A", "ppg": 21.0}, {"player": "B", "ppg": 18.5}])
    draft = DraftReport(sections=["Gap"], calculations=[{
        "calculation_id": "ppg_gap", "operation": "subtract",
        "inputs": [{"evidence_id": ev.evidence_id, "path": "rows[0].ppg"},
                   {"evidence_id": ev.evidence_id, "path": "rows[1].ppg"}],
        "result": "2.5", "unit": "points_per_game",
    }], claims=[Claim(text="A leads B by 2.5 points per game.", kind="derived",
                     evidence_ids=[ev.evidence_id], calculation_id="ppg_gap")])
    result = asyncio.run(MechanicalVerifier().verify(task(), draft, {ev.evidence_id: ev}))
    assert result.status == VerificationStatus.PASS


def test_best_record_claim_requires_complete_wins_losses_record():
    from datetime import UTC, datetime
    from v2.contracts import Claim, DraftReport, EvidenceEnvelope, TaskSpec
    from v2.runtime.verifier import verify_mechanical

    evidence = EvidenceEnvelope(
        evidence_id="standings", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), qualification="All NBA teams",
        coverage="Full standings table", rows=[{
            "team": "Oklahoma City Thunder", "wins": 64, "losses": 18,
            "win_pct": 78.0, "RANK": 1,
        }],
    )
    task = TaskSpec(goal="best record", mode="quick", deliverable="answer")
    incomplete = DraftReport(sections=["Record"], claims=[Claim(
        text="Oklahoma City Thunder had the best record with 64 wins and a 78.0% win percentage.",
        kind="observed", evidence_ids=["standings"],
    )])
    rejected = verify_mechanical(task, incomplete, [evidence])
    assert rejected.status == "repair"
    assert "complete wins-losses record" in rejected.claim_results[0].reasons[-1]

    complete = DraftReport(sections=["Record"], claims=[Claim(
        text="Oklahoma City Thunder had the best record at 64-18 with a 78.0% win percentage.",
        kind="observed", evidence_ids=["standings"],
    )])
    accepted = verify_mechanical(task, complete, [evidence])
    assert accepted.status == "pass"

def test_count_metrics_use_natural_metric_nouns() -> None:
    from datetime import UTC, datetime
    from v2.contracts import Claim, DraftReport, EvidenceEnvelope, TaskSpec
    from v2.runtime.verifier import verify_mechanical

    evidence = EvidenceEnvelope(
        evidence_id="standings", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), units={"WINS": "count", "LOSSES": "count"},
        qualification="All NBA teams", coverage="Full standings table",
        rows=[{"team": "Oklahoma City Thunder", "WINS": 64, "LOSSES": 18,
               "LeagueRank": 1}],
    )
    draft = DraftReport(sections=["Record"], claims=[Claim(
        text="Oklahoma City Thunder had the best record at 64-18.",
        kind="observed", evidence_ids=["standings"],
    )])
    assert verify_mechanical(TaskSpec(
        goal="best record", mode="quick", deliverable="answer"),
        draft, [evidence]).status == "pass"

def test_player_evidence_does_not_conflict_with_team_only_task_entity():
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    task = TaskSpec(goal="top team contributor", mode="quick", deliverable="answer",
                    entities=[{"id": "1610612760", "type": "team",
                               "display_name": "Oklahoma City Thunder"}])
    ev = EvidenceEnvelope(
        evidence_id="player", capability="player_report", source="fixture",
        observed_at=datetime.now(UTC),
        entities=[{"id": "1628983", "type": "player",
                   "display_name": "Shai Gilgeous-Alexander"}],
        rows={"player": "Shai Gilgeous-Alexander", "PPG": 31.1})
    claim = Claim(text="Shai Gilgeous-Alexander averaged 31.1 points per game.",
                  kind="observed", evidence_ids=["player"])
    result = verify_mechanical(task, DraftReport(sections=["Answer"], claims=[claim]), [ev])
    assert result.status == "pass"

def test_record_deliverable_requires_explicit_wins_losses_rendering():
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    ev = EvidenceEnvelope(
        evidence_id="standings", capability="standings", source="fixture",
        observed_at=datetime.now(UTC), qualification="All NBA teams",
        coverage="Full standings", rows=[{
            "team":"Oklahoma City Thunder", "WINS":64, "LOSSES":18,
            "WinPCT":.78, "LeagueRank":1}])
    task = TaskSpec(goal="best record", mode="quick", deliverable="team and record")
    incomplete = DraftReport(sections=["Record"], claims=[Claim(
        text="Oklahoma City led with 64 wins and a .780 win percentage.",
        kind="observed", evidence_ids=["standings"])])
    result = verify_mechanical(task, incomplete, [ev])
    assert result.status == "repair"
    assert "wins-losses record in W-L form" in result.repair_instructions[-1]
    complete = incomplete.model_copy(update={"claims":[Claim(
        text="Oklahoma City had the best record at 64-18.", kind="observed",
        evidence_ids=["standings"])]})
    assert verify_mechanical(task, complete, [ev]).status == "pass"

def test_requested_supported_efficiency_metric_cannot_be_omitted():
    from v2.contracts import EvidenceEnvelope
    ev = EvidenceEnvelope(
        evidence_id="player", capability="player_report", source="fixture",
        observed_at=datetime.now(UTC), rows={"season_line": {
            "PLAYER": "Luka Doncic", "PPG": 33.9, "RPG": 9.2,
            "APG": 9.8, "TS_PCT": .617,
        }})
    requested = TaskSpec(goal="compare performance", mode="deep_dive",
                         deliverable="key metrics and efficiency")
    omitted = DraftReport(sections=["Performance"], claims=[Claim(
        text="Luka averaged 33.9 points, 9.2 rebounds and 9.8 assists.",
        kind="observed", evidence_ids=["player"])])
    result = verify_mechanical(requested, omitted, [ev])
    assert result.status == "repair"
    assert "requested ts metric" in result.repair_instructions[-1]
    included = omitted.model_copy(update={"claims": [Claim(
        text="Luka averaged 33.9 points on 61.7% true shooting.",
        kind="observed", evidence_ids=["player"])]})
    assert verify_mechanical(requested, included, [ev]).status == "pass"

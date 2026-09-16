from datetime import date, datetime
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
        observed_at=datetime(2026, 4, 15, 12), season="2025-26", as_of=date(2026, 4, 15),
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
        observed_at=datetime(2026, 4, 15), season="2025-26", entities=raw.entities,
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
        [evidence(as_of=None, observed_at=datetime(2026, 4, 15, 12))],
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
        observed_at=datetime(2026, 4, 15), season="2025-26",
        rows={"player": "SGA", "ppg": 31.1})
    luka = EvidenceEnvelope(
        evidence_id="luka", capability="player_report",
        source="fallback:basketball-reference",
        observed_at=datetime(2026, 4, 15), season="2025-26",
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
        observed_at=datetime(2026, 4, 15),
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

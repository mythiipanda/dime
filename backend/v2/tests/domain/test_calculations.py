from datetime import UTC, datetime
from decimal import Decimal

import pytest

from v2.contracts import EvidenceEnvelope
from v2.domain.calculations import Calculation, CalculationInput, CalculationOperation, recompute, validate_calculation
from v2.domain.evidence import EvidenceIndex


def index():
    return EvidenceIndex([EvidenceEnvelope(evidence_id="box", capability="box", source="fixture",
        observed_at=datetime(2026, 9, 14, tzinfo=UTC), rows=[{"PTS": 30, "FGA": 20}, {"PTS": 20, "FGA": 25}])])


def ref(path):
    return CalculationInput(evidence_id="box", path=path)


def test_recomputes_percent_and_dense_rank():
    pct = Calculation(calculation_id="pct", operation=CalculationOperation.PERCENT,
        inputs=[ref("rows[0].PTS"), ref("rows[0].FGA")], result=Decimal("150"), unit="percent")
    rank = Calculation(calculation_id="rank", operation=CalculationOperation.RANK_DESC,
        inputs=[ref("rows[0].PTS"), ref("rows[1].PTS")], subject_input=0, result=Decimal("1"))
    assert recompute(pct, index()) == Decimal("150")
    assert recompute(rank, index()) == Decimal("1")
    assert validate_calculation(pct, index()) is None


def test_wrong_calculation_is_reported():
    calculation = Calculation(calculation_id="mean", operation=CalculationOperation.MEAN,
        inputs=[ref("rows[0].PTS"), ref("rows[1].PTS")], result=Decimal("26"))
    assert "computed 25" in validate_calculation(calculation, index())


def test_missing_input_fails_closed():
    calculation = Calculation(calculation_id="sum", operation=CalculationOperation.ADD,
        inputs=[ref("rows[0].MISSING")], result=Decimal("1"))
    with pytest.raises(ValueError, match="missing or non-numeric"):
        recompute(calculation, index())


@pytest.mark.parametrize("payload,error", [
    ({"calculation_id": "sum", "operation": "add", "inputs": [
        {"evidence_id": "box", "path": "rows[0].PTS"},
        {"evidence_id": "box", "path": "rows[0].PTS"},
    ], "result": 60}, "must not contain duplicates"),
    ({"calculation_id": "sum", "operation": "add", "inputs": [
        {"evidence_id": "box", "path": "rows[0].PTS"},
    ], "result": 30, "invented": True}, "Extra inputs are not permitted"),
])
def test_calculation_contract_rejects_ambiguous_inputs(payload, error):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match=error):
        Calculation.model_validate(payload)


@pytest.mark.parametrize("schema,payload,error", [
    (CalculationInput, {"evidence_id": " ", "path": "rows.value"}, "identity"),
    (CalculationInput, {"evidence_id": "ev", "path": " "}, "identity"),
    (Calculation, {"calculation_id": " ", "operation": "add",
                   "inputs": [{"evidence_id": "box", "path": "rows[0].PTS"}],
                   "result": 30}, "calculation id"),
    (Calculation, {"calculation_id": "sum", "operation": "add",
                   "inputs": [{"evidence_id": "box", "path": "rows[0].PTS"}],
                   "result": "NaN"}, "finite number"),
])
def test_calculation_contract_rejects_blank_identity_and_nonfinite_result(schema, payload, error):
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match=error):
        schema.model_validate(payload)


def test_non_rank_calculation_rejects_subject_input() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="only for rank calculations"):
        Calculation(
            calculation_id="sum", operation="add",
            inputs=[ref("rows[0].PTS")], subject_input=0, result=Decimal("30"),
        )


@pytest.mark.parametrize("value", [True, "0", 0.0])
def test_rank_subject_index_is_a_strict_integer(value) -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Calculation(
            calculation_id="rank", operation="rank_desc",
            inputs=[ref("rows[0].PTS")], subject_input=value,
            result=Decimal("1"),
        )


def test_calculation_evaluation_revalidates_copied_contract() -> None:
    from pydantic import ValidationError
    valid = Calculation(calculation_id="sum", operation="add",
                        inputs=[ref("rows[0].PTS")], result=Decimal("30"))
    invalid = valid.model_copy(update={"result": Decimal("NaN")})
    with pytest.raises(ValidationError, match="finite"):
        recompute(invalid, index())


@pytest.mark.parametrize("tolerance", [Decimal("NaN"), Decimal("-0.1")])
def test_calculation_validation_rejects_invalid_tolerance(tolerance) -> None:
    valid = Calculation(calculation_id="sum", operation="add",
                        inputs=[ref("rows[0].PTS")], result=Decimal("30"))
    with pytest.raises(ValueError, match="tolerance must be finite and non-negative"):
        validate_calculation(valid, index(), tolerance)


def test_calculation_input_list_has_a_hard_limit() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="at most 256 items"):
        Calculation(
            calculation_id="sum", operation="add",
            inputs=[CalculationInput(evidence_id="box", path=f"rows.{index}")
                    for index in range(257)],
            result=Decimal("1"),
        )


def test_calculation_identity_text_has_hard_limits() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="at most 1000 characters"):
        CalculationInput(evidence_id="ev", path="x" * 1001)

def test_mean_expands_canonical_list_selector_and_preserves_zero():
    evidence = EvidenceIndex([EvidenceEnvelope(
        evidence_id="logs", capability="game_logs", source="fixture",
        observed_at=datetime.now(UTC),
        rows={"matches":[{"pts":10},{"pts":0},{"pts":20}]})])
    calc = Calculation(calculation_id="avg", operation="mean",
        inputs=[{"evidence_id":"logs","path":"rows.matches[].pts"}],
        result=10)
    assert recompute(calc, evidence) == Decimal("10")

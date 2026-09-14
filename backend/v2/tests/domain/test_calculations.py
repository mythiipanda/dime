from datetime import datetime
from decimal import Decimal

import pytest

from v2.contracts import EvidenceEnvelope
from v2.domain.calculations import Calculation, CalculationInput, CalculationOperation, recompute, validate_calculation
from v2.domain.evidence import EvidenceIndex


def index():
    return EvidenceIndex([EvidenceEnvelope(evidence_id="box", capability="box", source="fixture",
        observed_at=datetime(2026, 9, 14), rows=[{"PTS": 30, "FGA": 20}, {"PTS": 20, "FGA": 25}])])


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

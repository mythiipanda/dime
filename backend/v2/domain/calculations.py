from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from v2.domain.evidence import EvidenceIndex, decimal_value


class CalculationOperation(StrEnum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    PERCENT = "percent"
    MEAN = "mean"
    RANK_DESC = "rank_desc"
    RANK_ASC = "rank_asc"


class CalculationInput(BaseModel):
    evidence_id: str
    path: str


class Calculation(BaseModel):
    calculation_id: str
    operation: CalculationOperation
    inputs: list[CalculationInput]
    result: Decimal
    unit: str | None = None
    subject_input: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_shape(self) -> "Calculation":
        if not self.inputs:
            raise ValueError("calculations require inputs")
        if self.operation in (CalculationOperation.SUBTRACT,
                              CalculationOperation.DIVIDE,
                              CalculationOperation.PERCENT):
            if len(self.inputs) != 2:
                raise ValueError(f"{self.operation} requires two inputs")
        if self.operation in (CalculationOperation.RANK_ASC,
                              CalculationOperation.RANK_DESC):
            if self.subject_input is None or self.subject_input >= len(self.inputs):
                raise ValueError("rank calculations require a valid subject input")
        return self


def _input_values(calculation: Calculation,
                  evidence: EvidenceIndex) -> list[Decimal]:
    indexed = {
        (value.evidence_id, value.path): value.value
        for value in evidence.values(input_.evidence_id
                                     for input_ in calculation.inputs)
    }
    values: list[Decimal] = []
    for input_ in calculation.inputs:
        raw = indexed.get((input_.evidence_id, input_.path))
        value = decimal_value(raw)
        if value is None:
            raise ValueError(
                f"calculation input is missing or non-numeric: "
                f"{input_.evidence_id}:{input_.path}"
            )
        values.append(value)
    return values


def recompute(calculation: Calculation, evidence: EvidenceIndex) -> Decimal:
    values = _input_values(calculation, evidence)
    try:
        if calculation.operation == CalculationOperation.ADD:
            return sum(values, Decimal(0))
        if calculation.operation == CalculationOperation.SUBTRACT:
            return values[0] - values[1]
        if calculation.operation == CalculationOperation.MULTIPLY:
            result = Decimal(1)
            for value in values:
                result *= value
            return result
        if calculation.operation == CalculationOperation.DIVIDE:
            return values[0] / values[1]
        if calculation.operation == CalculationOperation.PERCENT:
            return values[0] / values[1] * 100
        if calculation.operation == CalculationOperation.MEAN:
            return sum(values, Decimal(0)) / len(values)
        reverse = calculation.operation == CalculationOperation.RANK_DESC
        subject = values[calculation.subject_input or 0]
        ordered = sorted(set(values), reverse=reverse)
        return Decimal(ordered.index(subject) + 1)
    except (DivisionByZero, InvalidOperation, ZeroDivisionError) as exc:
        raise ValueError(f"calculation cannot be evaluated: {exc}") from exc


def validate_calculation(calculation: Calculation, evidence: EvidenceIndex,
                         tolerance: Decimal = Decimal("0.000001")) -> str | None:
    actual = recompute(calculation, evidence)
    if abs(actual - calculation.result) > tolerance:
        return (
            f"calculation {calculation.calculation_id} does not recompute "
            f"(declared {calculation.result}, computed {actual})"
        )
    return None

"""Optional TypeSafe decision helpers. The runtime does not depend on this module."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

UNRESOLVED = "unresolved"


class DecisionClient(Protocol):
    def evaluate(self, state: Mapping[str, Any], questions: Mapping[str, Any]) -> Any: ...


@dataclass(frozen=True)
class DecisionThresholds:
    evidence: float = 0.50
    eval_judgment: float = 0.50
    model_route: float = 0.50
    tool: float = 0.50
    argument: float = 0.50
    satisfaction: float = 0.30

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} threshold must be numeric")
            if not 0 <= value <= 1:
                raise ValueError(f"{name} threshold must be between 0 and 1")


@dataclass(frozen=True)
class Decision:
    value: str
    confidence: float
    probabilities: Mapping[str, float]


@dataclass(frozen=True)
class ToolDecision:
    tool: Decision
    arguments: Mapping[str, Decision]


class TypeSafeClientAdapter:
    """Load the optional SDK only when an enabled caller constructs the adapter."""

    def __init__(
        self, *, api_key: str, model: str = "jev-1.13.0", timeout: float = 2.0
    ) -> None:
        if not api_key.strip():
            raise ValueError("TypeSafe API key is required")
        try:
            from typesafe_sdk import TypeSafeClient
        except ImportError as exc:
            raise RuntimeError(
                "Install typesafe-sdk from the TypeSafe private package index to enable Jev"
            ) from exc
        self._client = TypeSafeClient(api_key=api_key, model=model, timeout=timeout)

    def evaluate(self, state: Mapping[str, Any], questions: Mapping[str, Any]) -> Any:
        return self._client.system_one(state=dict(state), questions=dict(questions))

    def close(self) -> None:
        self._client.close()


class DecisionAuditLog:
    """Append sanitized read-only decision outcomes to a local shadow log."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def __call__(self, kind: str, data: Mapping[str, Any]) -> None:
        record = {"kind": kind, **dict(data)}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")


def build_optional_jev_layer(
    *, enabled: bool, api_key: str, model: str = "jev-1.13.0",
    timeout: float = 2.0, shadow_log: str | Path | None = None,
    thresholds: DecisionThresholds | None = None,
) -> "JevDecisionLayer | None":
    """Build the isolated layer only when the experimental flag is enabled."""
    if not enabled:
        return None
    try:
        from typesafe_sdk import Choice, Noul
    except ImportError as exc:
        raise RuntimeError(
            "Install typesafe-sdk from the TypeSafe private package index to enable Jev"
        ) from exc
    audit = DecisionAuditLog(shadow_log) if shadow_log else None
    return JevDecisionLayer(
        TypeSafeClientAdapter(api_key=api_key, model=model, timeout=timeout),
        choice=Choice,
        noul=Noul,
        thresholds=thresholds,
        audit=audit,
    )


class JevDecisionLayer:
    """Make bounded decisions over candidates already resolved by Dime code."""

    def __init__(
        self,
        client: DecisionClient,
        *,
        choice: Callable[..., Any],
        noul: Callable[..., Any],
        thresholds: DecisionThresholds | None = None,
        audit: Callable[[str, Mapping[str, Any]], None] | None = None,
    ) -> None:
        self._client = client
        self._choice = choice
        self._noul = noul
        self._thresholds = thresholds or DecisionThresholds()
        self._audit = audit or (lambda _kind, _data: None)

    def filter_evidence(
        self, *, goal: str, candidates: Mapping[str, Mapping[str, Any]]
    ) -> tuple[str, ...]:
        questions = {
            evidence_id: self._noul(
                instructions=(
                    "Is this evidence directly relevant to the stated analytical goal "
                    "within its declared coverage?"
                )
            )
            for evidence_id in candidates
        }
        response = self._try_call(
            "evidence_filter", {"goal": goal, "evidence": candidates}, questions)
        if response is None:
            return tuple(candidates)
        answers = response.answers
        return tuple(
            evidence_id for evidence_id in candidates
            if float(answers[evidence_id].noul) >= self._thresholds.evidence
        )

    def judge_eval(
        self, *, expectation: Mapping[str, Any], result: Mapping[str, Any]
    ) -> Decision:
        answer = self._choice_answer(
            "eval_judgment",
            {"expectation": expectation, "result": result},
            "Which label describes the result against the expectation?",
            {
                "pass": "The result satisfies the expectation.",
                "fail": "The result violates the expectation.",
                "partial": "The result satisfies only part of the expectation.",
                "contradictory": "The result conflicts with the expectation or itself.",
                UNRESOLVED: "The supplied data cannot establish a label.",
            },
        )
        if answer is None:
            return Decision(UNRESOLVED, 0.0, {})
        if answer.value == UNRESOLVED or answer.confidence < self._thresholds.eval_judgment:
            return Decision(UNRESOLVED, answer.confidence, answer.probabilities)
        return answer

    def route_model(
        self, *, stage: Mapping[str, Any], routes: Mapping[str, str], strongest: str
    ) -> Decision:
        if strongest not in routes:
            raise ValueError("strongest route must be an enumerated candidate")
        answer = self._choice_answer(
            "model_route", stage,
            "Which configured model route fits this bounded stage?",
            {**routes, UNRESOLVED: "No route is clearly appropriate."},
        )
        if answer is None:
            return Decision(strongest, 0.0, {})
        if answer.value == UNRESOLVED or answer.confidence < self._thresholds.model_route:
            return Decision(strongest, answer.confidence, answer.probabilities)
        return answer

    def choose_tool(
        self,
        *,
        state: Mapping[str, Any],
        tools: Mapping[str, str],
        argument_candidates: Callable[
            [str], Mapping[str, tuple[str, Mapping[str, str]]]
        ],
    ) -> ToolDecision | None:
        if not tools or UNRESOLVED in tools:
            raise ValueError("tools must be non-empty and cannot declare unresolved")
        tool = self._choice_answer(
            "tool_choice", state,
            "Which valid evidence tool performs this resolved step?",
            {**tools, UNRESOLVED: "No tool is valid for this resolved step."},
        )
        if (tool is None or tool.value == UNRESOLVED
                or tool.confidence < self._thresholds.tool):
            return None
        fields = argument_candidates(tool.value)
        if any(not candidates or UNRESOLVED in candidates
               for _instructions, candidates in fields.values()):
            raise ValueError(
                "argument candidates must be non-empty and cannot declare unresolved")
        questions = {
            name: self._choice(instructions=instructions, criteria={
                **candidates, UNRESOLVED: "No candidate is established for this role."
            })
            for name, (instructions, candidates) in fields.items()
        }
        response = self._try_call("tool_arguments", state, questions)
        if response is None:
            return None
        arguments: dict[str, Decision] = {}
        for name in fields:
            answer = response.answers[name]
            decision = Decision(
                answer.choice, float(answer.confidence), answer.probabilities)
            if (decision.value == UNRESOLVED
                    or decision.confidence < self._thresholds.argument):
                return None
            arguments[name] = decision
        entity_roles = {
            name: decision.value for name, decision in arguments.items()
            if any(token in name.lower() for token in (
                "player", "subject", "outgoing", "incoming", "primary",
                "comparison",
            ))
        }
        if len(entity_roles.values()) != len(set(entity_roles.values())):
            return None
        return ToolDecision(tool=tool, arguments=arguments)

    def result_satisfied(
        self, *, step: Mapping[str, Any], result: Mapping[str, Any]
    ) -> bool:
        response = self._try_call("result_satisfaction", {
            "step": step, "typed_result": result,
        }, {"satisfied": self._noul(instructions=(
            "Did this typed result completely satisfy this one evidence step, "
            "including entities, required fields, season, and vintage?"
        ))})
        if response is None:
            return True
        return float(response.answers["satisfied"].noul) >= self._thresholds.satisfaction

    def _choice_answer(
        self, kind: str, state: Mapping[str, Any], instructions: str,
        criteria: Mapping[str, str],
    ) -> Decision | None:
        response = self._try_call(kind, state, {
            "answer": self._choice(instructions=instructions, criteria=criteria)
        })
        if response is None:
            return None
        answer = response.answers["answer"]
        return Decision(answer.choice, float(answer.confidence), answer.probabilities)

    def _try_call(
        self, kind: str, state: Mapping[str, Any], questions: Mapping[str, Any]
    ) -> Any | None:
        try:
            response = self._client.evaluate(state, questions)
        except Exception as exc:
            self._audit(kind, {"status": "failed", "error": type(exc).__name__})
            return None
        self._audit(kind, {"status": "ok"})
        return response

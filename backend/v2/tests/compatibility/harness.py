from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from v2.contracts import EvidenceEnvelope, VerificationReport, VerificationStatus
from v2.runtime.ledger import LedgerEntry
from v2.runtime.projections import admitted_evidence, tool_attempts


@dataclass(frozen=True)
class RevisionFingerprint:
    revision: str
    executable_sha256: str

    @classmethod
    def current(cls, root: Path) -> "RevisionFingerprint":
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        backend = root / "backend" if (root / "backend").is_dir() else root
        digest = hashlib.sha256()
        for directory in (backend / "app", backend / "v2"):
            for path in sorted(directory.rglob("*")):
                if path.is_file() and path.suffix in {".py", ".md"}:
                    digest.update(path.relative_to(backend).as_posix().encode())
                    digest.update(b"\0")
                    digest.update(path.read_bytes())
                    digest.update(b"\0")
        return cls(revision, digest.hexdigest())


@dataclass(frozen=True)
class TurnTrace:
    seconds: float
    tool_calls: int
    evidence: tuple[EvidenceEnvelope, ...]
    tools: tuple[dict[str, Any], ...]
    report: VerificationReport | None = None
    text: str = ""

    @classmethod
    def from_ledger(
        cls,
        entries: Iterable[LedgerEntry],
        *,
        seconds: float,
        report: VerificationReport | None = None,
        text: str = "",
    ) -> "TurnTrace":
        entries = tuple(entries)
        tools = tuple(tool_attempts(entries))
        return cls(
            seconds=seconds,
            tool_calls=len(tools),
            evidence=tuple(admitted_evidence(entries)),
            tools=tools,
            report=report,
            text=text,
        )


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def load_pack(path: Path) -> dict[str, Any]:
    pack = json.loads(path.read_text())
    scenarios = pack.get("scenarios", [])
    if len(scenarios) != 35:
        raise ValueError(f"compatibility pack must contain 35 scenarios, got {len(scenarios)}")
    ids = [scenario["id"] for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("compatibility scenario ids must be unique")
    banned = pack.get("banned_everywhere", [])
    for scenario in scenarios:
        scenario["_banned_everywhere"] = banned
    return pack


def _walk(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
    elif value is not None:
        yield str(value)


def _contains(values: Iterable[str], needle: str) -> bool:
    folded = needle.casefold().replace(",", "")
    return any(folded in value.casefold().replace(",", "") for value in values)


def grade_scenario(scenario: dict[str, Any], turns: list[TurnTrace]) -> ScenarioResult:
    failures: list[str] = []
    expected_turns = len(scenario["chain"])
    if len(turns) != expected_turns:
        return ScenarioResult(scenario["id"], (f"expected {expected_turns} turns, got {len(turns)}",))
    expectations = scenario.get("expect_turns") or [scenario.get("expect", {})]
    if len(expectations) != expected_turns:
        return ScenarioResult(
            scenario["id"],
            (f"expected {expected_turns} turn expectations, got {len(expectations)}",),
        )
    banned = [*scenario.get("_banned_everywhere", []),
              *scenario.get("banned", [])]
    for index, (turn, expected) in enumerate(zip(turns, expectations), 1):
        text = turn.text.casefold()
        for needle in expected.get("contains", []):
            if needle.casefold() not in text:
                failures.append(f"T{index}: missing expected text: {needle!r}")
        for alternatives in expected.get("contains_any", []):
            if not any(needle.casefold() in text for needle in alternatives):
                failures.append(f"T{index}: missing any of: {alternatives!r}")
        for needle in [*expected.get("not_contains", []), *banned]:
            if needle.casefold() in text:
                failures.append(f"T{index}: contains banned text: {needle!r}")

    budget = scenario.get("budget") or {}
    max_per_turn = budget.get("max_seconds_per_turn")
    for index, turn in enumerate(turns, 1):
        if max_per_turn is not None and turn.seconds > max_per_turn:
            failures.append(f"T{index}: latency {turn.seconds:.1f}s > {max_per_turn}s budget")
        if turn.report is None:
            failures.append(f"T{index}: missing verification report")
        elif turn.report.status != VerificationStatus.PASS:
            failures.append(
                f"T{index}: verifier status is {turn.report.status.value}")
    seconds = sum(turn.seconds for turn in turns)
    calls = sum(turn.tool_calls for turn in turns)
    if budget.get("max_seconds") is not None and seconds > budget["max_seconds"]:
        failures.append(f"latency {seconds:.1f}s > {budget['max_seconds']}s budget")
    if budget.get("max_tool_calls") is not None and calls > budget["max_tool_calls"]:
        failures.append(f"{calls} tool calls > {budget['max_tool_calls']} budget")

    requirement = scenario.get("evidence_requirement")
    if requirement:
        evidence = [item for turn in turns for item in turn.evidence]
        capabilities = {item.capability.casefold() for item in evidence}
        alternatives = {item.casefold() for item in requirement.get("any_capability", [])}
        if alternatives and not capabilities.intersection(alternatives):
            failures.append(f"missing equivalent evidence capability: {sorted(alternatives)}")
        if requirement.get("max_evidence") is not None and len(evidence) > requirement["max_evidence"]:
            failures.append(f"{len(evidence)} evidence calls > {requirement['max_evidence']} budget")
        values = [value for item in evidence for value in _walk(item.rows)]
        for needle in requirement.get("required_values", []):
            if not _contains(values, needle):
                failures.append(f"evidence missing value: {needle!r}")
        qualification = [item.qualification or "" for item in evidence]
        for needle in requirement.get("qualification_contains", []):
            if not _contains(qualification, needle):
                failures.append(f"qualification missing: {needle!r}")
        definitions = [value for item in evidence for value in item.metric_definitions.values()]
        for needle in requirement.get("metric_definitions_contain", []):
            if not _contains(definitions, needle):
                failures.append(f"metric definition missing: {needle!r}")
        warnings = [warning for item in evidence for warning in item.warnings]
        for needle in requirement.get("warnings_contain", []):
            if not _contains(warnings, needle):
                failures.append(f"warning missing: {needle!r}")
    return ScenarioResult(scenario["id"], tuple(failures))


def assert_server_revision(base_url: str, expected: RevisionFingerprint) -> None:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/revision", timeout=5) as response:
        observed = json.load(response)
    actual = RevisionFingerprint(observed["revision"], observed["executable_sha256"])
    if actual != expected:
        raise RuntimeError(f"server revision mismatch: expected {expected}, observed {actual}")


class ShadowRunner:
    def __init__(self, primary: Callable[[dict[str, Any]], list[TurnTrace]],
                 shadow: Callable[[dict[str, Any]], list[TurnTrace]]) -> None:
        self.primary = primary
        self.shadow = shadow

    def run(self, scenario: dict[str, Any]) -> dict[str, ScenarioResult]:
        return {
            "primary": grade_scenario(scenario, self.primary(scenario)),
            "shadow": grade_scenario(scenario, self.shadow(scenario)),
        }


class OwnedServer:
    def __init__(self, command: list[str], base_url: str, expected: RevisionFingerprint,
                 cwd: Path, startup_seconds: float = 10.0) -> None:
        self.command = command
        self.base_url = base_url
        self.expected = expected
        self.cwd = cwd
        self.startup_seconds = startup_seconds
        self.process: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> "OwnedServer":
        self.process = subprocess.Popen(self.command, cwd=self.cwd)
        deadline = time.monotonic() + self.startup_seconds
        while True:
            if self.process.poll() is not None:
                raise RuntimeError(f"owned server exited with {self.process.returncode}")
            try:
                assert_server_revision(self.base_url, self.expected)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("owned server did not become ready")
                time.sleep(0.05)

    def __exit__(self, *_: object) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)

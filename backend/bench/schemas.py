"""Benchmark data shapes. Plain dataclasses, JSONL-serializable via to_dict."""

from dataclasses import asdict, dataclass, field


@dataclass
class Task:
    task_id: str
    family: str
    question: str
    entities: list[str] = field(default_factory=list)
    gold_tool_families: list[str] = field(default_factory=list)
    timeout_s: int = 180
    seed: int = 7


@dataclass
class GroundTruth:
    task_id: str
    facts: dict = field(default_factory=dict)
    computed_at: str = ""
    source: str = ""


@dataclass
class RunResult:
    task_id: str
    ok: bool
    error: str = ""
    tool_calls: list = field(default_factory=list)
    final_answer: str = ""
    latency_ms: int = 0
    ttft_ms: int = 0
    scores: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

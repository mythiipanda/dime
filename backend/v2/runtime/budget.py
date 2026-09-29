from __future__ import annotations
from contextvars import ContextVar



RUN_MODEL_DEADLINE: ContextVar[float | None] = ContextVar(
    "v2_run_model_deadline", default=None)

from __future__ import annotations
from contextvars import ContextVar

# Absolute monotonic deadline for model work. A request task owns its value;
# child coroutines inherit it without mutable global cross-talk.
RUN_MODEL_DEADLINE: ContextVar[float | None] = ContextVar(
    "v2_run_model_deadline", default=None)

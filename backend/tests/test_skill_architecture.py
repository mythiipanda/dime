"""Skill-file architecture: defensive routing regression tests.

1. The keyword table routes defensive questions to the defensive_analysis
   skill (no hardcoded per-question pins).
2. The bounded ReAct loop exposes (question, state, max_steps).
3. The "Defensive leaderboard pin" hardcoded routing anti-pattern is gone
   from app/graph.py.
4. The termination gate (guard) machinery is still intact — we removed
   routing, not guards.
"""

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import graph as graph_module  # noqa: E402
from app.graph import match_skills, react_loop  # noqa: E402


def test_defensive_skill_loaded():
    assert "defensive_analysis" in match_skills("best defensive players?")


def test_react_loop_exists():
    assert callable(react_loop)
    sig = inspect.signature(react_loop)
    params = list(sig.parameters)
    assert params[:3] == ["question", "state", "max_steps"]


def test_no_hardcoded_defensive_pin():
    source = inspect.getsource(graph_module)
    assert "Defensive leaderboard pin" not in source


def test_termination_gate_intact():
    source = inspect.getsource(graph_module)
    verify_fns = [
        name for name in dir(graph_module)
        if (("termination" in name) or ("_verify" in name))
        and callable(getattr(graph_module, name))
    ]
    assert verify_fns, "expected at least one termination/_verify function"
    assert "termination" in source or "_verify" in source

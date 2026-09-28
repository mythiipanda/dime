"""Shared harness plumbing: result type, pytest-free test driver, sha pins."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SuiteResult:
    """One suite's outcome. Mode labels are the honesty contract."""
    name: str
    mode: str = "hermetic"  # hermetic | recorded | fallback-only |
                            # live-llm | live-judge | live-backend |
                            # live-warehouse | conditional | skipped | error
    ledger: str = "plumbing"  # plumbing (harness integrity) |
                              # signal (live answer-quality vs ground truth)
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    seconds: float = 0.0
    failures: list = field(default_factory=list)  # {id, detail, expected, got}
    notes: list = field(default_factory=list)

    def fail(self, id, detail="", expected=None, got=None):
        self.failed += 1
        self.failures.append({"id": id, "detail": detail,
                              "expected": expected, "got": got})

    def ok(self):
        self.passed += 1

    def skip(self, reason=""):
        self.skipped += 1
        if reason:
            self.notes.append(f"skipped: {reason}")


class _Skipped(Exception):
    def __init__(self, reason=""):
        super().__init__(reason)
        self.reason = reason


def _pytest_stub():
    """Minimal pytest stand-in so hermetic test modules import without pytest.

    Supports only what our hermetic modules use: pytest.skip(reason) and
    pytest.mark.skipif(cond, reason=...). Anything else raises loudly at
    import time instead of silently misbehaving.
    """
    mod = types.ModuleType("pytest")

    def skip(reason=""):
        raise _Skipped(reason)

    class _Mark:
        @staticmethod
        def skipif(cond, reason=""):
            def deco(fn):
                if cond:
                    def wrapper(*a, **k):
                        raise _Skipped(reason)
                    wrapper.__name__ = getattr(fn, "__name__", "test")
                    return wrapper
                return fn
            return deco

        def __getattr__(self, name):
            raise ImportError(
                f"pytest stub has no mark.{name}; "
                f"hermetic driver cannot run this module")

    mod.skip = skip
    mod.mark = _Mark()
    return mod


def load_test_module(path):
    """Import a test_*.py file with the pytest stub injected.

    Returns (module, error). Modules needing real pytest features fail
    loudly here; the calling suite reports a skip, never a silent pass.
    """
    path = Path(path)
    stub = _pytest_stub()
    old = sys.modules.get("pytest")
    sys.modules["pytest"] = stub
    try:
        name = "_evals_drivertest_" + path.stem
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        if old is not None:
            sys.modules["pytest"] = old
        else:
            sys.modules.pop("pytest", None)


def drive_tests(module, prefix=""):
    """Run every test_* callable in an imported test module.

    Returns (passed, failed, skipped, failures[]). Skipped tests stay
    skips; assertion failures are failures with the message attached.
    """
    passed = failed = skipped = 0
    failures = []
    for attr in sorted(dir(module)):
        if not attr.startswith("test_"):
            continue
        fn = getattr(module, attr)
        if not callable(fn):
            continue
        tid = prefix + attr
        try:
            fn()
            passed += 1
        except _Skipped as s:
            skipped += 1
            failures.append({"id": tid, "detail": f"SKIP: {s.reason}"})
        except AssertionError as exc:
            failed += 1
            failures.append({"id": tid, "detail": f"assertion: {exc}"})
        except Exception as exc:
            failed += 1
            failures.append({"id": tid,
                             "detail": f"{type(exc).__name__}: {exc}"})
    # strip SKIP entries out of failures; they are counted separately
    real_failures = [f for f in failures
                     if not f["detail"].startswith("SKIP:")]
    return passed, failed, skipped, real_failures


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_live_client():
    """Load backend/evals/live_backend.py (the SSE client) by file path.

    The module shares its name with suites/live_backend.py, so a plain
    `from live_backend import ...` resolves to whichever sys.path entry
    wins — historically the suite itself, by accident of import order.
    Load by explicit path instead; never ambiguous.
    """
    path = Path(__file__).resolve().parent.parent / "live_backend.py"
    name = "_evals_live_client"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

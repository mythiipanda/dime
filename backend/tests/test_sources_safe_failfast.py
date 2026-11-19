import importlib.util
import time
from pathlib import Path
import duckdb
import polars as pl
_base_path = Path(__file__).resolve().parent.parent.joinpath("shared").joinpath("sources").joinpath("base.py")
_spec = importlib.util.spec_from_file_location("failfast_base", str(_base_path))
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
safe = _base.safe

class FakeResponse:
    def __init__(self, code):
        self.status_code = code

class FakeHTTPError(Exception):
    def __init__(self, code):
        super().__init__(str(code))
        self.response = FakeResponse(code)

def test_catalog_exception_fails_fast(monkeypatch):
    monkeypatch.setenv("DIME_LIVE_ATTEMPTS", "3")
    calls = []
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    def boom():
        calls.append(1)
        raise duckdb.CatalogException("table missing")
    res = safe("u", "2025-26", boom)
    assert res.ok is False
    assert len(calls) == 1
    assert sleeps == []

def test_http_404_fails_fast(monkeypatch):
    monkeypatch.setenv("DIME_LIVE_ATTEMPTS", "3")
    calls = []
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    def boom():
        calls.append(1)
        raise FakeHTTPError(404)
    res = safe("u", "2025-26", boom)
    assert res.ok is False
    assert len(calls) == 1
    assert sleeps == []

def test_value_error_fails_fast(monkeypatch):
    monkeypatch.setenv("DIME_LIVE_ATTEMPTS", "3")
    calls = []
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    def boom():
        calls.append(1)
        raise ValueError("bad arg")
    res = safe("u", "2025-26", boom)
    assert res.ok is False
    assert len(calls) == 1
    assert sleeps == []

def test_transient_runtime_error_still_retried(monkeypatch):
    monkeypatch.setenv("DIME_LIVE_ATTEMPTS", "3")
    calls = []
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("transient boom")
        return pl.DataFrame({"a": [1, 2]})
    res = safe("u", "2025-26", flaky)
    assert res.ok is True
    assert len(calls) == 2
    assert len(sleeps) == 1
    assert res.frame.height == 2

def test_http_429_still_retried(monkeypatch):
    monkeypatch.setenv("DIME_LIVE_ATTEMPTS", "3")
    calls = []
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise FakeHTTPError(429)
        return pl.DataFrame({"a": [5]})
    res = safe("u", "2025-26", flaky)
    assert res.ok is True
    assert len(calls) == 2
    assert len(sleeps) == 1

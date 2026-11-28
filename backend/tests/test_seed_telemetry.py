import json

import polars as pl
import pytest

from shared.sources.base import (
    flush_seed_telemetry,
    reset_seed_telemetry,
    safe,
)


class FakeHttpError(Exception):
    def __init__(self, status):
        super().__init__(f"http {status}")
        self.response = type("R", (), {"status_code": status})()


def raise_with(exc):
    def fn():
        raise exc
    return fn


@pytest.fixture(autouse=True)
def clean_telemetry(monkeypatch, tmp_path):
    monkeypatch.setenv("DIME_LIVE_BACKOFF_S", "0")
    monkeypatch.setenv("DIME_LIVE_ATTEMPTS", "2")
    reset_seed_telemetry()
    yield tmp_path
    reset_seed_telemetry()


def test_success_records_ok(clean_telemetry):
    result = safe("src", "2025-26", lambda: pl.DataFrame({"a": [1]}))
    assert result.ok
    path = flush_seed_telemetry(clean_telemetry)
    fetch = json.loads(path.read_text())["fetches"][0]
    assert fetch["ok"] == 1
    assert fetch["empty_response"] == 0


def test_empty_frame_records_empty_response(clean_telemetry):
    result = safe("src", "2025-26", lambda: pl.DataFrame())
    assert not result.ok
    fetch = json.loads(flush_seed_telemetry(clean_telemetry).read_text())["fetches"][0]
    assert fetch["empty_response"] == 1


def test_throttle_records_throttled_with_status(clean_telemetry):
    safe("src", "2025-26", raise_with(FakeHttpError(429)))
    fetch = json.loads(flush_seed_telemetry(clean_telemetry).read_text())["fetches"][0]
    assert fetch["throttled"] == 1
    assert fetch["status_codes"] == {"429": 1}


def test_client_error_records_status_without_retry(clean_telemetry):
    calls = []
    def fn():
        calls.append(1)
        raise FakeHttpError(404)
    safe("src", "2025-26", fn)
    assert len(calls) == 1
    fetch = json.loads(flush_seed_telemetry(clean_telemetry).read_text())["fetches"][0]
    assert fetch["client_error"] == 1
    assert fetch["status_codes"] == {"404": 1}


def test_value_error_records_parse_error(clean_telemetry):
    safe("src", "2025-26", raise_with(ValueError("bad payload")))
    fetch = json.loads(flush_seed_telemetry(clean_telemetry).read_text())["fetches"][0]
    assert fetch["parse_error"] == 1


def test_connection_error_records_fetch_error(clean_telemetry):
    safe("src", "2025-26", raise_with(ConnectionError("refused")))
    fetch = json.loads(flush_seed_telemetry(clean_telemetry).read_text())["fetches"][0]
    assert fetch["fetch_error"] == 1


def test_flush_clears_records(clean_telemetry):
    safe("src", "2025-26", lambda: pl.DataFrame({"a": [1]}))
    assert flush_seed_telemetry(clean_telemetry) is not None
    assert flush_seed_telemetry(clean_telemetry) is None


def test_sources_and_seasons_bucketed_separately(clean_telemetry):
    safe("src_a", "2025-26", lambda: pl.DataFrame({"a": [1]}))
    safe("src_a", "2024-25", lambda: pl.DataFrame())
    safe("src_b", "2025-26", lambda: pl.DataFrame({"a": [1]}))
    fetches = json.loads(flush_seed_telemetry(clean_telemetry).read_text())["fetches"]
    keys = {(f["source"], f["season"]) for f in fetches}
    assert keys == {("src_a", "2025-26"), ("src_a", "2024-25"), ("src_b", "2025-26")}

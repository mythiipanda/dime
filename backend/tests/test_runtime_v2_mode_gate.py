from __future__ import annotations

import pytest

from shared.config import runtime_v2_mode


@pytest.mark.parametrize("raw", [None, "", "   ", "on", "ON", " on "])
def test_v2_routes_serve_when_the_flag_is_absent_or_blank(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv("DIME_RUNTIME_V2", raising=False)
    else:
        monkeypatch.setenv("DIME_RUNTIME_V2", raw)
    assert runtime_v2_mode() == "on"


@pytest.mark.parametrize("raw,expected", [
    ("on", "on"),
    ("ON", "on"),
    ("shadow", "shadow"),
    ("Shadow", "shadow"),
    ("off", "off"),
    ("OFF", "off"),
    ("off ", "off"),
])
def test_explicit_mode_values_survive_normalisation(monkeypatch, raw, expected):
    monkeypatch.setenv("DIME_RUNTIME_V2", raw)
    assert runtime_v2_mode() == expected


@pytest.mark.parametrize("raw", ["typo", "1", "true", "ON!"])
def test_unknown_mode_value_still_raises(monkeypatch, raw):
    monkeypatch.setenv("DIME_RUNTIME_V2", raw)
    with pytest.raises(ValueError, match="unknown DIME_RUNTIME_V2 value"):
        runtime_v2_mode()


def test_off_remains_a_reachable_kill_switch(monkeypatch):
    monkeypatch.setenv("DIME_RUNTIME_V2", "off")
    assert runtime_v2_mode() == "off"


def test_shadow_stays_distinct_from_on(monkeypatch):
    monkeypatch.delenv("DIME_RUNTIME_V2", raising=False)
    live = runtime_v2_mode()
    monkeypatch.setenv("DIME_RUNTIME_V2", "shadow")
    shadow = runtime_v2_mode()
    assert live == "on" and shadow == "shadow" and live != shadow








class _StubRuntime:
    async def run(self, *args, **kwargs):
        raise RuntimeError("stub run aborts before any publication")

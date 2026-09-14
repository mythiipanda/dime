"""Provider probes (qm model-verification pattern): a provider that
fails live gets a synthetic probe; a fresh failed probe skips it in the
fallback chain until the TTL lets it earn a retry. Hermetic: fake
clients, no network."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.providers as prov  # noqa: E402


class _FakeClient:
    def __init__(self, reply="ok", boom=False):
        self.reply = reply
        self.boom = boom

    async def ainvoke(self, messages, **kwargs):
        if self.boom:
            raise RuntimeError("quota exhausted")
        class R:
            content = "ok"
        return R()


def _reset():
    prov._probe_state.clear()


def test_probe_records_ok_and_failure(monkeypatch):
    _reset()
    monkeypatch.setattr(prov, "get_llm",
                        lambda name, model=None: _FakeClient())
    assert asyncio.run(prov.probe_provider("mistral")) is True
    assert prov.probe_verdict("mistral") is True

    monkeypatch.setattr(prov, "get_llm",
                        lambda name, model=None: _FakeClient(boom=True))
    prov._probe_state.clear()
    assert asyncio.run(prov.probe_provider("groq")) is False
    assert prov.probe_verdict("groq") is False


def test_probe_verdict_expires():
    _reset()
    prov._probe_state["groq"] = (False, time.time() - 7000)
    assert prov.probe_verdict("groq") is None


def test_fallback_skips_probe_failed_provider(monkeypatch):
    _reset()
    prov._probe_state["mistral"] = (False, time.time())
    calls = []

    def fake_get_llm(name, model=None):
        calls.append(name)
        return _FakeClient()

    monkeypatch.setattr(prov, "get_llm", fake_get_llm)
    out = asyncio.run(prov.invoke_with_fallback(
        "mistral", "m", []))
    assert out.content == "ok"
    assert "mistral" not in calls, "probe-failed primary was not skipped"
    assert calls[0] == "openrouter"

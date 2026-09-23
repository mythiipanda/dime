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
    assert calls[0] == "nvidia"


def test_invoke_exposes_accepted_provider_and_sanitized_attempts(monkeypatch):
    _reset(); calls=[]
    class C:
        def __init__(self,name): self.name=name
        async def ainvoke(self,messages,**kwargs):
            calls.append(self.name)
            if self.name=='nvidia': raise TimeoutError('secret payload must not leak')
            class R: content='ok'
            return R()
    monkeypatch.setattr(prov,'get_llm',lambda name,model=None:C(name))
    out=asyncio.run(prov.invoke_with_fallback('mistral','primary-model',[]))
    assert out.content=='ok'
    assert out.provider=='openrouter'
    assert out.model==prov.OPENROUTER_DEFAULT
    assert out.elapsed_ms>=0
    assert out.provider_attempts==({'provider':'nvidia','model':prov.NVIDIA_NIM_DEFAULT,
        'attempt_number':1,'exception_type':'TimeoutError','message_class':'timeout',
        'latency_ms':out.provider_attempts[0]['latency_ms']},)
    assert 'secret' not in str(out.provider_attempts)


def test_paid_openrouter_primary_provenance_matches_constructed_free_slug(monkeypatch):
    _reset(); seen=[]
    class C:
        async def ainvoke(self,messages,**kwargs):
            class R: content='ok'
            return R()
    def fake_get(name, model=None):
        seen.append((name,model)); return C()
    monkeypatch.setattr(prov,'get_llm',fake_get)
    out=asyncio.run(prov.invoke_with_fallback(
        'openrouter','openai/gpt-4o',[]))
    assert out.provider=='nvidia'
    assert out.model==prov.NVIDIA_NIM_DEFAULT
    assert seen[0]==('nvidia',out.model)


def test_arbitrary_mistral_primary_provenance_matches_free_limit(monkeypatch):
    _reset(); seen=[]
    class C:
        async def ainvoke(self,messages,**kwargs):
            class R: content='ok'
            return R()
    monkeypatch.setattr(prov,'get_llm',lambda n,model=None: seen.append((n,model)) or C())
    out=asyncio.run(prov.invoke_with_fallback('mistral','arbitrary-paid',[]))
    assert out.provider=='nvidia'
    assert out.model==prov.NVIDIA_NIM_DEFAULT
    assert seen[0]==('nvidia',out.model)

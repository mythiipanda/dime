from shared.config import settings
from shared import providers


def test_ordinary_groq_client_requires_activation_and_has_fixed_config(monkeypatch):
    captured=[]
    monkeypatch.setattr(settings,"groq_api_key","key")
    monkeypatch.setattr(settings,"dime_enable_groq",False)
    monkeypatch.setattr(providers,"ChatOpenAI",lambda **kw: captured.append(kw) or object())
    assert providers.get_llm("groq") is None
    monkeypatch.setattr(settings,"dime_enable_groq",True)
    with __import__("pytest").raises(providers.ProviderPolicyError):
        providers.get_llm("groq","qwen/qwen3.8-27b")
    assert providers.get_llm("groq","openai/gpt-oss-120b") is not None
    captured.clear()
    assert providers.get_llm("groq",providers.GROQ_DEFAULT) is not None
    assert captured == [{"model":"openai/gpt-oss-120b","base_url":"https://api.groq.com/openai/v1","api_key":"key","timeout":settings.llm_timeout_s,"max_retries":0,"default_headers":{"User-Agent":"dime-agent/1.0"}}]

def test_streaming_groq_uses_same_gated_fixed_client(monkeypatch):
    import asyncio
    class Chunk: content="ok"
    class Client:
        async def astream(self,*a,**k):
            yield Chunk()
    monkeypatch.setattr(settings,"dime_enable_groq",True)
    monkeypatch.setattr(settings,"groq_api_key","key")
    monkeypatch.setattr(providers,"get_llm",lambda name,model=None: Client() if name=="groq" else None)
    monkeypatch.setattr(providers,"fallback_order",lambda primary:["groq"])
    async def collect():
        return [x async for x in providers.astream_with_fallback("groq","openai/gpt-oss-20b",[])]
    assert asyncio.run(collect()) == [{"provider":"groq","text":"ok"}]

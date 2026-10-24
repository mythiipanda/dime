# Agnes provider candidate

This candidate adds an opt-in Agnes OpenAI-compatible route using
`https://apihub.agnes-ai.com/v1`. It permits only `agnes-3.0-flash` and
`agnes-2.5-flash`; the default is `agnes-3.0-flash`. Pro models and all other
model IDs fail closed. The documented zero price is a current public price,
not proof of account quota or runtime availability.

The endpoint and model support are documented in Agnes's [API overview],
[3.0 Flash guide], [pricing], and [OpenCode integration guide]. The public
Token Plan FAQ lists 10 RPM for the default free tier. The user's reported
larger account quota remains unverified and is not assumed here.

Set `AGNES_API_KEY`, `DIME_ENABLE_AGNES=true`, and optionally
`AGNES_MODEL=agnes-2.5-flash` in the backend process environment, or in
`backend/.env`. The documented local launch starts Uvicorn after `cd backend`,
so this is the `.env` path that launch reads. `Settings` resolves `.env`
relative to process working directory; a different launch directory changes
that path. The repository ignores both root `.env` and `backend/.env`;
`backend/.env.example` contains no credential. Do not set an Agnes key in a
shared/global environment.

The future interactive free-provider preference is Groq, Agnes, then other
existing free providers that are actually configured and enabled: Cerebras,
NVIDIA, OpenRouter, and Mistral. Gemini is last and appears only when its key is
configured. Groq and Agnes also require their explicit enable flags. FLM is absent from accepted
baseline `b8e4e2ba`; this candidate does not register or claim FLM support.
No quota cycling is added. The existing explicitly gated Inception policy is
unchanged and is not enabled by this candidate. This ordering describes future
interactive development routing; it does not add fallback to controlled
structured Reflection measurements.

The controlled `provider_live` structured path resolves its explicit provider
and exact model and does not automatically fail over to another provider or
model. A pinned Reflection request therefore remains on its pinned route.
This candidate has not made an authenticated Agnes request. Mock transport
checks prove wiring only.

[API overview]: https://wiki.agnes-ai.com/en/docs/overview
[3.0 Flash guide]: https://wiki.agnes-ai.com/en/docs/agnes-30-flash
[pricing]: https://wiki.agnes-ai.com/en/docs/pricing
[OpenCode integration guide]: https://wiki.agnes-ai.com/en/docs/cid7
[Token Plan FAQ]: https://wiki.agnes-ai.com/en/docs/tokenplan

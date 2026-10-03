import httpx
import openai
import pytest

from v2.adapters.models import ROUTE_POLICIES, ProviderStructuredModel


def _request():
    return httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def _response(status):
    return httpx.Response(status, request=_request())


def _groq_cases():
    return [
        (openai.RateLimitError("limited", response=_response(429), body=None),
         "rate_limit", True),
        (openai.APITimeoutError(_request()), "timeout", True),
        (openai.APIConnectionError(request=_request()), "network", True),
        (openai.InternalServerError("down", response=_response(500), body=None),
         "server_error", True),
        (openai.BadRequestError("bad", response=_response(400), body=None),
         "client_error", False),
        (openai.AuthenticationError("key", response=_response(401), body=None),
         "authentication", False),
        (ValueError("model returned malformed json object"), "structured_output",
         False),
        (RuntimeError("groq transient blip"), "provider_error", True),
    ]


@pytest.mark.parametrize("exc,expected_class,expected_retry", [
    (exc, cls, retry) for exc, cls, retry in _groq_cases()
])
def test_groq_error_class_retry_contract(exc, expected_class, expected_retry):
    assert ProviderStructuredModel._failure_class(exc) == expected_class
    transient = ROUTE_POLICIES["intake"]["transient_classes"]
    assert (expected_class in transient) is expected_retry

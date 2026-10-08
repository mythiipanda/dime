import pytest

from v2.adapters.models import ProviderStructuredModel
from v2.api.routes import _failure_kind, _failure_message


def test_quota_exhausted_token_classifies_as_quota():
    exc = RuntimeError(
        "all structured-output providers failed "
        "[gemini:ModelHTTPError:quota_exhausted, gemini:ModelHTTPError:quota_exhausted]")
    assert ProviderStructuredModel._failure_class(exc) == "quota_exhausted"


def test_provider_outage_is_not_reported_as_missing_data():
    exc = RuntimeError(
        "all structured-output providers failed "
        "[gemini:ModelHTTPError:server_error, gemini:ModelHTTPError:quota_exhausted]")
    kind = _failure_kind(exc)
    assert kind not in ("execution_failure", "")
    assert _failure_message(kind) != "Some requested data was unavailable."


@pytest.mark.parametrize("token,expected", [
    ("quota_exhausted", "quota"),
    ("rate_limit", "rate_limited"),
    ("server_error", "provider_error"),
])
def test_wrapped_provider_failures_map_to_distinct_kinds(token, expected):
    exc = RuntimeError(f"all structured-output providers failed [gemini:ModelHTTPError:{token}]")
    assert _failure_kind(exc) == expected


def test_quota_message_names_the_model():
    assert _failure_message("quota") == "The model ran out of quota."
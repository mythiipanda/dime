import pytest

from v2.adapters.models import ProviderStructuredModel


def test_quota_exhausted_token_classifies_as_quota():
    exc = RuntimeError(
        "all structured-output providers failed "
        "[gemini:ModelHTTPError:quota_exhausted, gemini:ModelHTTPError:quota_exhausted]")
    assert ProviderStructuredModel._failure_class(exc) == "quota_exhausted"

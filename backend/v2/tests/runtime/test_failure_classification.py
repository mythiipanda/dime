from v2.adapters.models import ProviderStructuredModel

QUOTA_MESSAGE = "429 RESOURCE_EXHAUSTED (GenerateRequestsPerDayPerProjectPerModel-FreeTier, 500/day)"


def test_per_day_quota_message_is_quota_exhausted_not_rate_limit():
    assert ProviderStructuredModel._failure_class(Exception(QUOTA_MESSAGE)) == "quota_exhausted"


def test_per_minute_429_with_embedded_500_is_rate_limit():
    assert ProviderStructuredModel._failure_class(Exception("429 rate_limit_exceeded: 500 requests per minute")) == "rate_limit"


def test_plain_429_without_500_is_rate_limit():
    assert ProviderStructuredModel._failure_class(Exception("429 quota exceeded for quota metric")) == "rate_limit"


def test_genuine_503_without_429_is_server_error():
    assert ProviderStructuredModel._failure_class(Exception("503 Service Unavailable")) == "server_error"

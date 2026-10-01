import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.providers as prov

QUOTA_MESSAGE = "429 RESOURCE_EXHAUSTED (GenerateRequestsPerDayPerProjectPerModel-FreeTier, 500/day)"


def test_quota_message_with_embedded_500_is_rate_limit():
    assert prov._failure_class(Exception(QUOTA_MESSAGE)) == "rate_limit"


def test_plain_429_without_500_is_rate_limit():
    assert prov._failure_class(Exception("429 quota exceeded for quota metric")) == "rate_limit"


def test_genuine_503_without_429_is_server_error():
    assert prov._failure_class(Exception("503 Service Unavailable")) == "server_error"

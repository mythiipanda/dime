"""Dime backend package."""

import os

# Sanitize proxy env vars at import time. Some sandboxes ship a no_proxy
# with bracketed IPv6 literals (e.g. "[::1]") that httpx parses as an
# invalid port, silently hanging outbound LLM calls. Strip the brackets
# so httpx never chokes, regardless of how the app is imported.
for _var in ("no_proxy", "NO_PROXY"):
    _val = os.environ.get(_var)
    if _val and "[" in _val:
        os.environ[_var] = _val.replace("[", "").replace("]", "")

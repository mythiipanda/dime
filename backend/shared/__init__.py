"""Dime shared backend package (data layer, config, providers)."""
import os
for _var in ("no_proxy", "NO_PROXY"):
    _val = os.environ.get(_var)
    if _val and "[" in _val:
        os.environ[_var] = _val.replace("[", "").replace("]", "")

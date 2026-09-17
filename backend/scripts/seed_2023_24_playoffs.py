"""Backward-compatible entry point for historical playoff promotion."""
try:
    from scripts.seed_historical_playoffs import *  # noqa: F401,F403
    from scripts.seed_historical_playoffs import main
except ModuleNotFoundError:
    from seed_historical_playoffs import *  # noqa: F401,F403
    from seed_historical_playoffs import main

if __name__ == "__main__":
    raise SystemExit(main())

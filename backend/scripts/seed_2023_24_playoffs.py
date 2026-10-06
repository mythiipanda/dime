try:
    from scripts.seed_historical_playoffs import *
    from scripts.seed_historical_playoffs import main
except ModuleNotFoundError:
    from seed_historical_playoffs import *
    from seed_historical_playoffs import main

if __name__ == "__main__":
    raise SystemExit(main())

import os
import subprocess
import sys
from pathlib import Path

FALLBACK_ROOT = Path("C:/Users/15980/Downloads/dime/dime-internal/benchmarks/dab-v1")


def resolve_root(argv):
    if "--dab-root" in argv:
        index = argv.index("--dab-root")
        if index + 1 < len(argv):
            root = Path(argv[index + 1])
            del argv[index:index + 2]
            return root
    env_root = os.environ.get("DIME_DAB_ROOT")
    if env_root:
        return Path(env_root)
    sibling = Path(__file__).resolve().parents[2] / "dime-internal" / "benchmarks" / "dab-v1"
    if sibling.is_dir():
        return sibling
    return FALLBACK_ROOT


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    root = resolve_root(args)
    runner = root / "run_dab.py"
    if not runner.is_file():
        print(
            f"DAB runner not found: {runner}. Pass --dab-root <path> or set DIME_DAB_ROOT.",
            file=sys.stderr,
        )
        return 2
    result = subprocess.run([sys.executable, str(runner), *args], cwd=str(root))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

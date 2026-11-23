import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
DOC_SUFFIXES = {".md", ".mdx", ".rst", ".txt", ".adoc"}
MARKER_RE = ("<", "|", ">")
SELF_TEST_CASES = (
    ("head-marker", ".ts", "const a = 1\n<<<<<<< HEAD\nconst a = 2\n", 1),
    ("base-marker", ".ts", "const a = 1\n||||||| merged common ancestors\nconst a = 2\n", 1),
    ("theirs-marker", ".ts", "const a = 1\n>>>>>>> origin/dev\n", 1),
    ("eq-dangling-code", ".ts", "const a = 1\n=======\nconst b = 2\n", 1),
    ("eq-dangling-md-blank-prev", ".md", "Title\n\n=======\nmore\n", 1),
    ("md-title-underline", ".md", "Heading\n=======\nbody\n", 0),
    ("rst-title-underline", ".rst", "Heading\n=======\nbody\n", 0),
    ("eq-longer-run", ".ts", "const a = 1\n========\nconst b = 2\n", 0),
    ("marker-in-string", ".py", 's = "<<<<<<<"\nx = 1\n', 0),
    ("clean-file", ".ts", "const a = 1\nconst b = 2\n", 0),
)


def repository_files():
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    return [name.replace("\\", "/") for name in result.stdout.splitlines()]


def binary_file(path):
    try:
        with path.open("rb") as handle:
            return b"\x00" in handle.read(8192)
    except OSError:
        return True


def line_violations(text, is_doc):
    count = 0
    previous = ""
    for line in text.splitlines():
        stripped = line.strip()
        hit = False
        for char in MARKER_RE:
            if stripped.startswith(char * 7):
                hit = True
        if stripped == "=" * 7 and (not is_doc or not previous.strip()):
            hit = True
        if hit:
            count += 1
        previous = stripped
    return count


def scan():
    counts = {}
    for name in repository_files():
        path = ROOT / name
        if not path.is_file() or binary_file(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        count = line_violations(text, path.suffix.lower() in DOC_SUFFIXES)
        if count:
            counts[name] = count
    return counts


def self_test():
    failures = []
    for name, suffix, text, expected in SELF_TEST_CASES:
        actual = line_violations(text, suffix in DOC_SUFFIXES)
        if actual != expected:
            failures.append(f"{name}: expected {expected}, got {actual}")
    for failure in failures:
        print(f"FAIL  {failure}")
    if failures:
        print(f"FAIL  {len(failures)} self-test case(s) failed")
        return 1
    print(f"PASS  {len(SELF_TEST_CASES)} self-test case(s)")
    return 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    counts = scan()
    for name, count in sorted(counts.items()):
        print(f"FAIL  {name}: {count} conflict-marker line(s)")
    if counts:
        print(f"FAIL  {len(counts)} file(s) carry leftover conflict markers")
        return 1
    print("PASS  no conflict markers in tracked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

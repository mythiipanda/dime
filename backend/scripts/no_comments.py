import ast
import io
import json
import subprocess
import sys
import tokenize
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
BASELINE = SCRIPT.with_name("no_comments_baseline.json")
ROOTS = ("backend", "frontend")
EXCLUDED_DIRS = {"node_modules", ".next", "dist", "__pycache__", ".git", "out", "coverage"}
GENERATED_FILES = {"next-env.d.ts"}
PYTHON_SUFFIXES = {".py", ".pyi"}
SCRIPT_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
DIRECTIVES = ("type: ignore", "noqa", "pylint:", "@ts-ignore", "@ts-expect-error",
              "eslint-disable", "prettier-ignore", "-*- coding:")


def excluded(relative):
    if relative.name in GENERATED_FILES:
        return True
    if any(part in EXCLUDED_DIRS for part in relative.parts[:-1]):
        return True
    return ".min." in relative.name


def repository_files():
    try:
        result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                                cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        names = []
        for root_name in ROOTS:
            base = ROOT / root_name
            if not base.is_dir():
                continue
            names.extend(path.relative_to(ROOT).as_posix() for path in base.rglob("*") if path.is_file())
        return names
    return [name.replace("\\", "/") for name in result.stdout.splitlines()]


def machine_directive(body):
    stripped = body.strip()
    if not stripped:
        return True
    if stripped.startswith("!"):
        return True
    return stripped.startswith(DIRECTIVES)


def python_violations(text):
    count = 0
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type != tokenize.COMMENT:
                continue
            if not machine_directive(token.string.lstrip("#")):
                count += 1
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        pass
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return count
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        document = ast.get_docstring(node, clean=False)
        if document is not None and document.strip():
            count += 1
    return count


def skip_quoted(text, index):
    quote = text[index]
    index += 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == quote:
            return index + 1
        index += 1
    return index


def skip_regex(text, index):
    index += 1
    inside = False
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            inside = True
        elif char == "]":
            inside = False
        elif char == "/" and not inside:
            index += 1
            while index < len(text) and text[index].isalpha():
                index += 1
            return index
        elif char == "\n":
            return index
        index += 1
    return index


def regex_allowed(previous):
    if not previous:
        return True
    return not (previous.isalnum() or previous in "_$)]}")


def scan_code(text, index, comments, terminator=None):
    depth = 0
    previous = ""
    while index < len(text):
        char = text[index]
        if terminator is not None:
            if char == "{":
                depth += 1
            elif char == "}":
                if depth == 0:
                    return index + 1
                depth -= 1
        if char == "/" and text[index + 1:index + 2] == "/":
            end = text.find("\n", index)
            end = len(text) if end == -1 else end
            comments.append(text[index + 2:end])
            index = end
            previous = ""
            continue
        if char == "/" and text[index + 1:index + 2] == "*":
            end = text.find("*/", index + 2)
            end = len(text) if end == -1 else end + 2
            comments.append(text[index + 2:end - 2])
            index = end
            previous = ""
            continue
        if char in "\"'":
            index = skip_quoted(text, index)
            previous = char
            continue
        if char == "`":
            index = scan_template(text, index, comments)
            previous = char
            continue
        if char == "/" and regex_allowed(previous):
            index = skip_regex(text, index)
            previous = "/"
            continue
        if not char.isspace():
            previous = char
        index += 1
    return index


def scan_template(text, index, comments):
    index += 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "`":
            return index + 1
        if char == "$" and text[index + 1:index + 2] == "{":
            index = scan_code(text, index + 2, comments, "}")
            continue
        index += 1
    return index


def script_violations(text):
    comments = []
    scan_code(text, 0, comments)
    return sum(1 for comment in comments if not machine_directive(comment))


def scan():
    counts = {}
    for name in repository_files():
        relative = Path(name)
        if not relative.parts or relative.parts[0] not in ROOTS:
            continue
        if excluded(relative):
            continue
        path = ROOT / relative
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in PYTHON_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="replace")
            count = python_violations(text)
        elif suffix in SCRIPT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="replace")
            count = script_violations(text)
        else:
            continue
        if count:
            counts[relative.as_posix()] = count
    return counts


def main(argv):
    counts = scan()
    if "--write-baseline" in argv:
        BASELINE.write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"baseline written: {len(counts)} files, {sum(counts.values())} violations")
        return 0
    if not BASELINE.exists():
        print(f"FAIL  missing baseline {BASELINE}")
        return 2
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    failures = []
    for name in sorted(counts):
        extra = counts[name] - baseline.get(name, 0)
        if extra > 0:
            failures.append((name, extra))
    for name, count in failures:
        print(f"FAIL  {name}: {count} new comment violation(s)")
    if failures:
        print(f"FAIL  {len(failures)} file(s) carry new comment violations")
        return 1
    print(f"PASS  {len(counts)} file(s) keep their recorded violations, no new comment violations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

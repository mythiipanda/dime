import ast
import io
import json
import re
import subprocess
import sys
import tokenize
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
BASELINE = SCRIPT.with_name("no_comments_baseline.json")
ROOTS = ("backend", "frontend")
EXCLUDED_DIRS = {"node_modules", ".next", "dist", "__pycache__", ".git", "out", "coverage"}
EXCLUDED_PREFIXES = (("backend", "data"),)
GENERATED_FILES = {"next-env.d.ts"}
PYTHON_SUFFIXES = {".py", ".pyi"}
SCRIPT_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts",
                   ".jsonc", ".json5"}
JSX_SUFFIXES = {".jsx", ".tsx"}
BLOCK_SUFFIXES = {".css"}
MARKUP_SUFFIXES = {".html", ".svg"}
HASH_SUFFIXES = {".yml", ".yaml", ".toml", ".sh", ".ps1"}
HASH_NAMES = {"Dockerfile", ".dockerignore", ".gitignore"}
ENV_NAMES = {".env.example", ".env.template"}
DIRECTIVES = ("type: ignore", "type:ignore", "noqa", "pylint:", "@ts-ignore", "@ts-expect-error",
              "eslint-disable", "prettier-ignore", "-*- coding:")
REGEX_KEYWORDS = {"return", "typeof", "case", "in", "of", "delete", "void", "yield",
                  "await", "throw", "else", "do"}
BLOCK_COMMENT = re.compile(r"/\*(.*?)\*/", re.S)
MARKUP_COMMENT = re.compile(r"<!--(.*?)-->", re.S)
SELF_TEST_CASES = (
    ("jsx-url-text", "jsx", "export const A = () => <p>see http://a.dev/b</p>;\n", 0),
    ("jsx-division-text", "jsx", "export const A = () => <p>use // for division</p>;\n", 0),
    ("jsx-line-comment", "jsx", "export const A = 1;\n// real comment\n", 1),
    ("jsx-block-comment", "jsx", "export const A = 1;\n/* real comment */\n", 1),
    ("script-line-comment", "script", "// real comment\nexport const A = 1;\n", 1),
    ("script-trailing-comment", "script", "export const A = 1; // real comment\n", 1),
    ("script-ts-ignore", "script", "// @ts-ignore\nexport const A = 1;\n", 0),
    ("script-ts-expect-error", "script", "// @ts-expect-error\nexport const A = 1;\n", 0),
    ("script-eslint-disable", "script", "/* eslint-disable */\nexport const A = 1;\n", 0),
    ("script-prettier-ignore", "script", "// prettier-ignore\nexport const A = 1;\n", 0),
    ("script-regex-literal", "script", "function f(){ return /[/*]/; }\n", 0),
    ("script-regex-slash", "script", "function f(){ return /abc/; }\n", 0),
    ("hash-comment", "hash", "# human note\nKEY=value\n", 1),
    ("hash-shebang", "hash", "#!/bin/sh\nKEY=value\n", 0),
    ("hash-type-ignore", "hash", "# type:ignore\nKEY=value\n", 0),
    ("hash-type-ignore-space", "hash", "# type: ignore\nKEY=value\n", 0),
    ("block-comment", "block", "a { color: red; } /* human */\n", 1),
    ("block-prettier-ignore", "block", "/* prettier-ignore */\na { color: red; }\n", 0),
    ("markup-comment", "markup", "<p>x</p><!-- human -->\n", 1),
    ("python-comment", "python", "x = 1  # human\n", 1),
    ("python-shebang", "python", "#!/usr/bin/env python3\nx = 1\n", 0),
    ("python-docstring", "python", '"""doc."""\n', 1),
)


def excluded(relative):
    if relative.name in GENERATED_FILES:
        return True
    if any(part in EXCLUDED_DIRS for part in relative.parts[:-1]):
        return True
    for prefix in EXCLUDED_PREFIXES:
        if relative.parts[:len(prefix)] == prefix:
            return True
    if relative.name.startswith(".env") and relative.name not in ENV_NAMES:
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


def binary_file(path):
    with path.open("rb") as handle:
        return b"\x00" in handle.read(8192)


def file_kind(path):
    suffix = path.suffix.lower()
    if suffix in PYTHON_SUFFIXES:
        return "python"
    if suffix in SCRIPT_SUFFIXES:
        return "jsx" if suffix in JSX_SUFFIXES else "script"
    if suffix in BLOCK_SUFFIXES:
        return "block"
    if suffix in MARKUP_SUFFIXES:
        return "markup"
    if suffix in HASH_SUFFIXES:
        return "hash"
    if path.name in HASH_NAMES or path.name in ENV_NAMES:
        return "hash"
    if not suffix:
        return "hash"
    return None


def machine_directive(body):
    stripped = body.strip()
    if stripped.startswith("!/"):
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


def hash_violations(text):
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        if not machine_directive(stripped.lstrip("#")):
            count += 1
    return count


def block_violations(text):
    return sum(1 for body in BLOCK_COMMENT.findall(text) if not machine_directive(body))


def markup_violations(text):
    return sum(1 for body in MARKUP_COMMENT.findall(text) if not machine_directive(body))


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


def preceding_word(text, index):
    end = index
    while end > 0 and text[end - 1].isspace():
        end -= 1
    start = end
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "_$"):
        start -= 1
    return text[start:end]


def regex_allowed(previous, text, index):
    if not previous:
        return True
    if previous.isalnum() or previous in "_$)]}":
        return preceding_word(text, index) in REGEX_KEYWORDS
    return True


def line_leading(text, index):
    start = text.rfind("\n", 0, index) + 1
    return not text[start:index].strip()


def scan_code(text, index, comments, terminator=None, jsx=False):
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
            if jsx and not line_leading(text, index):
                index += 2
                previous = ""
                continue
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
            index = scan_template(text, index, comments, jsx)
            previous = char
            continue
        if char == "/" and regex_allowed(previous, text, index):
            index = skip_regex(text, index)
            previous = "/"
            continue
        if not char.isspace():
            previous = char
        index += 1
    return index


def scan_template(text, index, comments, jsx=False):
    index += 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "`":
            return index + 1
        if char == "$" and text[index + 1:index + 2] == "{":
            index = scan_code(text, index + 2, comments, "}", jsx)
            continue
        index += 1
    return index


def script_violations(text, jsx=False):
    comments = []
    scan_code(text, 0, comments, jsx=jsx)
    return sum(1 for comment in comments if not machine_directive(comment))


def violations_for(kind, text):
    if kind == "python":
        return python_violations(text)
    if kind == "script":
        return script_violations(text, False)
    if kind == "jsx":
        return script_violations(text, True)
    if kind == "block":
        return block_violations(text)
    if kind == "markup":
        return markup_violations(text)
    return hash_violations(text)


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
        kind = file_kind(path)
        if kind is None:
            continue
        if binary_file(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        count = violations_for(kind, text)
        if count:
            counts[relative.as_posix()] = count
    return counts


def self_test():
    failures = []
    for name, kind, text, expected in SELF_TEST_CASES:
        actual = violations_for(kind, text)
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

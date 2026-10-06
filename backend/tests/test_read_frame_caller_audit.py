
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

BACKEND = Path(__file__).resolve().parent.parent
SKIP_PARTS = {"tests", "test", "__pycache__", "bench", "fixtures"}

READ = "read_frame"
OPTIONAL = "read_frame_optional"
ERROR = "TableAbsent"

OPTIONAL_READ_SITES = {
    ("shared.tools._core", "_bound_warehouse_read"):
        "cache-first reader: a cold table is fetched live and seeded by "
        "save_frame, and the returned meta declares cached=False with the "
        "live source, so absence is a declared cold start rather than a miss",
    ("shared.tools.today", "_warehouse_has_games"):
        "the predicate only decides whether to consult the live source, and "
        "it is consulted in the offseason, where no games exist either way, "
        "so an absent scoreboard table and an empty one agree",
    ("scripts.seed_sportsdataverse", "have_shots"):
        "seed script asks whether silver_hist_shots has been seeded yet; "
        "absent means nothing seeded, which is the question being asked",
    ("scripts.seed_sportsdataverse", "have_player_seasons"):
        "seed script asks whether silver_hist_player_seasons has been "
        "seeded yet; absent means nothing seeded, which is the question "
        "being asked",
}

def _python_files():
    for path in sorted(BACKEND.rglob("*.py")):
        if SKIP_PARTS & set(path.parts):
            continue
        yield path

def _module_of(path: Path) -> str:
    return ".".join(path.relative_to(BACKEND).with_suffix("").parts)

def _dotted(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))

def _called_name(call: ast.Call) -> str | None:
    if not isinstance(call.func, ast.Attribute):
        return None
    if not isinstance(call.func.value, ast.Name):
        return None
    return call.func.attr

def _handler_catches_broadly(handler: ast.ExceptHandler) -> bool:
    caught: list[ast.AST] = []
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Tuple):
        caught = list(handler.type.elts)
    else:
        caught = [handler.type]
    return any(_dotted(node).rsplit(".", 1)[-1]
               in {"Exception", "BaseException"} for node in caught)

def _handler_names_absence(handler: ast.ExceptHandler) -> bool:
    nodes = handler.type.elts if isinstance(handler.type, ast.Tuple) else (
        [handler.type] if handler.type is not None else [])
    return any(_dotted(node).rsplit(".", 1)[-1] == ERROR for node in nodes)

def _handler_surfaces_error(handler: ast.ExceptHandler) -> bool:
    if not isinstance(handler.name, str):
        return False
    bound = handler.name
    for node in ast.walk(handler):
        if isinstance(node, ast.Name) and node.id == bound:
            return True
    return False

def _walk(node, module, funcs, frames, found):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _walk(child, module, funcs + [child.name], frames, found)
            continue
        if isinstance(child, ast.Try):
            _walk(child, module, funcs, frames + [child], found)
            continue
        if isinstance(child, ast.Call):
            name = _called_name(child)
            if name in (READ, OPTIONAL):
                found.append((module, ".".join(funcs), name, child.lineno,
                              list(frames)))
        _walk(child, module, funcs, frames, found)

def _calls():
    found = []
    for path in _python_files():
        module = _module_of(path)
        _walk(ast.parse(path.read_text(), filename=str(path)),
              module, [], [], found)
    return found

def _masks_the_miss(frames) -> str | None:
    for node in frames:
        broad = [h for h in node.handlers if _handler_catches_broadly(h)]
        if not broad:
            continue
        if any(_handler_names_absence(h) for h in node.handlers):
            continue
        if any(_handler_surfaces_error(h) for h in broad):
            continue
        return f"line {node.lineno} swallows a warehouse miss"
    return None

def test_audit_sees_every_read_frame_call_site():
    reads = [c for c in _calls() if c[2] == READ]
    optional = [c for c in _calls() if c[2] == OPTIONAL]
    assert len(reads) >= 20, "the audit lost its call sites; re-derive it"
    assert len(optional) >= 3, "the audit lost its optional call sites"

@pytest.mark.parametrize("entry", sorted(OPTIONAL_READ_SITES),
                         ids=lambda e: f"{e[0]}.{e[1]}")
def test_optional_read_sites_carry_a_reason(entry):
    reason = OPTIONAL_READ_SITES[entry]
    assert reason.strip(), "an optional read must state why absence is allowed"

def test_no_optional_read_outside_the_audit():
    allowed = set(OPTIONAL_READ_SITES)
    strays = sorted({f"{c[0]}.{c[1]}:{c[3]}" for c in _calls()
                     if c[2] == OPTIONAL and (c[0], c[1]) not in allowed})
    assert strays == [], (
        "read_frame_optional outside the audited set; register the site in "
        f"OPTIONAL_READ_SITES with its reason: {strays}")

def test_every_audited_optional_site_still_reads_optional():
    seen = {(c[0], c[1]) for c in _calls() if c[2] == OPTIONAL}
    assert set(OPTIONAL_READ_SITES) - seen == set(), (
        "OPTIONAL_READ_SITES names a site that no longer reads optional; "
        "stale registry entries hide real call sites")

def test_no_read_frame_call_can_receive_silent_empty():
    offenders = []
    for module, func, name, lineno, frames in _calls():
        if name != READ:
            continue
        why = _masks_the_miss(frames)
        if why:
            offenders.append(f"{module}.{func} line {lineno}: {why}")
    assert offenders == [], (
        "a warehouse miss is still converted into a plausible empty result; "
        "let TableAbsent propagate, name it in the handler, or surface the "
        f"error text: {offenders}")

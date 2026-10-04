from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import json
import re
import sys
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import duckdb

from shared import store as _store
from shared.tools import v1_tools
from v2.adapters import coverage as _coverage
from v2.adapters.capabilities import CAPABILITIES

MAX_DEPTH = 12
_CALL_METHODS = frozenset({"ainvoke", "invoke", "abatch", "batch", "arun", "run"})
RESOLUTION_HELPERS = frozenset({
    "shared.tools._core.coerce_player_id",
    "shared.tools._core.coerce_team_id",
    "shared.tools._core.score_player_candidates",
})


def _tool_entrypoint(tool: object):
    func = getattr(tool, "func", None)
    if inspect.isfunction(func) or inspect.ismethod(func):
        return func
    coroutine = getattr(tool, "coroutine", None)
    if inspect.isfunction(coroutine) or inspect.ismethod(coroutine):
        return coroutine
    raise ValueError(f"tool {tool!r} exposes no python entrypoint")


def _module_text(module) -> str:
    return Path(inspect.getfile(module)).read_text()


def _closure(entrypoint) -> tuple[list, dict[str, object]]:
    seen: set[tuple[str, str]] = set()
    entry_module = importlib.import_module(entrypoint.__module__)
    queue: list[tuple[object, object, int]] = [(entrypoint, entry_module, 0)]
    functions: list = []
    constants: dict[str, object] = {}
    while queue:
        node, module, depth = queue.pop()
        if depth > MAX_DEPTH:
            continue
        if isinstance(node, str):
            constants.setdefault(node, getattr(module, node, None))
            continue
        if not (inspect.isfunction(node) or inspect.ismethod(node)):
            continue
        key = (node.__module__, node.__qualname__)
        if key in seen:
            continue
        seen.add(key)
        functions.append(node)
        try:
            source = textwrap.dedent(inspect.getsource(node))
            tree = ast.parse(source)
        except (OSError, TypeError, SyntaxError) as exc:
            raise ValueError(f"cannot read source of {key}: {exc}") from exc
        module = importlib.import_module(node.__module__)
        scope = dict(_closure_scope(module))
        scope.update(_local_imports(module, tree))
        for child in ast.walk(tree):
            if isinstance(child, ast.Call):
                callee = child.func
                if isinstance(callee, ast.Attribute) and callee.attr in _CALL_METHODS:
                    owner = callee.value
                    if isinstance(owner, ast.Name):
                        queue.append(
                            (_resolve(module, owner.id, scope), module, depth + 1))
                    continue
                name = (callee.id if isinstance(callee, ast.Name)
                        else callee.attr if isinstance(callee, ast.Attribute)
                        else None)
                if name:
                    queue.append((_resolve(module, name, scope), module, depth + 1))
            elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                if child.id in scope:
                    queue.append((child.id, module, depth + 1))
    return functions, constants


def _local_imports(module, tree: ast.AST) -> dict[str, object]:
    scope: dict[str, object] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        name = node.module.lstrip(".")
        if node.level and node.level > 1:
            target = None
        else:
            target = getattr(module, name, None)
        if not isinstance(target, object) or not hasattr(target, "__name__"):
            try:
                target = importlib.import_module(
                    f"{module.__package__}.{name}" if node.level else name)
            except ImportError:
                continue
        for alias in node.names:
            value = getattr(target, alias.name, None)
            scope[alias.asname or alias.name] = value
    return scope


def _closure_scope(module) -> dict[str, object]:
    scope: dict[str, object] = {}
    for node in ast.parse(_module_text(module)).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope[node.name] = getattr(module, node.name, None)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    scope[target.id] = getattr(module, target.id, None)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            scope[node.target.id] = getattr(module, node.target.id, None)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                scope[alias.asname or alias.name.split(".")[0]] = getattr(
                    module, alias.asname or alias.name.split(".")[0], None)
    return scope


def _resolve(module, name: str, scope: dict[str, object]):
    target = scope.get(name, getattr(module, name, None))
    if isinstance(target, (list, tuple)):
        for item in target:
            if hasattr(item, "func") or hasattr(item, "coroutine"):
                return _tool_entrypoint(item)
        return None
    if hasattr(target, "name") and (
            hasattr(target, "func") or hasattr(target, "coroutine")):
        return _tool_entrypoint(target)
    if inspect.isfunction(target) or inspect.ismethod(target):
        return target
    if isinstance(target, (str, int, float, bool, type(None))):
        return target
    if isinstance(target, (list, tuple)):
        return None
    return str(target)


def _scan(text: str, tables: tuple[str, ...]) -> set[str]:
    return {table for table in tables
            if re.search(rf"\b{re.escape(table)}\b", text)}


def warehouse_inventory() -> tuple[tuple[str, ...], dict[str, dict]]:
    connection = duckdb.connect(str(_store.DB_PATH), read_only=True)
    try:
        names = tuple(sorted(
            row[0] for row in connection.execute("SHOW TABLES").fetchall()))
        detail: dict[str, dict] = {}
        for name in names:
            columns = [row[1] for row in connection.execute(
                f"PRAGMA table_info({name})").fetchall()]
            total = connection.execute(
                f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            seasons: dict[str, int] = {}
            if "_season" in columns:
                seasons = {
                    str(row[0]): int(row[1])
                    for row in connection.execute(
                        f"SELECT _season, COUNT(*) FROM {name} "
                        "GROUP BY 1 ORDER BY 1").fetchall()
                    if row and row[0]
                }
            detail[name] = {"rows": int(total), "seasons": seasons}
    finally:
        connection.close()
    return names, detail


def _entrypoint_for(tool_name: str):
    by_name = {tool.name: tool for tool in v1_tools}
    tool = by_name.get(tool_name)
    if tool is not None:
        return _tool_entrypoint(tool), f"shared tool {tool_name}"
    module = importlib.import_module("v2.adapters.coverage")
    func = getattr(module, tool_name, None)
    if inspect.isfunction(func):
        return func, f"v2 coverage {tool_name}"
    raise ValueError(f"capability tool {tool_name} is not registered")


def _dynamic_reads(functions, tables: tuple[str, ...]) -> list[str]:
    reasons = []
    for function in functions:
        source = textwrap.dedent(inspect.getsource(function))
        names = " ".join(tables)
        if ("SHOW TABLES" in source or re.search(r"\bstore\.tables\(", source)) \
                and not re.search(rf"\b{re.escape(names)}", source):
            reasons.append(f"{function.__qualname__} enumerates every table")
        if "f\"silver_leaders_" in source:
            reasons.append(
                f"{function.__qualname__} resolves a leaderboard table name")
    return reasons


def build() -> list[dict]:
    names, detail = warehouse_inventory()
    rows: list[dict] = []
    for capability, spec in CAPABILITIES.items():
        entrypoint, origin = _entrypoint_for(spec.tool_name)
        functions, constants = _closure(entrypoint)
        read: set[str] = set()
        result_functions = [
            function for function in functions
            if f"{function.__module__}.{function.__qualname__}"
            not in RESOLUTION_HELPERS
        ]
        resolution: set[str] = set()
        for function in functions:
            found = _scan(textwrap.dedent(inspect.getsource(function)), names)
            if f"{function.__module__}.{function.__qualname__}" in RESOLUTION_HELPERS:
                resolution |= found
                continue
            read |= found
        for value in constants.values():
            if isinstance(value, str):
                read |= _scan(value, names)
        dynamic = _dynamic_reads(functions, names)
        prefixed = _dynamic_prefixes(functions, names)
        season_tables = tuple(
            sorted(name for name in read if detail[name]["seasons"]))
        read_without_season = tuple(
            sorted(name for name in read if not detail[name]["seasons"]))
        registry = _coverage.tables_for_capability(capability, {})
        missing = tuple(sorted(set(season_tables) - set(registry)))
        extra = tuple(sorted(set(registry) - set(season_tables)))
        rows.append({
            "capability": capability,
            "tool": spec.tool_name,
            "tool_origin": origin,
            "season_scoped": spec.task_season_scoped,
            "live_fallback": spec.live_fallback,
            "closure_size": len(functions),
            "read_tables": season_tables,
            "read_without_season": read_without_season,
            "resolution_tables": tuple(sorted(resolution - read)),
            "closure_functions": len(result_functions),
            "registry_tables": tuple(registry),
            "missing_from_registry": missing,
            "not_read_by_tool": extra,
            "dynamic_reads": dynamic,
            "dynamic_prefixes": prefixed,
            "seasons": {
                name: sorted(detail[name]["seasons"])
                for name in season_tables
            },
            "rows_in": {name: detail[name]["rows"] for name in season_tables},
            "registry_seasons": {
                name: sorted(detail[name]["seasons"])
                for name in registry if name in detail
            },
            "registry_unknown_tables": tuple(
                sorted(name for name in registry if name not in detail)),
        })
    return rows


def _dynamic_prefixes(functions, tables: tuple[str, ...]) -> list[str]:
    found = []
    for function in functions:
        for node in ast.walk(ast.parse(textwrap.dedent(
                inspect.getsource(function)))):
            if not isinstance(node, ast.JoinedStr):
                continue
            for value in node.values:
                if not isinstance(value, ast.Constant):
                    continue
                text = str(value.value)
                if "_" not in text:
                    continue
                if any(table.startswith(text) for table in tables):
                    found.append(
                        f"{function.__qualname__}: f-string fragment {text!r}")
    return sorted(set(found))


def _fmt(values) -> str:
    return ", ".join(values) if values else "-"


def render(rows: list[dict]) -> str:
    lines = [
        f"{'capability':22} {'tool':28} {'registry':52} "
        f"{'reads':6} {'missing':6} {'extra':6}",
    ]
    for row in rows:
        lines.append(
            f"{row['capability']:22} {row['tool']:28} "
            f"{_fmt(row['registry_tables']):52} "
            f"{len(row['read_tables']):<6} "
            f"{'X' if row['missing_from_registry'] else '-':6} "
            f"{'X' if row['not_read_by_tool'] else '-':6}")
    lines.append("")
    for row in rows:
        if row["missing_from_registry"] or row["not_read_by_tool"] or \
                row["dynamic_reads"] or row["registry_unknown_tables"]:
            lines.append(f"{row['capability']} ({row['tool']})")
            lines.append(f"  reads            {_fmt(row['read_tables'])}")
            if row["read_without_season"]:
                lines.append(
                    f"  reads no season  {_fmt(row['read_without_season'])}")
            lines.append(f"  registry         {_fmt(row['registry_tables'])}")
            lines.append(f"  missing          {_fmt(row['missing_from_registry'])}")
            lines.append(f"  not read         {_fmt(row['not_read_by_tool'])}")
            if row["registry_unknown_tables"]:
                lines.append(
                    f"  unknown table    {_fmt(row['registry_unknown_tables'])}")
            for note in row["dynamic_reads"] + row["dynamic_prefixes"]:
                lines.append(f"  dynamic          {note}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument(
        "--check", action="store_true",
        help="exit 1 when a season-scoped capability has no registry entry")
    args = parser.parse_args()
    rows = build()
    if args.check:
        invisible = sorted(
            row["capability"] for row in rows
            if row["season_scoped"] and not row["registry_tables"])
        if invisible:
            print(f"season-scoped capabilities with no registry entry: {invisible}")
            return 1
        print("every season-scoped capability names coverage tables")
        return 0
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    if args.markdown:
        print("| capability | tool | registry entry | reads | verdict |")
        print("| --- | --- | --- | --- | --- |")
        for row in rows:
            verdict = []
            if row["missing_from_registry"]:
                verdict.append(f"missing {_fmt(row['missing_from_registry'])}")
            if row["not_read_by_tool"]:
                verdict.append(f"extra {_fmt(row['not_read_by_tool'])}")
            if row["registry_unknown_tables"]:
                verdict.append(
                    f"unknown table {_fmt(row['registry_unknown_tables'])}")
            if not verdict:
                verdict.append("ok")
            reads = ", ".join(
                f"{name} ({len(row['seasons'][name])} seasons)"
                for name in row["read_tables"])
            print(f"| {row['capability']} | {row['tool']} | "
                  f"{_fmt(row['registry_tables'])} | {reads or '-'} | "
                  f"{'; '.join(verdict)} |")
        return 0
    print(render(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
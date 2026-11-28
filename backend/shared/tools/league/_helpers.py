from contextlib import contextmanager
import sys


def _pkg():
    return sys.modules[__package__]


def _warehouse_tables(con) -> set[str]:
    return {r[0] for r in con.execute("SHOW TABLES").fetchall()}


def _cap_season_for_fa_year(fa_year: object) -> str | None:
    try:
        year = int(str(fa_year).strip())
    except (TypeError, ValueError):
        return None
    if year < 1000 or year > 9999:
        return None
    return f"{year}-{(year + 1) % 100:02d}"


@contextmanager
def _owned_connection(con: object, *, read_only: bool = True):
    if con is not None:
        yield con
        return
    own = _pkg().store.connect(read_only=read_only)
    try:
        yield own
    finally:
        try:
            own.close()
        except Exception:
            pass


def declare_units(result: dict, mapping: dict) -> dict:
    if not mapping:
        return result
    declared = result.setdefault("declared_column_semantics", {})
    for column, unit in mapping.items():
        if not isinstance(column, str) or not isinstance(unit, str) or not unit.strip():
            continue
        entry = declared.setdefault(column, {})
        if isinstance(entry, dict):
            entry["unit"] = unit.strip()
    return result


def declare_money(result: dict, fields) -> dict:
    return declare_units(result, {field: "usd_dollars" for field in fields})

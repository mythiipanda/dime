from contextlib import contextmanager
import sys


def _pkg():
    return sys.modules[__package__]


def _warehouse_tables(con) -> set[str]:
    return {r[0] for r in con.execute("SHOW TABLES").fetchall()}


@contextmanager
def _owned_connection(con: object):
    if con is not None:
        yield con
        return
    own = _pkg().store.connect()
    try:
        yield own
    finally:
        try:
            own.close()
        except Exception:
            pass

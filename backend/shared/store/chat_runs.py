import json as _json
import sys
from datetime import datetime, timezone


def _pkg():
    return sys.modules[__package__]


def save_chat(thread: str, role: str, text: str, owner: str = "") -> None:
    pkg = _pkg()
    con = pkg.state_connect()
    try:
        with pkg.state_write_guard():
            con.execute(
                """CREATE TABLE IF NOT EXISTS chat_history(
                thread VARCHAR, role VARCHAR, text VARCHAR, created_at VARCHAR,
                owner VARCHAR)"""
            )
            cols = [r[1] for r in con.execute("PRAGMA table_info(chat_history)").fetchall()]
            if "owner" not in cols:
                con.execute("ALTER TABLE chat_history ADD COLUMN owner VARCHAR DEFAULT ''")
            con.execute(
                "INSERT INTO chat_history VALUES (?,?,?,?,?)",
                [
                    thread,
                    role,
                    text[:4000],
                    datetime.now(timezone.utc).isoformat(),
                    owner[:80],
                ],
            )
    finally:
        con.close()


def chat_history(thread: str, limit: int = 6) -> list[dict[str, str]]:
    con = _pkg().state_connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "chat_history" not in tables:
            return []
        rows = con.execute(
            """SELECT role, text FROM chat_history
            WHERE thread = ? ORDER BY created_at DESC LIMIT ?""",
            [thread, limit],
        ).fetchall()
        return [{"role": r[0], "text": r[1]} for r in reversed(rows)]
    finally:
        con.close()


def save_facts(thread: str, facts: list[str], owner: str = "") -> None:
    if not thread or not facts:
        return
    pkg = _pkg()
    con = pkg.state_connect()
    try:
        with pkg.state_write_guard():
            con.execute(
                """CREATE TABLE IF NOT EXISTS thread_facts(
                thread VARCHAR, fact VARCHAR, created_at VARCHAR,
                owner VARCHAR)"""
            )
            for f in facts:
                f = str(f)[:500]
                dupe = con.execute(
                    "SELECT 1 FROM thread_facts WHERE thread=? AND fact=? LIMIT 1",
                    [thread, f],
                ).fetchone()
                if not dupe:
                    con.execute(
                        "INSERT INTO thread_facts VALUES (?,?,?,?)",
                        [thread, f, datetime.now(timezone.utc).isoformat(), owner[:80]],
                    )
    finally:
        con.close()


def thread_facts(thread: str, limit: int = 20) -> list[str]:
    if not thread:
        return []
    con = _pkg().state_connect()
    try:
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables"
            ).fetchall()
        }
        if "thread_facts" not in tables:
            return []
        rows = con.execute(
            """SELECT fact FROM thread_facts WHERE thread = ?
            ORDER BY created_at DESC LIMIT ?""",
            [thread, limit],
        ).fetchall()
        return [r[0] for r in reversed(rows)]
    except Exception:
        return []
    finally:
        con.close()


def strip_view_context(text: str) -> str:
    if not text.startswith("<dime-context "):
        return text
    close = text.find("</dime-context>")
    if close == -1:
        return text
    return text[close + len("</dime-context>"):].lstrip()


def list_threads(owner: str = "") -> list[dict[str, str]]:
    con = _pkg().state_connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "chat_history" not in tables:
            return []
        cols = {r[1] for r in con.execute("PRAGMA table_info(chat_history)").fetchall()}
        if "owner" in cols:
            rows = con.execute(
                """SELECT thread, MAX(created_at), COUNT(*)
                FROM chat_history WHERE owner = ?
                GROUP BY thread ORDER BY MAX(created_at) DESC LIMIT 100""",
                [owner],
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT thread, MAX(created_at), COUNT(*)
                FROM chat_history GROUP BY thread ORDER BY MAX(created_at) DESC LIMIT 100"""
            ).fetchall()
        out = []
        for r in rows:
            first = con.execute(
                """SELECT text FROM chat_history
                WHERE thread = ? AND role = 'human'
                ORDER BY created_at LIMIT 1""",
                [r[0]],
            ).fetchone()
            title = strip_view_context((first[0] if first else "") or "")[:90]
            if not title.strip():
                continue
            out.append({"id": r[0], "title": title, "updated": r[1], "turns": r[2]})
        return out
    finally:
        con.close()


def save_run(
    thread: str,
    question: str,
    answer: str,
    tables: list[dict],
    suggestions: list[str],
    owner: str = "",
    run_id: str = "",
) -> None:
    pkg = _pkg()
    con = pkg.state_connect()
    try:
        with pkg.state_write_guard():
            con.execute(
                """CREATE TABLE IF NOT EXISTS runs(
                thread VARCHAR, question VARCHAR, answer VARCHAR,
                tables VARCHAR, suggestions VARCHAR, created_at VARCHAR,
                owner VARCHAR)"""
            )
            cols = [r[1] for r in con.execute("PRAGMA table_info(runs)").fetchall()]
            if "owner" not in cols:
                con.execute("ALTER TABLE runs ADD COLUMN owner VARCHAR DEFAULT ''")
            if "run_id" not in cols:
                con.execute("ALTER TABLE runs ADD COLUMN run_id VARCHAR DEFAULT ''")
            con.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)",
                [
                    thread,
                    question[:2000],
                    answer[:8000],
                    _json.dumps(tables, default=str)[:60000],
                    _json.dumps(suggestions)[:2000],
                    datetime.now(timezone.utc).isoformat(),
                    owner[:80],
                    run_id[:80],
                ],
            )
    finally:
        con.close()


def list_runs(thread: str, owner: str = "") -> list[dict]:
    con = _pkg().state_connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "runs" not in tables:
            return []
        cols = {r[1] for r in con.execute("PRAGMA table_info(runs)").fetchall()}
        if "owner" not in cols:
            return []
        has_run_id = "run_id" in cols
        rows = con.execute(
            f"""SELECT question, answer, tables, suggestions, created_at
            {", run_id" if has_run_id else ""}
            FROM runs WHERE thread = ? AND owner = ?
            ORDER BY created_at DESC""",
            [thread, owner[:80]],
        ).fetchall()
        out = []
        for r in rows:
            try:
                tbl = _json.loads(r[2])
            except Exception:
                tbl = []
            try:
                sug = _json.loads(r[3])
            except Exception:
                sug = []
            row = {
                "question": r[0],
                "answer": r[1],
                "tables": tbl,
                "suggestions": sug,
                "created_at": r[4],
            }
            if has_run_id and r[5]:
                row["id"] = r[5]
            out.append(row)
        return out
    finally:
        con.close()


def _summarize_transcript(transcript: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage
    from ..providers import get_llm, resolve_model_id

    primary, model = resolve_model_id(None)
    client = get_llm(primary, model)
    if client is None:
        return ""
    resp = client.invoke(
        [
            SystemMessage(content="You compress chat threads into short memos."),
            HumanMessage(
                content=(
                    "Summarize these older chat turns for an NBA analyst "
                    "assistant. Produce three sections: entities discussed, "
                    "Q&A pairs (question plus one-line answer each), "
                    "open/unresolved items. Keep every entity name and number. "
                    "Be concise.\n\n" + transcript
                )
            ),
        ]
    )
    return str(getattr(resp, "content", "") or "").strip()


def compact_thread(
    thread: str, keep_recent: int = 4, threshold: int = 12
) -> dict:
    pkg = _pkg()
    con = pkg.state_connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "chat_history" not in tables:
            return {"compacted": False, "kept": 0, "dropped": 0}
        rows = con.execute(
            """SELECT rowid, role, text FROM chat_history
            WHERE thread = ? ORDER BY created_at, rowid""",
            [thread],
        ).fetchall()
    finally:
        con.close()
    if len(rows) <= threshold:
        return {"compacted": False, "kept": len(rows), "dropped": 0}
    keep = rows[-keep_recent:] if keep_recent > 0 else []
    older = rows[: len(rows) - len(keep)]
    transcript = "\n".join(f"{r[1]}: {(r[2] or '')[:1000]}" for r in older)
    try:
        memo = _summarize_transcript(transcript)
    except Exception:
        return {"compacted": False, "kept": len(rows), "dropped": 0}
    if not memo:
        return {"compacted": False, "kept": len(rows), "dropped": 0}
    con = pkg.state_connect()
    try:
        with pkg.state_write_guard():
            ids = [r[0] for r in older]
            con.execute(
                "DELETE FROM chat_history WHERE rowid IN (%s)"
                % ",".join(["?"] * len(ids)),
                ids,
            )
            con.execute(
                "INSERT INTO chat_history (thread, role, text, created_at)"
                " VALUES (?,?,?,?)",
                [
                    thread,
                    "summary",
                    ("THREAD SUMMARY: " + memo)[:4000],
                    datetime.now(timezone.utc).isoformat(),
                ],
            )
    finally:
        con.close()
    return {"compacted": True, "kept": len(keep), "dropped": len(older)}

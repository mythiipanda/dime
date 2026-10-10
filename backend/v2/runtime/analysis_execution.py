import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
_CHILD_SRC = (
"import sys,json\n"
"def main():\n"
"    req=json.load(sys.stdin)\n"
"    try:\n"
"        import duckdb\n"
"    except Exception as e:\n"
"        sys.stdout.write(json.dumps({\"ok\":False,\"error\":\"duckdb import failed: \"+str(e)}))\n"
"        return\n"
"    try:\n"
"        con=duckdb.connect(req[\"input_path\"],read_only=True,config={\"enable_external_access\":\"false\",\"autoinstall_known_extensions\":\"false\",\"autoload_known_extensions\":\"false\",\"lock_configuration\":\"true\"})\n"
"    except Exception as e:\n"
"        sys.stdout.write(json.dumps({\"ok\":False,\"error\":\"duckdb connect failed: \"+str(e)}))\n"
"        return\n"
"    try:\n"
"        cur=con.sql(req[\"sql\"])\n"
"        cols=[d[0] for d in cur.description] if cur.description else []\n"
"        rows=cur.fetchall()\n"
"        con.close()\n"
"    except Exception as e:\n"
"        sys.stdout.write(json.dumps({\"ok\":False,\"error\":\"duckdb query failed: \"+str(e)}))\n"
"        return\n"
"    out=[[float(c) if isinstance(c,float) else c for c in r] for r in rows]\n"
"    sys.stdout.write(json.dumps({\"ok\":True,\"columns\":cols,\"rows\":out}))\n"
"main()\n"
)
_THROUGH_WORDS = frozenset(["SELECT", "WITH", "VALUES"])
_WRITE_WORDS = frozenset(["DELETE", "INSERT", "UPDATE", "DROP", "CREATE", "ALTER", "TRUNCATE", "MERGE", "REPLACE", "GRANT", "REVOKE", "VACUUM", "CHECKPOINT"])
@dataclass(frozen=True)
class EnforcementState:
    job_object: str = "unsupported"
    tree_termination: str = "unsupported"
    stdin_gate: str = "unsupported"
    isolated_environment: str = "unsupported"
@dataclass(frozen=True)
class AnalysisRequest:
    run_id: str
    node_id: str
    sql: str
    input_path: str
    input_sha256: str
    artifact_dir: str
    deadline_s: float = 20.0
    row_cap: int = 25
    byte_cap: int = 65536
    allowed_tables: tuple = ()
    memory_limit_bytes: object = None
@dataclass
class AnalysisResult:
    status: str
    rows: object = None
    columns: object = None
    error: object = None
    dead: bool = False
    pid: object = None
    row_cap_hit: bool = False
    truncated: bool = False
    enforcement: EnforcementState = field(default_factory=EnforcementState)
    run_id: str = ""
    node_id: str = ""
    input_sha256: str = ""
def _sha_of(path: str):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
def _first_word(sql: str):
    m = re.match(r"\s*\(?\s*([A-Za-z]+)", sql)
    if not m:
        return ""
    return m.group(1).upper()
_TABLE_FUNCTIONS = frozenset(["query_table", "read_csv", "read_csv_auto", "read_parquet", "read_json", "read_json_auto", "parquet_scan", "csv_scan", "sniff_csv"])
_STOP_WORDS = frozenset(["WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET", "UNION", "INTERSECT", "EXCEPT", "ON", "USING", "AS", "WINDOW", "QUALIFY", "RETURNING", "SET", "VALUES", "SELECT"])
def _tokenize_identifiers(sql: str):
    tokens = []
    i = 0
    n = len(sql)
    while i < n:
        c = sql[i]
        if c == ".":
            tokens.append(("dot", "."))
            i += 1
            continue
        if c == ",":
            tokens.append(("comma", ","))
            i += 1
            continue
        if c in ('"', "'", "`"):
            quote = c
            j = i + 1
            buf = []
            while j < n:
                if sql[j] == quote:
                    if j + 1 < n and sql[j + 1] == quote:
                        buf.append(quote)
                        j += 2
                        continue
                    break
                buf.append(sql[j])
                j += 1
            tokens.append(("quoted", "".join(buf)))
            i = j + 1
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            word = sql[i:j]
            k = j
            while k < n and sql[k] in " \t\r\n":
                k += 1
            if k < n and sql[k] == "(":
                tokens.append(("func", word))
                i = j
                continue
            tokens.append(("word", word))
            i = j
            continue
        i += 1
    return tokens
def _is_path_like(value):
    if not value:
        return False
    if value.startswith(("http://", "https://", "s3://", "file://", "gs://", "gcs://", "az://", "s3a://", "abfs://")):
        return True
    if "/" in value or "\\" in value:
        return True
    if len(value) > 1 and value[1] == ":" and value[0].isalpha():
        return True
    low = value.lower()
    if low.endswith((".csv", ".parquet", ".json", ".jsonl", ".ndjson", ".tsv", ".gz", ".zip", ".duckdb", ".db", ".sqlite", ".xlsx")):
        return True
    return False
def _table_component(name):
    return name.split(".")[-1]
def _referenced_tables(sql: str):
    tokens = _tokenize_identifiers(sql)
    names = []
    n = len(tokens)
    i = 0
    while i < n:
        kind, value = tokens[i]
        if kind == "word" and value.upper() in ("FROM", "JOIN"):
            j = i + 1
            while j < n and tokens[j][0] == "func" and tokens[j][1].upper() == "LATERAL":
                j += 1
            while j < n:
                tk, tv = tokens[j]
                if tk == "word" and tv.upper() in _STOP_WORDS:
                    break
                if tk == "quoted":
                    names.append(tv)
                elif tk == "func":
                    if j + 1 < n and tokens[j + 1][0] == "quoted":
                        arg = tokens[j + 1][1]
                        if not _is_path_like(arg):
                            names.append(arg)
                    break
                elif tk == "word":
                    k = j
                    parts = []
                    while k < n and tokens[k][0] == "word":
                        parts.append(tokens[k][1])
                        k += 1
                        if k < n and tokens[k][0] == "dot":
                            k += 1
                            continue
                        break
                    names.append(".".join(parts))
                    j = k - 1
                if j + 1 < n and tokens[j + 1][0] == "comma":
                    j += 2
                    continue
                break
        if kind == "func" and value.lower() in _TABLE_FUNCTIONS:
            j = i + 1
            while j < n and tokens[j][0] == "func" and tokens[j][1].upper() == "LATERAL":
                j += 1
            if j < n and tokens[j][0] == "quoted" and not _is_path_like(tokens[j][1]):
                names.append(tokens[j][1])
        i += 1
    return names
def _local_names(sql: str):
    found = set()
    for pat in (r"WITH\s+(?:RECURSIVE\s+)?([A-Za-z_][\w]*)", r",\s*([A-Za-z_][\w]*)\s*(?:\([^)]*\))?\s+AS\s*\("):
        for m in re.finditer(pat, sql, flags=re.IGNORECASE):
            found.add(m.group(1))
    return found
class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]
class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_ulong),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_ulong),
        ("Affinity", ctypes.c_ulonglong),
        ("PriorityClass", ctypes.c_ulong),
        ("SchedulingClass", ctypes.c_ulong),
    ]
class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
_JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
_JOBOBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
def _create_job(limit):
    if os.name != "nt":
        return (None, "unsupported: non-windows host")
    try:
        k = ctypes.windll.kernel32
        k.CreateJobObjectW.restype = wintypes.HANDLE
        k.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        k.SetInformationJobObject.restype = wintypes.BOOL
        k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        handle = k.CreateJobObjectW(None, None)
        if not handle:
            return (None, "unsupported: CreateJobObjectW failed")
        ext = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        flags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        limit_val = None
        if limit is not None:
            try:
                limit_val = int(limit)
            except Exception as e:
                k.CloseHandle(wintypes.HANDLE(handle))
                return (None, "unsupported: memory limit not an integer: " + str(e))
            if limit_val <= 0:
                k.CloseHandle(wintypes.HANDLE(handle))
                return (None, "unsupported: memory limit must be positive")
            flags |= _JOB_OBJECT_LIMIT_PROCESS_MEMORY | _JOB_OBJECT_LIMIT_JOB_MEMORY
            ext.ProcessMemoryLimit = limit_val
            ext.JobMemoryLimit = limit_val
        ext.BasicLimitInformation.LimitFlags = flags
        ok = k.SetInformationJobObject(
            wintypes.HANDLE(handle),
            _JOBOBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(ext),
            ctypes.sizeof(ext),
        )
        if not ok:
            err = ctypes.get_last_error()
            k.CloseHandle(wintypes.HANDLE(handle))
            if limit is not None:
                return (None, "unsupported: memory limit rejected by OS: " + str(err))
            return (None, "unsupported: SetInformationJobObject failed: " + str(err))
        if limit is not None:
            return (int(handle), "established with memory limit " + str(limit_val))
        return (int(handle), "established")
    except Exception as e:
        return (None, "unsupported: " + str(e))
def _assign_to_job(job, proc):
    try:
        k = ctypes.windll.kernel32
        k.AssignProcessToJobObject.restype = wintypes.BOOL
        k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        ok = k.AssignProcessToJobObject(wintypes.HANDLE(job), wintypes.HANDLE(proc._handle))
        return bool(ok)
    except Exception:
        return False
def _terminate_job(job):
    try:
        k = ctypes.windll.kernel32
        k.TerminateJobObject.restype = wintypes.BOOL
        k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.TerminateJobObject(wintypes.HANDLE(job), 1)
    except Exception:
        pass
def _close_job(job):
    try:
        k = ctypes.windll.kernel32
        k.CloseHandle.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle(wintypes.HANDLE(job))
    except Exception:
        pass
def _policy_rejected(request, reason):
    return AnalysisResult(status="policy_rejected", rows=None, columns=None, error=reason, dead=False, pid=None, enforcement=EnforcementState(), run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
def execute_analysis(request, cancel_event=None):
    try:
        os.makedirs(request.artifact_dir, exist_ok=True)
    except Exception as e:
        return AnalysisResult(status="execution_failed", rows=None, columns=None, error="artifact dir failed: " + str(e), dead=False, pid=None, enforcement=EnforcementState(), run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    try:
        actual = _sha_of(request.input_path)
    except Exception as e:
        return AnalysisResult(status="execution_failed", rows=None, columns=None, error="input read failed: " + str(e), dead=False, pid=None, enforcement=EnforcementState(), run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    if actual.lower() != str(request.input_sha256).lower():
        return _policy_rejected(request, "input pin mismatch")
    word = _first_word(request.sql)
    if word in _WRITE_WORDS:
        return _policy_rejected(request, "write statement rejected")
    if word not in _THROUGH_WORDS and word not in ("ATTACH", "COPY", "INSTALL", "LOAD", "PRAGMA", "SET"):
        if word == "":
            return _policy_rejected(request, "empty statement rejected")
        return _policy_rejected(request, "statement rejected: " + word)
    allowed = set(request.allowed_tables or ()) | _local_names(request.sql)
    for name in _referenced_tables(request.sql):
        component = _table_component(name)
        if allowed and name not in allowed and component not in allowed and component.lower() not in ("duckdb_memory",):
            return _policy_rejected(request, "unauthorized table: " + name)
    job, job_reason = _create_job(request.memory_limit_bytes)
    if job is None:
        return AnalysisResult(status="unsupported", rows=None, columns=None, error=job_reason, dead=False, pid=None, enforcement=EnforcementState(job_object=job_reason), run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    enforcement = EnforcementState(job_object=job_reason, tree_termination="job terminate", stdin_gate="stdin request gate", isolated_environment="-I -B allowlist")
    payload = json.dumps({"input_path": request.input_path, "sql": request.sql, "row_cap": request.row_cap})
    try:
        proc = subprocess.Popen([sys.executable, "-I", "-B", "-c", _CHILD_SRC], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        _close_job(job)
        return AnalysisResult(status="execution_failed", rows=None, columns=None, error="spawn failed: " + str(e), dead=False, pid=None, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    pid = proc.pid
    assigned = _assign_to_job(job, proc)
    if not assigned:
        _terminate_job(job)
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        _close_job(job)
        return AnalysisResult(status="execution_failed", rows=None, columns=None, error="job assignment failed", dead=True, pid=pid, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    try:
        proc.stdin.write(payload.encode("utf-8"))
        proc.stdin.close()
    except Exception:
        pass
    start = time.monotonic()
    status = None
    stdout_data = b""
    while True:
        if cancel_event is not None and cancel_event.is_set():
            status = "cancelled"
            break
        if proc.poll() is not None:
            break
        if (time.monotonic() - start) > float(request.deadline_s):
            status = "timeout"
            break
        time.sleep(0.02)
    if status in ("cancelled", "timeout"):
        _terminate_job(job)
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        try:
            stdout_data, _ = proc.communicate(timeout=5)
        except Exception:
            stdout_data = b""
        dead = proc.poll() is not None
        _close_job(job)
        return AnalysisResult(status=status, rows=None, columns=None, error=None, dead=bool(dead), pid=pid, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    try:
        stdout_data, _ = proc.communicate(timeout=10)
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass
        _close_job(job)
        return AnalysisResult(status="execution_failed", rows=None, columns=None, error="collect failed: " + str(e), dead=proc.poll() is not None, pid=pid, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    dead = proc.poll() is not None
    _close_job(job)
    try:
        doc = json.loads(stdout_data.decode("utf-8", errors="replace") or "{}")
    except Exception as e:
        return AnalysisResult(status="execution_failed", rows=None, columns=None, error="bad child output: " + str(e), dead=bool(dead), pid=pid, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    if not doc.get("ok"):
        return AnalysisResult(status="execution_failed", rows=None, columns=None, error=doc.get("error") or "duckdb failed", dead=bool(dead), pid=pid, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
    columns = tuple(doc.get("columns") or [])
    rows = [list(r) for r in (doc.get("rows") or [])]
    row_cap_hit = False
    if len(rows) > int(request.row_cap):
        rows = rows[:int(request.row_cap)]
        row_cap_hit = True
    truncated = False
    cap = int(request.byte_cap)
    while rows and len(json.dumps(rows)) > cap:
        rows = rows[:-1]
        truncated = True
    return AnalysisResult(status="success", rows=rows, columns=columns, error=None, dead=bool(dead), pid=pid, row_cap_hit=row_cap_hit, truncated=truncated, enforcement=enforcement, run_id=request.run_id, node_id=request.node_id, input_sha256=request.input_sha256)
def build_envelope(result, evidence_id, capability, source, observed_at):
    from v2.contracts import EvidenceEnvelope
    table = []
    cols = list(result.columns or [])
    for row in (result.rows or []):
        table.append({str(k): v for k, v in zip(cols, list(row))})
    lineage = ["run:" + str(result.run_id), "node:" + str(result.node_id), "input:" + str(result.input_sha256)[:16]]
    return EvidenceEnvelope(evidence_id=evidence_id, capability=capability, source=source, observed_at=observed_at, rows=table, lineage=lineage)
